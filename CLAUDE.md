# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Start infrastructure (run from `backend/`)
```bash
docker compose up -d qdrant postgres minio
```

### Run the API (dev, with auto-reload)
```bash
fastapi dev app/main.py
```

### Run without auto-reload
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Build the Ollama embedding model (once, ~8 GB download)
```bash
ollama create my-project-embed -f Modelfile
```

### Run integration tests (standalone scripts, not pytest)
```bash
python test/embedding/test_embedding.py
python test/minio/test_minio_client.py
python test/qdrant/test_qdrant_client.py
```

### Environment setup
```bash
cp .env.example .env   # then fill in real values
```

There is no linter config, no Makefile, and no CI pipeline in the repo. Tests are standalone scripts under `test/`, not a pytest suite — run them directly with `python`.

---

## Architecture

FastAPI RAG backend for an AI tutoring platform. Services: PostgreSQL (relational data), Qdrant (vector DB), MinIO (object storage), Ollama (local embeddings), OpenAI (LLM).

### Request flow

1. **Upload** (`POST /api/v1/files/upload`) — saves file to MinIO, creates `Material` record with `ingestion_status=pending`, returns immediately, submits background ingestion to `ThreadPoolExecutor`.
2. **Ingestion** (`app/workers/ingestion_worker.py`) — runs synchronously in a thread; creates its own event loop and DB engine. Pipeline: Docling → Markdown-aware text split → sparse (BGE-M3) + dense (Ollama) embeddings → RRF hybrid fusion → cross-encoder reranking → Qdrant upsert.
3. **Chat** (`POST /api/v1/sessions/ask`) — retrieves context via hybrid search, condenses multi-turn history via query rewrite, builds prompt, streams LLM response as SSE (`StreamingResponse` with async generator).

### Provider abstraction

Every pluggable layer (embedding, LLM, vector DB, sparse encoder, reranker, object storage, text splitter) follows the same pattern:
- Abstract base class in `app/data_access/interfaces/`
- Concrete client(s) in `app/data_access/clients/`
- Factory in `app/api/dependencies.py` keyed on a `*_CLIENT_TYPE` env var
- Swapping a provider only touches `dependencies.py` + `.env`

### Dependency injection

All clients are initialized in `app/api/dependencies.py` with `@lru_cache()` and wired into routes via FastAPI `Depends()`. The lifespan context in `main.py` owns startup pre-warming (BGE-M3, cross-encoder, Docling, MinIO bucket creation) and the `ThreadPoolExecutor` lifecycle.

### Database

SQLModel with async SQLAlchemy + asyncpg. Sessions are per-request, injected via `Depends(get_db_session)`, and auto-rolled back on exception. The background worker creates its own `AsyncEngine` with `NullPool` to avoid event loop conflicts.

All tables use UUID PKs and `created_at`/`updated_at` UTC timestamps. Schema is defined in SQLModel classes under `app/schemas/`; tables are created via `SQLModel.metadata.create_all()` on startup (no Alembic migrations).

### Key modules

| Path | Role |
|---|---|
| `app/api/dependencies.py` | Single source of truth for DI and client initialization |
| `app/core/config.py` | All settings (pydantic-settings), grouped by service |
| `app/services/chat_service.py` | RAG orchestration: retrieval, context building, streaming |
| `app/services/file_service.py` | Upload + background ingestion coordination |
| `app/workers/ingestion_worker.py` | Synchronous document processing pipeline |
| `app/rag_engine/` | Context retrieval, RRF fusion, query rewrite, output formatting |
| `app/data_access/interfaces/` | ABCs for all pluggable clients |

### Dev-mode stubs

`dependencies.py` falls back to fixed dummy UUIDs (`00000000-0000-0000-0000-000000000001` for user, `...0002` for course) when no auth/course context is provided, enabling local testing without a full auth flow.

### .env.example

Whenever a new environment variable is added, it must also be added to `.env.example` with a placeholder value and an inline comment marking it required or optional.
