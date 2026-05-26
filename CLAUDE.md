# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

**Infrastructure (run first):**
```bash
docker compose up -d
```

**Ollama embedding model** (required for ingestion and search):
```bash
ollama create my-project-embed -f Modelfile
```

**API server:**
```bash
uvicorn app.main:app --reload
```
The first startup downloads ~1.1GB of ML models (BGE-M3 ~570MB + cross-encoder ~570MB) and runs `SQLModel.metadata.create_all()` to create database tables. There is no Alembic — schema changes that alter existing tables require manual SQL.

**ARQ background worker** (separate terminal, required for file ingestion):
```bash
arq app.workers.arq_worker.WorkerSettings
```
The worker maintains its own DB engine, Qdrant client, and MinIO client — separate from the API process. It must be restarted whenever `arq_worker.py` changes.

**Database seeder:**
```bash
python -m scripts.seed              # mock mode — Postgres only
python -m scripts.seed --reset      # wipe all tables then re-seed
python -m scripts.seed --embed      # embed real PDFs (needs all services running)
python -m scripts.seed --dry-run    # preview without writing
```

**Integration tests** (no pytest, run directly):
```bash
python -m test.qdrant.test_qdrant_client
python -m test.minio.test_minio_client
python -m test.embedding.test_embedding
```

## Architecture

### Dependency injection pattern

`app/api/dependencies.py` is the IoC container for the whole application. The pattern has two layers:

- `@lru_cache` private functions (e.g., `_get_qdrant_client`) — instantiate and cache concrete clients as singletons
- Public non-cached wrappers (e.g., `get_vector_db_client`) — read the `*_CLIENT_TYPE` env var and call the appropriate private factory, returning the interface type

Services (`ChatService`, `FileService`, `CourseService`) depend only on interfaces (`VectorDBInterface`, `EmbeddingInterface`, etc.), never on concrete clients. Adding a new provider means adding a new `_get_*` factory and a branch in the public wrapper — nothing else changes.

### ARQ pool lifecycle

The ARQ Redis pool is created during the FastAPI lifespan and stored on `app.state.arq_pool`. The `get_arq_pool` dependency reads it from `request.app.state`. Do not use a module-level global for it.

### Authentication (dev stub)

`get_current_user()` in `dependencies.py` returns a hardcoded dummy `User` — there is no real JWT auth yet. `app/core/security.py` and `app/api/routers/auth.py` are empty stubs. The hardcoded user UUID is `00000000-0000-0000-0000-000000000001` and must match the seed data.

### RAG pipeline (ChatService)

`ask_stream` in `chat_service.py` runs this sequence:
1. Condense follow-up query using chat history (LLM call via `query_rewrite.py`)
2. Parallel dense search (Ollama embeddings → Qdrant) + sparse search (BGE-M3 → Qdrant)
3. Merge results with Reciprocal Rank Fusion (`rag_engine/fusion.py`)
4. Re-rank fused results with cross-encoder (`CrossEncoderReranker`)
5. Build system prompt with retrieved context
6. Stream LLM response (OpenAI-compatible)
7. Persist both user message and AI response to DB

### File ingestion pipeline

`POST /api/v1/files/upload` → `FileService.upload_and_index`:
1. Validates PDF, uploads bytes to MinIO
2. Creates `Material` DB record with `ingestion_status=PENDING`
3. Enqueues `process_pdf_task` on ARQ

ARQ worker `process_pdf_task`:
1. Downloads PDF from MinIO
2. Extracts text with `pypdf` (runs in `asyncio.to_thread`)
3. Splits with `LangChainRecursiveSplitterClient`
4. Embeds with Ollama
5. Upserts dense vectors to Qdrant (`QDRANT_MATERIALS_COLLECTION = "university_library"`)
6. Updates `Material.ingestion_status` to `COMPLETED` or `FAILED`

The worker stores `material.vector_namespace` on success so `CourseService.delete_course()` knows which Qdrant collection to clean up.

### Config system

All configuration is in `app/core/config.py` as separate `BaseSettings` subclasses (`QdrantSettings`, `MinIOSettings`, `PostgresSettings`, etc.). Each reads from `.env` (or environment variables). Module-level constants `MATERIALS_BUCKET` and `QDRANT_MATERIALS_COLLECTION` are the single source of truth for storage names — use them instead of string literals.
