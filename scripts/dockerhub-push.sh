#!/usr/bin/env bash
# Build and push all Career Copilot images to Docker Hub.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Error: .env not found. Copy .env.example to .env and configure it." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${DOCKERHUB_USER:?Set DOCKERHUB_USER in .env}"
TAG="${IMAGE_TAG:-latest}"
: "${NEXT_PUBLIC_API_URL:?Set NEXT_PUBLIC_API_URL in .env}"
: "${GITHUB_REDIRECT_URI:?Set GITHUB_REDIRECT_URI in .env}"
: "${GITHUB_CLIENT_ID:?Set GITHUB_CLIENT_ID in .env}"

echo "Building images as ${DOCKERHUB_USER}:${TAG} ..."

docker build -t "${DOCKERHUB_USER}/career-copilot-backend:${TAG}" ./backend
docker build -t "${DOCKERHUB_USER}/career-copilot-mcp:${TAG}" -f ./backend/Dockerfile.mcp ./backend
docker build -t "${DOCKERHUB_USER}/career-copilot-livekit-agent:${TAG}" ./livekit-agent
docker build \
  -t "${DOCKERHUB_USER}/career-copilot-frontend:${TAG}" \
  -f ./frontend/Dockerfile.prod \
  --build-arg "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" \
  --build-arg "NEXT_PUBLIC_GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}" \
  --build-arg "NEXT_PUBLIC_GITHUB_REDIRECT_URI=${GITHUB_REDIRECT_URI}" \
  ./frontend

echo "Pushing to Docker Hub ..."
docker push "${DOCKERHUB_USER}/career-copilot-backend:${TAG}"
docker push "${DOCKERHUB_USER}/career-copilot-mcp:${TAG}"
docker push "${DOCKERHUB_USER}/career-copilot-livekit-agent:${TAG}"
docker push "${DOCKERHUB_USER}/career-copilot-frontend:${TAG}"

echo ""
echo "Done. On EC2 run:"
echo "  docker compose -f docker-compose.hub.yml pull"
echo "  docker compose -f docker-compose.hub.yml up -d"
