#!/usr/bin/env bash
# Universal script to bring down the IBM Power Porting Triage Agent stack via Docker or Podman Compose

# Ensure standard bin paths are in PATH
export PATH="/opt/podman/bin:/usr/local/bin:/opt/homebrew/bin:${HOME}/Library/Python/3.9/bin:${HOME}/.local/bin:$PATH"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif command -v podman-compose >/dev/null 2>&1; then
  COMPOSE_CMD="podman-compose"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
  COMPOSE_CMD="podman compose"
else
  echo "Error: No compose command found."
  exit 1
fi

echo "Stopping and removing IBM Power Porting Triage Agent containers using $COMPOSE_CMD..."
$COMPOSE_CMD down

# Also ensure named containers are removed if previously started standalone
if command -v podman >/dev/null 2>&1; then
  podman rm -f ibm-power-triage-backend ibm-power-triage-frontend >/dev/null 2>&1 || true
elif command -v docker >/dev/null 2>&1; then
  docker rm -f ibm-power-triage-backend ibm-power-triage-frontend >/dev/null 2>&1 || true
fi

echo "Containers stopped successfully."
