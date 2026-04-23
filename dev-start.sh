#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

die() {
  echo -e "${RED}✗ Error: $1${NC}"
  exit 1
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

info() {
  echo -e "${YELLOW}→ $1${NC}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect LAN IPv4
LAN_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')
[ -z "$LAN_IP" ] && LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$LAN_IP" ] && LAN_IP="localhost"

# Check prerequisites
info "Checking prerequisites..."

[ -f .env ] || die ".env not found — create from .env.example"
success ".env exists"

[ -f certs/cert.pem ] || die "certs/cert.pem not found — run: python -m backend.scripts.generate_cert"
success "certs/cert.pem exists"

[ -f certs/key.pem ] || die "certs/key.pem not found — run: python -m backend.scripts.generate_cert"
success "certs/key.pem exists"

# Accept either venv or .venv
VENV=""
if [ -d ".venv" ]; then
  VENV=".venv"
elif [ -d "venv" ]; then
  VENV="venv"
else
  die "Python venv not found — run: python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
fi
success "$VENV exists"

# Frontend deps
if [ ! -d "frontend/node_modules" ]; then
  info "Installing frontend dependencies..."
  (cd frontend && npm install)
fi
success "frontend/node_modules exists"

# Ensure Monaco runtime files are copied to public/
if [ ! -f "frontend/public/monaco-editor/vs/loader.js" ]; then
  info "Copying Monaco Editor runtime files..."
  node frontend/scripts/copy-monaco.js
fi
success "Monaco runtime files ready"

# Cleanup function for SIGINT/SIGTERM
cleanup() {
  info "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null || true
  success "Cleaned up"
  exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
info "Starting backend on https://$LAN_IP:8443..."
source "$VENV/bin/activate" && python -m backend.main &
BACKEND_PID=$!
success "Backend started (PID: $BACKEND_PID)"

# Start frontend dev server
info "Starting frontend dev server..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
success "Frontend started (PID: $FRONTEND_PID)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ServerDash Dev Environment Ready${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backend:  https://$LAN_IP:8443"
echo "Frontend: http://$LAN_IP:5173  (proxies to backend)"
echo ""
echo "Local:    https://localhost:8443  /  http://localhost:5173"
echo ""
echo "Press Ctrl+C to shutdown"
echo ""

# Wait for both processes
wait
