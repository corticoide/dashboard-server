#!/usr/bin/env bash
# ServerDash — development deploy & start script (uvicorn, --reload)
# Usage: ./deploy.sh [--port 8443] [--host 0.0.0.0] [--no-service]
#   --no-service  Accepted for compatibility; dev mode never creates a system service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8443}"
HOST="${HOST:-0.0.0.0}"

# Parse flags
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --port)       PORT="$2"; shift ;;
    --host)       HOST="$2"; shift ;;
    --no-service) ;;  # no-op: dev always runs in foreground
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

echo "==> ServerDash deploy (dev)"

# --- Python venv ---
if [ ! -d ".venv" ]; then
  echo "--> Creating Python virtual environment..."
  python3 -m venv .venv || { echo "ERROR: python3-venv not available. Install it (e.g. apt install python3-venv)."; exit 1; }
fi

echo "--> Installing Python dependencies..."
.venv/bin/pip install -q -r backend/requirements.txt

# --- .env ---
if [ ! -f ".env" ]; then
  echo "--> Creating .env from .env.example..."
  cp .env.example .env
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s/change-me-to-a-long-random-string/$SECRET/" .env
  echo "    JWT_SECRET generated. Edit .env to set ADMIN_PASSWORD before first login."
fi

# --- Directories ---
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
fi

# --- Node.js / npm ---
if ! command -v npm &>/dev/null; then
  echo "--> npm not found. Installing Node.js..."
  if command -v dnf &>/dev/null; then
    sudo dnf install -y nodejs npm
  elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y nodejs npm
  elif command -v pacman &>/dev/null; then
    sudo pacman -Sy --noconfirm nodejs npm
  elif command -v zypper &>/dev/null; then
    sudo zypper install -y nodejs npm
  else
    echo "ERROR: Cannot auto-install Node.js — package manager not recognised."
    echo "       Install Node.js manually and re-run this script."
    exit 1
  fi
fi

# --- Frontend build ---
if [ ! -f "backend/static/index.html" ]; then
  echo "--> Building frontend..."
  (cd frontend && npm install --silent && npm run build)
fi

# --- Start server ---
echo ""
echo "==> Starting ServerDash (dev) on https://$HOST:$PORT"
echo "    Open https://localhost:$PORT in your browser (accept the self-signed cert)"
echo "    Press Ctrl+C to stop."
echo ""

exec .venv/bin/uvicorn backend.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --ssl-certfile certs/cert.pem \
  --ssl-keyfile certs/key.pem \
  --reload
