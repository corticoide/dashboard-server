#!/usr/bin/env bash
# ServerDash — production deploy script (gunicorn, 4 workers, no --reload)
# Usage: ./deploy-prod.sh [--port 8443] [--host 0.0.0.0] [--workers 4]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8443}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-4}"

# Parse flags
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --port)    PORT="$2";    shift ;;
    --host)    HOST="$2";    shift ;;
    --workers) WORKERS="$2"; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

echo "==> ServerDash production deploy"

# --- Python venv ---
if [ ! -d ".venv" ]; then
  echo "--> Creating Python virtual environment..."
  python3 -m venv .venv
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

# --- Frontend build ---
if [ ! -f "backend/static/index.html" ]; then
  echo "--> Building frontend..."
  if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. Install Node.js to build the frontend."
    exit 1
  fi
  cd frontend && npm install --silent && npm run build && cd ..
fi

# --- Start server (production: gunicorn, no --reload) ---
echo ""
echo "==> Starting ServerDash (production) on https://$HOST:$PORT"
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
