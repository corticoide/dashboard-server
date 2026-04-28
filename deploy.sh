#!/usr/bin/env bash
# ServerDash deploy script — Debian/Ubuntu, RHEL/Fedora, Arch, openSUSE, Alpine
# Usage: ./deploy.sh [--port 8443] [--host 0.0.0.0]

# Re-exec with bash if invoked via sh/dash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8443}"
HOST="${HOST:-0.0.0.0}"

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --port)       PORT="$2"; shift ;;
    --host)       HOST="$2"; shift ;;
    --no-service) ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

# --- Package manager detection ---
detect_pm() {
  if   command -v apt-get &>/dev/null; then echo "apt"
  elif command -v dnf     &>/dev/null; then echo "dnf"
  elif command -v yum     &>/dev/null; then echo "yum"
  elif command -v pacman  &>/dev/null; then echo "pacman"
  elif command -v zypper  &>/dev/null; then echo "zypper"
  elif command -v apk     &>/dev/null; then echo "apk"
  else echo "unknown"; fi
}
PM=$(detect_pm)

pkg_install() {
  case "$PM" in
    apt)    sudo apt-get install -y "$@" ;;
    dnf)    sudo dnf install -y "$@" ;;
    yum)    sudo yum install -y "$@" ;;
    pacman) sudo pacman -Sy --noconfirm "$@" ;;
    zypper) sudo zypper install -y "$@" ;;
    apk)    sudo apk add --no-cache "$@" ;;
    *)      echo "ERROR: Unsupported package manager. Install manually: $*"; exit 1 ;;
  esac
}

echo "==> ServerDash deploy  [pm: $PM]"

# --- System: curl (needed for NodeSource) ---
if ! command -v curl &>/dev/null; then
  echo "--> Installing curl..."
  case "$PM" in
    apt)    pkg_install curl ;;
    dnf|yum) pkg_install curl ;;
    pacman) pkg_install curl ;;
    zypper) pkg_install curl ;;
    apk)    pkg_install curl ;;
  esac
fi

# --- System: udisks2 (disk management daemon) ---
if ! command -v udisksctl &>/dev/null; then
  echo "--> Installing udisks2..."
  case "$PM" in
    apt)    pkg_install udisks2 ;;
    dnf|yum) pkg_install udisks2 ;;
    pacman) pkg_install udisks2 ;;
    zypper) pkg_install udisks2 ;;
    apk)    pkg_install udisks2 ;;
    *)      echo "WARNING: Cannot auto-install udisks2. Install it manually."; ;;
  esac
fi

# --- System: Python 3 + build deps for native extensions ---
if ! command -v python3 &>/dev/null; then
  echo "--> Installing Python 3..."
  case "$PM" in
    apt)    pkg_install python3 python3-venv python3-pip python3-dev build-essential libssl-dev libffi-dev ;;
    dnf|yum) pkg_install python3 python3-pip python3-devel gcc openssl-devel libffi-devel ;;
    pacman) pkg_install python python-pip base-devel ;;
    zypper) pkg_install python3 python3-pip python3-devel gcc libopenssl-devel libffi-devel ;;
    apk)    pkg_install python3 py3-pip python3-dev musl-dev gcc libffi-dev openssl-dev ;;
    *)      echo "ERROR: python3 not found. Install it manually."; exit 1 ;;
  esac
else
  # Ensure build deps for cryptography / bcrypt native compilation
  if ! python3 -c "import ssl, ctypes" 2>/dev/null; then
    echo "--> Installing Python build dependencies..."
    case "$PM" in
      apt)    pkg_install python3-dev build-essential libssl-dev libffi-dev ;;
      dnf|yum) pkg_install python3-devel gcc openssl-devel libffi-devel ;;
      pacman) pkg_install base-devel ;;
      zypper) pkg_install python3-devel gcc libopenssl-devel libffi-devel ;;
      apk)    pkg_install python3-dev musl-dev gcc libffi-dev openssl-dev ;;
    esac
  fi
fi

# --- Python venv ---
if [ ! -d ".venv" ]; then
  echo "--> Creating Python virtual environment..."
  if ! python3 -c "import venv" 2>/dev/null; then
    [ "$PM" = "apt" ] && pkg_install python3-venv || { echo "ERROR: python3 venv module missing."; exit 1; }
  fi
  python3 -m venv .venv
fi

echo "--> Installing Python dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt

# --- .env ---
if [ ! -f ".env" ]; then
  echo "--> Creating .env from .env.example..."
  cp .env.example .env
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s/change-me-to-a-long-random-string/$SECRET/" .env
  echo "    JWT_SECRET generated. Edit .env to set ADMIN_PASSWORD before first login."
fi

mkdir -p certs data

# --- TLS certificate ---
if [ ! -f "certs/cert.pem" ]; then
  echo "--> Generating self-signed TLS certificate..."
  .venv/bin/python -m backend.scripts.generate_cert
fi

# --- Database init ---
if [ ! -f "data/serverdash.db" ]; then
  echo "--> Initialising database and admin user..."
  .venv/bin/python -m backend.scripts.init_db
else
  echo "--> Database already exists — skipping init."
  echo "    If login fails, delete data/serverdash.db and re-run to reset credentials."
fi

# --- Node.js (requires >= 18 for Vite/Vue 3) ---
install_nodejs() {
  echo "--> Installing Node.js 20.x..."
  case "$PM" in
    apt)
      curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
      pkg_install nodejs
      ;;
    dnf)    pkg_install nodejs npm ;;
    yum)    sudo yum module install -y nodejs:20 2>/dev/null || pkg_install nodejs npm ;;
    pacman) pkg_install nodejs npm ;;
    zypper) pkg_install nodejs20 npm20 2>/dev/null || pkg_install nodejs npm ;;
    apk)    pkg_install nodejs npm ;;
    *)      echo "ERROR: Cannot auto-install Node.js. Install Node.js 18+ manually."; exit 1 ;;
  esac
}

NODE_OK=false
if command -v node &>/dev/null; then
  NODE_MAJOR=$(node -e "process.stdout.write(process.versions.node.split('.')[0])")
  if [ "$NODE_MAJOR" -ge 18 ] 2>/dev/null; then
    NODE_OK=true
  else
    echo "--> Node.js $NODE_MAJOR.x found but >= 18 required. Upgrading..."
  fi
fi
[ "$NODE_OK" = false ] && install_nodejs

# --- Frontend build ---
echo "--> Building frontend..."
(cd frontend && npm install --silent && npm run build)

# --- Start server ---
echo ""
echo "==> Starting ServerDash on https://$HOST:$PORT"
echo "    Open https://localhost:$PORT (accept the self-signed cert)"
echo "    Press Ctrl+C to stop."
echo ""

exec .venv/bin/uvicorn backend.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --ssl-certfile certs/cert.pem \
  --ssl-keyfile certs/key.pem \
  --reload
