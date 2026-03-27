#!/usr/bin/env bash
# ServerDash — production deploy script (gunicorn, 4 workers)
# Usage: ./deploy-prod.sh [--port 8443] [--host 0.0.0.0] [--workers 4] [--no-service]
#
#   Default:      installs/updates a systemd service and starts it
#   --no-service: skips systemd entirely, runs gunicorn in the foreground
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8443}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-4}"
NO_SERVICE=false

# Parse flags
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --port)       PORT="$2";    shift ;;
    --host)       HOST="$2";    shift ;;
    --workers)    WORKERS="$2"; shift ;;
    --no-service) NO_SERVICE=true ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

echo "==> ServerDash production deploy"

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

# --- Start: foreground or systemd service ---
if [ "$NO_SERVICE" = true ]; then
  echo ""
  echo "==> Starting ServerDash (production, foreground) on https://$HOST:$PORT"
  echo "    Workers: $WORKERS"
  echo "    Press Ctrl+C to stop."
  echo ""
  exec .venv/bin/gunicorn \
    -w "$WORKERS" \
    -k uvicorn.workers.UvicornWorker \
    backend.main:app \
    --bind "$HOST:$PORT" \
    --certfile certs/cert.pem \
    --keyfile certs/key.pem
fi

# --- Systemd service ---
SERVICE="serverdash"
SERVICE_FILE="/etc/systemd/system/${SERVICE}.service"
GUNICORN="$SCRIPT_DIR/.venv/bin/gunicorn"

echo "--> Installing systemd service (${SERVICE})..."

SERVICE_UNIT="[Unit]
Description=ServerDash server management dashboard
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${SCRIPT_DIR}
Environment=PORT=${PORT}
ExecStart=${GUNICORN} -w ${WORKERS} -k uvicorn.workers.UvicornWorker backend.main:app --bind ${HOST}:${PORT} --certfile ${SCRIPT_DIR}/certs/cert.pem --keyfile ${SCRIPT_DIR}/certs/key.pem
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

SUDO=""
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
  echo "    (not root — using sudo for systemd commands)"
fi

echo "$SERVICE_UNIT" | $SUDO tee "$SERVICE_FILE" > /dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE"
$SUDO systemctl restart "$SERVICE"

echo ""
echo "==> ServerDash service installed and running!"
echo "    Status:  ${SUDO} systemctl status ${SERVICE}"
echo "    Logs:    ${SUDO} journalctl -u ${SERVICE} -f"
echo "    URL:     https://localhost:${PORT}"
