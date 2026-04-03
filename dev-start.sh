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

# Check prerequisites
info "Checking prerequisites..."

[ -f .env ] || die ".env not found — create from .env.example"
success ".env exists"

[ -f certs/cert.pem ] || die "certs/cert.pem not found — run: python -m backend.scripts.generate_cert"
success "certs/cert.pem exists"

[ -f certs/key.pem ] || die "certs/key.pem not found — run: python -m backend.scripts.generate_cert"
success "certs/key.pem exists"

[ -d venv ] || die "venv not found — run: python -m venv venv && source venv/bin/activate && pip install -r backend/requirements.txt"
success "venv exists"

[ -d frontend/node_modules ] || die "frontend/node_modules not found — cd frontend && npm install"
success "frontend/node_modules exists"

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
info "Starting backend on https://localhost:8443..."
source venv/bin/activate && python -m backend.main &
BACKEND_PID=$!
success "Backend started (PID: $BACKEND_PID)"

# Start frontend dev server
info "Starting frontend dev server..."
cd frontend && npm run dev &
FRONTEND_PID=$!
cd ..
success "Frontend started (PID: $FRONTEND_PID)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ServerDash Dev Environment Ready${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backend:  https://localhost:8443"
echo "Frontend: http://localhost:5173 (proxies to backend)"
echo ""
echo "Press Ctrl+C to shutdown"
echo ""

# Wait for both processes
wait
