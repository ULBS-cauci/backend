# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

RAG-based AI Tutor backend built with FastAPI. Professors upload PDFs (stored in MinIO, chunked and embedded into Qdrant); students ask questions that trigger semantic retrieval and a streaming LLM response via OpenAI. PostgreSQL stores users, courses, conversations, and messages.

## Running the Project

**Infrastructure (Docker)** — run from `backend/`:
```bash
docker compose up -d              # start Qdrant, MinIO, PostgreSQL
docker compose down               # stop all
docker compose logs <service>     # qdrant | minio | postgres
```

**Ollama embedding model** — runs natively (not in Docker):
```bash
ollama create my-project-embed -f Modelfile   # one-time setup (~8 GB download)
sudo systemctl start ollama                    # Linux; Mac/Windows: launch app
```

**FastAPI dev server**:
```bash
source .venv/bin/activate
fastapi dev app/main.py            # auto-reload, Swagger at http://localhost:8000/docs
```

**Environment**:
```bash
cp .env.example .env   # then fill in real values
```
All required variables are documented in `.env.example`. `ENVIRONMENT=dev` is the only supported value right now.

## Running Tests

Tests are integration scripts (not pytest) and must be run from `backend/` so `.env` is found:

```bash
python test/qdrant/test_qdrant_client.py    # requires live Qdrant
python test/minio/test_minio_client.py      # requires live MinIO
python test/embedding/test_embedding.py     # uses sentence-transformers (own requirements)
```

The embedding test has its own `requirements.txt` at `test/embedding/requirements.txt`.

## Architecture

### Request Flow

```
Router → Service → data_access/interfaces (ABC) → data_access/clients (concrete)
```

Routers handle HTTP only. Services orchestrate business logic. All external systems are accessed exclusively through Abstract Base Classes in `data_access/interfaces/` — services never import concrete clients directly.

### IoC Container (`api/dependencies.py`)

This is the single source of truth for dependency wiring:

- **`@lru_cache()` functions** (`_get_qdrant_client`, `_get_async_engine`, `_get_ollama_embedding_client`, etc.) create connection pools **once per application lifecycle**.
- **Provider selector functions** (`get_vector_db_client`, `get_llm_client`, etc.) read `*_CLIENT_TYPE` env vars and return the cached concrete client typed as the interface.
- **`get_db_session()`** yields a fresh `AsyncSession` per request (never cached).
- **Service factories** (`get_chat_service`, `get_file_service`, `get_course_service`) assemble services by injecting interface-typed clients.

When adding a new external client: implement the interface, add `@lru_cache()` factory and provider function in `dependencies.py`, update `config.py` and `.env.example`.

### Data Access Interfaces

| Interface | Concrete clients |
|---|---|
| `VectorDBInterface` | `QdrantClient` |
| `EmbeddingInterface` | `OllamaEmbeddingClient` |
| `LLMInterface` | `OpenAILLMClient` |
| `ObjectStorageInterface` | `MinIOClient` |

PostgreSQL is the one exception — it uses `AsyncSession` directly (no interface), injected via `get_db_session()`.

### Database Schema (SQLModel)

Tables are auto-created at startup via `SQLModel.metadata.create_all()` in `main.py`'s lifespan. There is no migration tool (no Alembic). All SQLModel table classes **must be imported in `main.py`** before startup runs, or their tables won't be created.

Schema pattern per entity:
```
<Entity>Base (shared fields) → <Entity> (table=True, DB entity) → <Entity>Create / <Entity>Update (input DTOs) → <Entity>Public (output DTO, strips sensitive fields)
```

### Background Workers

CPU-heavy PDF work (extraction, chunking) in `workers/ingestion_worker.py` is synchronous and runs via `asyncio.to_thread()` in `FileService` to avoid blocking the event loop.

### RAG Engine

`rag_engine/` contains stubs for `fusion.py`, `context_builder.py`, `query_rewrite.py`, and `output_formatter.py` — these are not yet implemented. The current `ChatService.ask_stream()` does a direct semantic-only search against the hardcoded `"university_library"` Qdrant collection.

### Authentication

Auth is not implemented. In `ENVIRONMENT=dev`, `get_current_user()` auto-creates and returns a hardcoded dummy user (`00000000-0000-0000-0000-000000000001`). Non-dev environments return HTTP 501. Several routers also have hardcoded IDs as temporary dev stubs (e.g., `HARDCODED_TEACHER_ID` in `course.py`, hardcoded `course_id`/`user_id` in `files.py`).

## Coding Rules

**Async I/O is mandatory.** Never use `requests`, `time.sleep()`, or synchronous DB calls on the main thread. Use `httpx`/`ollama.AsyncClient`, `asyncio.sleep()`, `asyncpg`. CPU-bound work goes in `workers/` and is called via `asyncio.to_thread()`.

**No global clients.** All network/DB client instantiation happens inside `@lru_cache()` functions in `dependencies.py`. Never initialize clients inside routers or services.

**LangChain is restricted** to prompt templating, LLM abstraction, and output parsers only. Do not use `LangChain VectorStores` (e.g., `QdrantVectorStore`) — use the native `qdrant-client` SDK via `VectorDBInterface`.

**Schemas for all cross-layer data.** Use or create Pydantic/SQLModel models in `schemas/`. Never pass raw dicts across API or service boundaries.

**Documentation parity.** When adding a new dependency, `.env` variable, or external service: update `requirements.txt`, `README.md`/`app/ARCHITECTURE.md`, and `.env.example` simultaneously.

## Naming Conventions

- Interfaces: `<Name>Interface` (e.g., `VectorDBInterface`) in files named `<service_name>.py`
- Clients: `<ServiceName>Client` (e.g., `OllamaEmbeddingClient`) in files named `<service_name>_client.py`
- Provider selector env vars: `<INTERFACE>_CLIENT_TYPE` (e.g., `EMBEDDING_CLIENT_TYPE`)
- Service-scoped env vars: `<SERVICE>_*` (e.g., `OLLAMA_HOST`, `OLLAMA_EMBED_MODEL`)

## Formatter

Black is the project formatter. Use the Black VS Code extension set as the default Python formatter.
