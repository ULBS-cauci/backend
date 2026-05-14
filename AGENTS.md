# AI Tutor Backend - Agent Instructions

Welcome! This is a Python FastAPI application providing an AI Tutor backend using RAG (Retrieval-Augmented Generation).

## Key Documentation
Before writing or modifying code, please consult the relevant architectural documentation:
- **Architecture & System Flow:** [app/ARCHITECTURE.md](app/ARCHITECTURE.md) (RAG Pipeline, Hybrid Retrieval, Prompt Assembly, API Blueprint)
- **Database Schema:** [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)
- **Environment Setup:** [README.md](README.md)

## Tech Stack & Architecture
- **Framework:** FastAPI
- **Databases/Storage:** PostgreSQL, Qdrant (Vector DB), MinIO (Object Storage)
- **Architecture:** Layered design isolating components:
  - `app/api/`: Routing and endpoint mapping
  - `app/services/`: Core Business Logic
  - `app/data_access/`: External clients (MinIO, Qdrant, OpenAI, Embedding)
  - `app/rag_engine/`: Specific RAG algorithms (Fusion, Context Build, Query Rewrite)
  - `app/schemas/`: DB models and Pydantic validation

## Run & Test Commands
Most infrastructure is handled via Docker Compose.
- **Start infrastructure:** `docker compose up -d`
- **Stop infrastructure:** `docker compose stop`
- All `docker compose` commands should be run from the repository root (where `docker-compose.yml` lives).

## Agent Guidelines
1. **Link, don't embed:** Rely on the provided markdown files for deep architectural context.
2. **Framework complexity:** Keep architecture modular and testable. Ensure that changes inside RAG (e.g., query transformation) maintain the linear structure detailed in `app/ARCHITECTURE.md`.
3. **Dependencies:** Use the activated `.venv` for Python scripts and `pip`. Confirm updates in `requirements.txt`.
