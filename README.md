# Backend Setup Guide

This folder contains the Python backend setup and dependency workflow.


## Prerequisites

- Git
- Python 3.10+ (recommended)
- pip (comes with Python)
- Docker + Docker Compose (for Qdrant, MinIO, PostgreSQL)

### Install Docker

- **Ubuntu:**
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
sudo usermod -aG docker $USER   # then re-login
```

- **macOS:** Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) or `brew install --cask docker`.
- **Windows:** Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) with WSL2 backend enabled.

Verify:

```bash
docker --version
docker compose version
```

### Useful Docker Commands

> All `docker compose` commands must be run from the `backend/` directory, where `docker-compose.yml` lives.

These apply to any service (`qdrant`, `postgres`, `minio`):

| Action | Command |
|---|---|
| Start a service | `docker compose up -d <service>` |
| Stop a service | `docker compose stop <service>` |
| Stop + delete container | `docker compose down <service>` |
| Stop + delete container & data | `docker compose down <service> -v` |
| View logs | `docker compose logs <service>` |
| Start all services | `docker compose up -d` |
| Stop all services | `docker compose down` |

## 1) Clone the Project

- git clone `<YOUR_REPOSITORY_URL>`
- cd ULBS-coach/backend

## 2) Create and Activate a Virtual Environment

Run these commands inside the `backend` folder.

### Linux

- python3 -m venv .venv
- source .venv/bin/activate
- python -m pip install --upgrade pip
- pip install -r requirements.txt

### macOS

- python3 -m venv .venv
- source .venv/bin/activate
- python -m pip install --upgrade pip
- pip install -r requirements.txt

### Windows (PowerShell)

- py -m venv .venv
- .\.venv\Scripts\Activate.ps1
- python -m pip install --upgrade pip
- pip install -r requirements.txt

If PowerShell blocks activation, run this once in PowerShell as Administrator:

Set-ExecutionPolicy RemoteSigned

### Windows (Command Prompt)

- py -m venv .venv
- .venv\Scripts\activate.bat
- python -m pip install --upgrade pip
- pip install -r requirements.txt

## 3) Environment Variables (.env)

Create your local `.env` from `.env.example`.

### Linux/macOS

cp .env.example .env

### Windows (PowerShell)

Copy-Item .env.example .env

Then edit (ask teammates for production .env) `.env` and set real values (remove `#` and spaces around `=`).


## Keep .env.example Updated (Important)

Whenever you add a new environment variable in code:

1. Add it to `.env.example`.
2. Keep values empty or placeholder-only (never commit secrets).
3. Add a short inline comment explaining the variable.
4. Mention whether it is required or optional.

---

> **Before starting any container:** all `docker compose` commands read credentials from `.env`. Complete step 3 above and set the service .env variables before running any service.

## Service: Qdrant (Vector Database)

Qdrant stores and searches document chunk embeddings. It runs as a Docker container on port `6333`.

### Environment Variables

```env
VECTOR_DB_CLIENT_TYPE=qdrant
VECTOR_DB_ENDPOINT=http://localhost:6333
# VECTOR_DB_API_KEY=your_key   # optional — only if you enable authentication
```

> **API key (optional for local dev):** By default the compose file runs Qdrant without authentication. To enable it, uncomment the `QDRANT__SERVICE__API_KEY` block in `docker-compose.yml` and add `VECTOR_DB_API_KEY=your_key` to your `.env`.

### Step 1 — Start the container

```bash
docker compose up -d qdrant
```

### Step 2 — Verify it's running

```bash
docker ps | grep qdrant_db
```

You should see `qdrant_db` with status `Up`.

### Step 3 — Verify the connection

```bash
curl http://localhost:6333/healthz
# Expected: healthz check passed
```

Dashboard: `http://localhost:6333/dashboard`

### Reset Local Data

```bash
docker compose down
rm -rf data/qdrant_data
docker compose up -d qdrant
```
---

## Service: PostgreSQL (Relational Database)

PostgreSQL stores user data, session metadata, and chat history. It runs as a Docker container on port `5432`.

### Environment Variables

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change_me
POSTGRES_DB=postgres_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

> **Note on `POSTGRES_HOST`:** Always use `localhost` in your `.env` for local development — FastAPI runs natively (not inside Docker), so it connects to the container via the published port. The hostname `postgres` only works when FastAPI itself runs inside the Docker network (e.g. production).

### Step 1 — Start the container

```bash
docker compose up -d postgres
```

### Step 2 — Verify it's running

```bash
docker ps | grep postgres_db
```

You should see `postgres_db` with status `Up`.

### Step 3 — Verify the connection

Requires `postgresql-client` requirement:

```bash
PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT 1;"
```

A result of `1` means the server is accepting connections.

### Step 4 — Check for tables

```bash
PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt"
```

This will be empty until SQLModel migrations run.

### Reset Local Data

```bash
docker compose down
rm -rf data/postgres_data
docker compose up -d postgres
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| Port 5432 in use | Stop the conflicting process, or change `POSTGRES_PORT` in `.env` (e.g. `5433`) |
| Variables not picked up | Ensure `.env` is in the same folder as `docker-compose.yml` with no `.txt` extension |
| `psql: command not found` | `sudo apt install postgresql-client` |

---

## Service: MinIO (Object Storage)

MinIO stores the original uploaded files (PDFs, notes) as S3-compatible object storage. It runs as a Docker container on ports `9000` (S3 API) and `9001` (web console).

### Environment Variables

```env
OBJECT_STORAGE_CLIENT_TYPE=minio
MINIO_ENDPOINT=http://localhost:9000
MINIO_USER=user               # MinIO root username
MINIO_PASSWORD=change_me      # MinIO root password (keep secret!)
MINIO_USE_SSL=false           # true only for production TLS
```

### Step 1 — Start the container

```bash
docker compose up -d minio
```

### Step 2 — Verify it's running

```bash
docker ps | grep minio_storage
```

You should see `minio_storage` with status `Up`.

### Step 3 — Verify the connection

```bash
curl -o /dev/null -w "%{http_code}\n" http://localhost:9000/minio/health/live
# Expected: 200
```

Web console: `http://localhost:9001` — log in with the `MINIO_USER` / `MINIO_PASSWORD` values from your `.env`.

### Reset Local Data

```bash
docker compose down
rm -rf data/minio_data
docker compose up -d minio
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| Port 9000/9001 in use | Stop the conflicting process, or change the port mapping in `docker-compose.yml` |
| Console login fails | Confirm `MINIO_USER` and `MINIO_PASSWORD` in `.env` match what was set when the container was first created. If they differ, reset local data (above). |

---

## Service: Ollama (Embedding Model)

Ollama runs the Qwen3-Embedding-4B model locally and exposes it over HTTP on port `11434`. It runs **natively** (not in Docker) so each team member gets full hardware acceleration — Apple Metal on Mac, NVIDIA CUDA on GPU laptops, or CPU fallback — without cross-platform driver issues.

> **Production note:** The university server deployment will use an Ollama Docker container. Local development always uses native Ollama.

### 1. Install Ollama

Download and install from [ollama.com](https://ollama.com/).

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

After installation, make sure the service is running:
- **macOS / Windows:** launch the Ollama app from your Applications folder or Start menu. You should see the Ollama icon in the system tray.
- **Linux:** `sudo systemctl start ollama`

### 2. Build the Model

We pin the exact model weights and quantization using a `Modelfile` (analogous to a `Dockerfile`). The file is already at `embedding/Modelfile`:

```dockerfile
FROM hf.co/Qwen/Qwen3-Embedding-4B-GGUF:Q8_0
```

Run this once from the `backend/` directory:

```bash
ollama create my-project-embed -f embedding/Modelfile
```

This downloads the model from Hugging Face (~8 GB on first run) and tags it locally as `my-project-embed`.

### 3. Environment Variables

```env
EMBEDDING_CLIENT_TYPE=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_EMBED_MODEL=my-project-embed
```

### 4. Test the Embedding

```bash
python test/embedding/test_embedding.py
```

Expected output: embedding vectors (2560 dimensions each) and semantic similarity scores — high for related sentences, low for unrelated ones.

---

## Service: OpenAI (LLM)

The LLM layer generates the final answers. It is abstracted behind `LLMInterface` so the provider can be swapped (e.g., Anthropic, Ollama) without changing anything outside `dependencies.py`.

### Environment Variables

```env
LLM_CLIENT_TYPE=openai
OPENAI_API_KEY=sk-proj-...
```

### Installation

The `openai` package is included in `requirements.txt`. No extra steps beyond the standard venv setup.

### Switching Providers

To use a different LLM provider:

1. Implement a new client that extends `LLMInterface` (`app/data_access/interfaces/llm.py`).
2. Add the required env vars to `config.py` and `.env.example`.
3. Add an `if/else` branch in `dependencies.py` keyed on `LLM_CLIENT_TYPE`.

Nothing outside `dependencies.py` changes.

---

## Run the API

Once all services are up and `.env` is filled in, start the FastAPI dev server from `backend/`:

```bash
source .venv/bin/activate   # if not already active
fastapi dev app/main.py
```

The server starts with auto-reload on file changes. Swagger UI is available at `http://localhost:8000/docs`.

To run without auto-reload (closer to production):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```