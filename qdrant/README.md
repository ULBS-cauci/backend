# Qdrant Local Setup Guide

This guide shows you how to run a local Qdrant database using Docker Compose.

## What You Are Setting Up

Qdrant is a vector database. In this project, it runs as a Docker container and exposes an HTTP API on port `6333`.

The Compose file used is:

- `docker-compose.yml`

## Prerequisites

You need all of the following:

1. Docker installed and running.
2. Docker Compose available (`docker compose` command).
3. Internet access for first run (to pull the image).
4. Port `6333` free on your machine.

## Install Dependencies (Linux, macOS, Windows)

This section helps you install everything needed before running Qdrant locally.

Official Docker docs (index):

- https://docs.docker.com/get-started/get-docker/

### Linux

Official Linux install docs:

- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Docker Engine on Debian: https://docs.docker.com/engine/install/debian/
- Docker Engine on Fedora: https://docs.docker.com/engine/install/fedora/
- Linux post-install steps (docker group/non-root): https://docs.docker.com/engine/install/linux-postinstall/
- Docker Compose plugin (Linux): https://docs.docker.com/compose/install/linux/

#### Option A: Ubuntu
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	$(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Add your user to Docker group (so you can run Docker without sudo), then re-login:

```bash
sudo usermod -aG docker $USER
```


### macOS

Official macOS install docs:

- Docker Desktop for Mac: https://docs.docker.com/desktop/setup/install/mac-install/

1. Install Docker Desktop:
	 - Download from the official Docker website.
2. Open Docker Desktop once and wait until it shows as running.
3. If prompted, approve required system permissions.

Optional Homebrew install:

```bash
brew install --cask docker
```

### Windows

Official Windows install docs:

- Docker Desktop for Windows: https://docs.docker.com/desktop/setup/install/windows-install/
- WSL install guide (Microsoft): https://learn.microsoft.com/windows/wsl/install

1. Install Docker Desktop for Windows from the official Docker website.
2. During setup, keep WSL2 integration enabled (recommended).
3. Restart machine if installer asks.
4. Open Docker Desktop and wait until engine is running.

Notes:

- Windows Home should use WSL2 backend.
- You can run project commands in PowerShell, Command Prompt, or WSL terminal.

### Verify Installation (All OS)

Run:

```bash
docker --version
docker compose version
docker info
```

Expected:

- Version commands print installed versions.
- `docker info` returns engine details without errors.

If these commands fail, fix Docker installation first, then continue with the next steps below.

## 1) Open Terminal in This Folder

From project root:

```bash
cd backend/qdrant
```

## 2) Configure the API Key

Open `docker-compose.yml` and set your own local api key:

```yaml
QDRANT__SERVICE__API_KEY=<set_your_api_key>
```

Replace `<set_your_api_key>` with a real value, for example:

```yaml
QDRANT__SERVICE__API_KEY=my_local_dev_key_123
```

Important:

- Do not commit real secrets.
- If this is only local development, use a temporary key.

## 2.1) Configure App Environment Variables (Local vs Production)

Your Python app reads these variables from `.env`:

- `QDRANT_HOST`
- `QDRANT_PORT`
- `QDRANT_SERVICE_API_KEY`

Use values based on where Qdrant is running.

### Local development (Docker on your machine)

```env
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_SERVICE_API_KEY=your_api_key_variable_from_docker_compose
```

### Production deployment

```env
QDRANT_HOST=
QDRANT_PORT=
QDRANT_SERVICE_API_KEY=
(Ask for .env.production)
```

Notes:

- Keep `QDRANT_HOST` as `localhost` only for local development.
- For production, use full `https://...` URL.
- Keep production secrets outside git (secret manager, CI/CD env vars, or host-level env injection).

## 3) Start Qdrant

Run:

```bash
docker compose up -d
```

What this does:

- Downloads `qdrant/qdrant:latest` (first run only).
- Starts container `qdrant_db`.
- Maps local port `6333` to container port `6333`.
- Creates/uses local folder `qdrant_data` for persistent storage.

## 4) Check Container Status

```bash
docker compose ps
```

You should see service `qdrant` as `Up`.

## 5) Verify Qdrant API Is Reachable

Because API key is enabled, include it in requests.

### Health check

```bash
curl -H "api-key: my_local_dev_key_123" http://localhost:6333/healthz
```

Expected response:

```json
{"title":"ok"}
```

### Cluster/collections info

```bash
curl -H "api-key: my_local_dev_key_123" http://localhost:6333/collections
```

If you get JSON back, Qdrant is running correctly.

## 6) View Logs (If Needed)

```bash
docker compose logs -f qdrant
```

Press `Ctrl + C` to stop log streaming.

## 7) Stop / Restart

Stop container:

```bash
docker compose down
```

Start again:

```bash
docker compose up -d
```

Data remains because of volume mapping:

- `./qdrant_data:/qdrant/storage`

## 8) Reset Local Data (Danger)

If you want a clean database, stop and remove local data:

```bash
docker compose down
rm -rf qdrant_data
docker compose up -d
```

This permanently deletes local vectors and collections.

## Common Problems and Fixes

### Port 6333 already in use

Symptom: container fails to start.

Fix options:

1. Stop the process using `6333`.
2. Or change mapping in `docker-compose.yml`, for example:

```yaml
ports:
	- "6334:6333"
```

Then call API on `http://localhost:6334`.

### Unauthorized / missing API key

Symptom: HTTP `401` or `403`.

Fix:

- Confirm `QDRANT__SERVICE__API_KEY` in compose file.
- Use exactly the same key in request header:

```bash
-H "api-key: <your_key>"
```

### Docker command not found

Install Docker Desktop (Windows/macOS) or Docker Engine + Compose plugin (Linux), then retry.

### Container exits immediately

Check logs:

```bash
docker compose logs qdrant
```

## Useful Day-to-Day Commands

Start in background:

```bash
docker compose up -d
```

See running services:

```bash
docker compose ps
```

Follow logs:

```bash
docker compose logs -f qdrant
```

Stop and remove container:

```bash
docker compose down
```

## Quick Success Checklist

- Docker is running.
- `docker compose up -d` finishes without errors.
- `docker compose ps` shows `qdrant` as `Up`.
- `curl` to `/healthz` with API key returns `ok`.

If all 4 are true, your local Qdrant deployment is ready.
