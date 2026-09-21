#!/usr/bin/env bash
# rebuild-redeploy.sh
# Tear down, rebuild (no cache), and restart the IBM Power Porting Triage Agent stack.
# Works with Docker Compose (v2 plugin) or Podman Compose.
#
# Usage:
#   ./rebuild-redeploy.sh              # rebuild all services
#   ./rebuild-redeploy.sh backend      # rebuild only the backend service
#   ./rebuild-redeploy.sh frontend     # rebuild only the frontend service

set -euo pipefail

# Ensure standard bin paths (Podman, Homebrew, Docker, pip-installed tools) are in PATH
export PATH="/opt/podman/bin:/usr/local/bin:/opt/homebrew/bin:${HOME}/Library/Python/3.9/bin:${HOME}/.local/bin:$PATH"

# ---------------------------------------------------------------------------
# Parse optional service filter argument
# ---------------------------------------------------------------------------
SERVICE="${1:-}"
if [[ -n "$SERVICE" && "$SERVICE" != "backend" && "$SERVICE" != "frontend" ]]; then
  echo "Error: unknown service '${SERVICE}'. Valid options: backend, frontend (or omit for all)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
if [[ -f .env ]]; then
  echo "Loading environment from .env..."
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs)
fi

# ---------------------------------------------------------------------------
# Detect compose tool
# ---------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif command -v podman-compose >/dev/null 2>&1; then
  COMPOSE_CMD="podman-compose"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
  COMPOSE_CMD="podman compose"
else
  echo "Error: No compose provider found." >&2
  echo "Tried: docker compose, docker-compose, podman-compose, podman compose" >&2
  echo "Install one of: docker, docker-compose, or run: pip3 install podman-compose" >&2
  exit 1
fi

echo "Using compose engine: ${COMPOSE_CMD}"

# ---------------------------------------------------------------------------
# Step 1: Stop and remove existing containers
# ---------------------------------------------------------------------------
echo ""
echo "==> [1/3] Stopping existing containers..."
if [[ -n "$SERVICE" ]]; then
  $COMPOSE_CMD stop "$SERVICE" || true
  # podman-compose does not support 'rm'; fall back to podman/docker rm directly
  if command -v podman >/dev/null 2>&1; then
    podman rm -f "ibm-power-triage-${SERVICE}" 2>/dev/null || true
  elif command -v docker >/dev/null 2>&1; then
    docker rm -f "ibm-power-triage-${SERVICE}" 2>/dev/null || true
  fi
else
  $COMPOSE_CMD down 2>/dev/null || true
  # Ensure containers are gone even if 'down' failed (e.g. podman-compose quirks)
  if command -v podman >/dev/null 2>&1; then
    podman rm -f ibm-power-triage-backend ibm-power-triage-frontend 2>/dev/null || true
  elif command -v docker >/dev/null 2>&1; then
    docker rm -f ibm-power-triage-backend ibm-power-triage-frontend 2>/dev/null || true
  fi
fi

# ---------------------------------------------------------------------------
# Step 2: Rebuild images (no layer cache to pick up all code changes)
# ---------------------------------------------------------------------------
echo ""
echo "==> [2/3] Rebuilding image(s) (--no-cache)..."
if [[ -n "$SERVICE" ]]; then
  $COMPOSE_CMD build --no-cache "$SERVICE"
else
  $COMPOSE_CMD build --no-cache
fi

# ---------------------------------------------------------------------------
# Step 3: Start containers
# ---------------------------------------------------------------------------
echo ""
echo "==> [3/3] Starting container(s)..."
if [[ -n "$SERVICE" ]]; then
  $COMPOSE_CMD up -d "$SERVICE"
else
  $COMPOSE_CMD up -d
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Rebuild & redeploy complete!"
if [[ -z "$SERVICE" ]]; then
echo " Web UI:        http://localhost:8080"
echo " API Docs:      http://localhost:8000/docs"
echo " Health:        http://localhost:8000/api/health"
fi
echo "============================================================"
echo "To tail logs:   ${COMPOSE_CMD} logs -f ${SERVICE}"
echo "To stop stack:  ./docker-stop.sh"
