# Build and push all Career Copilot images to Docker Hub.
# Usage (from repo root):
#   1. Copy .env and set DOCKERHUB_USER, NEXT_PUBLIC_API_URL, GITHUB_REDIRECT_URI, GITHUB_CLIENT_ID
#   2. docker login
#   3. .\scripts\dockerhub-push.ps1

$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot ".." ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found. Copy .env.example to .env and configure it."
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$user = $env:DOCKERHUB_USER
if (-not $user) {
    Write-Error "Set DOCKERHUB_USER in .env (your Docker Hub username)."
}

$tag = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "latest" }
$apiUrl = $env:NEXT_PUBLIC_API_URL
$redirectUri = $env:GITHUB_REDIRECT_URI
$ghClient = $env:GITHUB_CLIENT_ID

if (-not $apiUrl -or -not $redirectUri -or -not $ghClient) {
    Write-Error "Set NEXT_PUBLIC_API_URL, GITHUB_REDIRECT_URI, and GITHUB_CLIENT_ID in .env before building frontend."
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "Building images as ${user} tag ${tag} ..."

docker build -t "${user}/career-copilot-backend:${tag}" "$root\backend"
docker build -t "${user}/career-copilot-mcp:${tag}" -f "$root\backend\Dockerfile.mcp" "$root\backend"
docker build -t "${user}/career-copilot-livekit-agent:${tag}" "$root\livekit-agent"
docker build -t "${user}/career-copilot-frontend:${tag}" `
    -f "$root\frontend\Dockerfile.prod" `
    --build-arg "NEXT_PUBLIC_API_URL=$apiUrl" `
    --build-arg "NEXT_PUBLIC_GITHUB_CLIENT_ID=$ghClient" `
    --build-arg "NEXT_PUBLIC_GITHUB_REDIRECT_URI=$redirectUri" `
    "$root\frontend"

Write-Host "Pushing to Docker Hub ..."
docker push "${user}/career-copilot-backend:${tag}"
docker push "${user}/career-copilot-mcp:${tag}"
docker push "${user}/career-copilot-livekit-agent:${tag}"
docker push "${user}/career-copilot-frontend:${tag}"

Write-Host ""
Write-Host "Done. Images published:"
Write-Host "  ${user}/career-copilot-backend:${tag}"
Write-Host "  ${user}/career-copilot-mcp:${tag}"
Write-Host "  ${user}/career-copilot-livekit-agent:${tag}"
Write-Host "  ${user}/career-copilot-frontend:${tag}"
Write-Host ""
Write-Host "On EC2: copy .env + docker-compose.hub.yml, then run:"
Write-Host "  docker compose -f docker-compose.hub.yml pull"
Write-Host "  docker compose -f docker-compose.hub.yml up -d"
