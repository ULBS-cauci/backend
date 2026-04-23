# AI Tutor Backend: Architectural Specification

## I. Architecture & System Flow
*What the application does, how data moves through the system, and its structural layout.*

### 1. Overview
This document outlines the architectural design, processing pipeline, and software engineering principles for a highly scalable, RAG-based AI Tutor. The system is designed to process university textbooks and notes, allowing students to prompt the chatbot for specific study outputs (quizzes, info cards, detailed explanations). 

The architecture prioritizes modularity, testability, and robust memory management over premature framework complexity (e.g., deferring LangGraph until non-linear agentic loops are strictly required).

### 2. The Prompt Processing Pipeline
When a user submits a prompt, the system executes the following linear flow orchestrated by the Business Logic (Service) layer:
* **A. Input Processing & Validation:** The API endpoint receives the user's query and requested output format. The system initializes a study session and fetches recent conversation history. Validating early ensures bad payloads don't waste compute.
* **B. Query Transformation:** The raw user query and the chat history are passed to a `QueryRewriter`. It condenses the conversation into a highly specific, standalone search query, allowing the Vector DB to match accurately.
* **C. Advanced Retrieval Strategy:** The optimized query is embedded and sent to Qdrant. The retrieval phase uses a mix of Semantic (Vector) and Lexical (BM25) search.
* **D. Prompt Assembly (Dynamic Context):** The retrieved chunks are evaluated. If no relevant chunks are found, the system triggers the **"I don't know" fallback**, preventing hallucinations. If relevant chunks exist, a `ContextBuilder` formats the chunks and the requested output type into a final system prompt.
* **E. Generation & Streaming:** The assembled prompt is sent to the LLM. The response is yielded asynchronously and streamed back to the client via Server-Sent Events (SSE).

### 3. Chat History & Memory Management
Memory is split into two distinct mechanisms to balance context-awareness with token economy:
* **A. Storage (Keep Everything):** Every user interaction is saved into a PostgreSQL `chat_messages` table, tied to a unique `session_id` for analytics and fine-tuning.
* **B. Injection (The Sliding Window):** Only the $N$ most recent messages are retrieved, measured via a token counter, and injected into the LLM prompt to prevent context limits being exceeded.

### 4. RESTful API Blueprint
The application exposes a standard RESTful API. Endpoints are grouped by domain noun.
* **A. Authentication & Users (`/auth`, `/users`):** Handles identity and preferences.
* **B. Chat Sessions (`/sessions`):** Manages the study history and core AI interactions (Includes the Core RAG `/ask` endpoint).
* **C. Knowledge Base & Files (`/files`):** Manages ingestion of textbooks/notes into the vector database.
* **D. System Configuration (`/admin`):** Allows dynamic adjustment of AI behavior.

### 5. Scalable Folder Structure
To support the modular REST API and background file processing, the fully-expanded directory structure is designed as follows (excluding implicit namespace items):

```text
app/
├── main.py                     # Application entry point & FastAPI instance
├── api/                        # Controllers (HTTP layer)
│   ├── dependencies.py         # FastAPI Depends() definitions (Auth, DB session)
│   └── routers/                # Modular API grouping
│       ├── admin.py            
│       ├── auth.py             
│       ├── files.py            
│       └── sessions.py         
├── clients/                    # Infrastructure / Data Access Layer
│   ├── db_client.py            # PostgreSQL connection pool
│   ├── llm_client.py           # Text Generation wrapper (LLM SDKs)
│   ├── qdrant_client.py        # Vector DB operations
│   └── storage_client.py       # S3/Local file storage wrapper
├── core/                       # App-Wide Configuration & Cross-Cutting Concerns
│   ├── config.py               # Pydantic BaseSettings for Env vars
│   ├── exceptions.py           # Custom Error definitions
│   └── security.py             # JWT hashing and validation logic
├── models/                     # SQLAlchemy/SQLModel classes (Database tables)
├── rag_engine/                 # Domain Logic (AI Operations)
│   ├── context_builder.py      # Combines query and retrieved chunks into prompt
│   ├── output_formatter.py     # Structures LLM output into JSON/Quiz format
│   └── query_rewrite.py        # Condenses chat history into standalone queries
├── schemas/                    # Pydantic classes (API Request/Response validation)
├── services/                   # Business Logic Orchestration
│   ├── auth_service.py         
│   ├── chat_service.py         # Ties together routers <-> rag_engine <-> clients
│   └── file_service.py         
└── workers/                    # Background Tasks
    └── ingestion_worker.py     # Heavy lifting: PDF parsing, chunking, and embedding
```

---

## II. Developer Rules & Standards
*Mandatory engineering principles and constraints for anyone contributing to the codebase.*

### 1. N-Tier Architecture (Separation of Concerns)
Code must enforce strict boundaries between layers. 
* **Routers (`api/`):** Only handle HTTP requests, input validation, and HTTP responses. Do not put business logic or database queries here.
* **Services (`services/`):** Handle business logic and process orchestration. Services should NOT return `HTTPException` or know anything about HTTP status codes. They should raise custom domain exceptions (defined in `core/exceptions.py`).
* **Clients (`clients/`):** Solely responsible for external I/O (Database, API, File System). They should not contain application business logic.

### 2. 100% Asynchronous I/O Execution
To allow high concurrency during slow network/LLM requests, blocking code is forbidden on the main thread.
* **Rule:** Every database query, network call, and file read/write MUST use `async`/`await`.
* **Enforcement:** Never use `requests`, use `httpx` or `aiohttp`. Never use `time.sleep()`, use `asyncio.sleep()`. DB operations must use async drivers (like `asyncpg`). Workloads that are heavily CPU-bound (like parsing giant PDFs) should be offloaded to `workers/` or executed via `asyncio.run_in_executor`.

### 3. Strict Dependency Injection (DI)
Hidden global states cause flakey tests and unpredictable bugs.
* **Rule:** Resource clients (e.g., Qdrant connection, PostgreSQL session, LLM client) MUST be injected into services and routers.
* **Enforcement:** Use FastAPI's `Depends()` at the router level, and pass those dependencies down to the service functions as arguments. Never instantiate a DB connection or LLM client deep inside a function body. This makes it trivial to override dependencies with mock versions during `pytest` execution.

### 4. Strict Type Hinting & Validation
Python is dynamic, but this codebase operates under strict type-checking assumptions.
* **Rule:** All function signatures must include type hints for arguments and return types.
* **Enforcement:** Data traversing the API boundary (Input/Output) MUST be validated using Pydantic models located in `schemas/`. Data mapped to the database MUST use models located in `models/`.

---

## III. Recommendations for Future Enhancement
*Strategic improvements and features planned for near-term implementation.*

### 1. Production Readiness Roadmap
* **Observability & Tracing:** Integrate a tracing layer (e.g., LangSmith, Phoenix, or OpenTelemetry) to monitor chunk retrieval quality, prompt construction details, and exact token usage per request.
* **Ingestion Strategy:** Establish explicit document chunking strategies. Textbook structures require specific parsing (e.g., Markdown-aware or Semantic chunking) rather than basic recursive character splitting.
* **Continuous RAG Evaluation:** Establish an automated CI/CD evaluation pipeline (using tools like Ragas or TruLens) to regularly regression-test precision, recall, and AI faithfulness to the source material.
* **Rate Limiting & Abuse Prevention:** Implement robust rate-limiting at the `api/` layer (e.g., using Redis caching) to protect expensive LLM and Vector DB calls.
