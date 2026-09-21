#!/usr/bin/env bash
# Universal script to bring up the IBM Power Porting Triage Agent stack via Docker or Podman Compose

set -e

# Ensure standard bin paths (Podman, Homebrew, Docker) are in PATH
export PATH="/opt/podman/bin:/usr/local/bin:/opt/homebrew/bin:${HOME}/Library/Python/3.9/bin:${HOME}/.local/bin:$PATH"

# Load .env if present
if [ -f .env ]; then
  echo "Loading environment from .env..."
  export $(grep -v '^#' .env | xargs)
fi

# Determine container compose tool
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif command -v podman-compose >/dev/null 2>&1; then
  COMPOSE_CMD="podman-compose"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
  COMPOSE_CMD="podman compose"
else
  echo "Error: No compose provider found."
  echo "Tried: docker compose, docker-compose, podman-compose, podman compose"
  exit 1
fi

echo "Using compose engine: $COMPOSE_CMD"
echo "Building and starting IBM Power Porting Triage Agent containers..."
$COMPOSE_CMD up -d --build

echo ""
echo "============================================================"
echo " IBM Power Porting Triage Agent is up and running!"
echo " Web UI:           http://localhost:5173 (or http://localhost)"
echo " API Docs:         http://localhost:8000/docs"
echo " Health Status:    http://localhost:8000/api/health"
echo "============================================================"
echo "To view logs: $COMPOSE_CMD logs -f"
echo "To stop:      ./docker-stop.sh"
