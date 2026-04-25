# AI Tutor Backend: Architectural Specification

## I. Architecture & System Flow
*What the application does, how data moves through the system, and its structural layout.*

### 1. Overview
This document outlines the architectural design, processing pipeline, and software engineering principles for a highly scalable, RAG-based AI Tutor. The system is designed to process university textbooks and notes, allowing students to prompt the chatbot for specific study outputs (quizzes, info cards, detailed explanations). 

The architecture prioritizes modularity, testability, and robust memory management over premature framework complexity (e.g., deferring LangGraph until non-linear agentic loops are strictly required).

### 2. The Prompt Processing Pipeline
When a user submits a prompt, the system executes the following linear flow orchestrated by the Business Logic (Service) layer:
* **A. Input Processing & Validation:** The API endpoint receives the user's query and requested output format. The system initializes a study session and fetches recent conversation history. Validating early ensures bad payloads don't waste compute.
* **B. Query Transformation & Conditional Routing:** The raw user query is first evaluated using a lightweight heuristic check to determine if it relies on previous chat context (e.g., checking for pronouns like "it" or "this"). If context resolution is required, the raw query and the chat history are passed to a QueryRewriter powered by a dedicated high-speed, low-cost model to minimize latency. It condenses the conversation into a highly specific, standalone search query, allowing the Vector DB to match accurately. If the query is entirely self-contained, the rewriter is bypassed entirely to save compute and reduce Time to First Token (TTFT), and the raw query is passed directly to the retrieval phase.
* **C. Hybrid Retrieval & Fusion Strategy:** The system executes a parallel retrieval process:
    * Semantic Search: The optimized query is embedded via the EmbeddingClient and sent to Qdrant to find conceptual matches.

    * Lexical Search (BM25): Simultaneously, the system performs a keyword-based search to capture exact terminology, acronyms, and unique identifiers.

    * Reciprocal Rank Fusion (RRF): The results from both searches—which use different scoring scales—are merged using the RRF algorithm. This normalizes the scores to create a single, prioritized list of the most relevant chunks.

    * (Optional) Cross-Encoder Re-ranking: To ensure maximum precision, the top-scoring fused results are passed through a Re-ranker model that evaluates the direct relationship between the query and each chunk, filtering out low-relevance noise.
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
To support the modular REST API and background file processing, the current directory structure is:

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
├── data_access/                # Infrastructure / Data Access Layer
│   ├── clients/                # Concrete adapters to external systems
│   │   ├── relational_db_client.py # PostgreSQL connection pool
│   │   ├── llm_client.py       # Text generation wrapper (LLM SDKs)
│   │   ├── embedding_client.py # Connector to embedding model
│   │   ├── qdrant_client.py    # Vector DB operations
│   │   └── object_storage_client.py # S3/local file storage wrapper
│   └── interfaces/             # Contracts for swappable implementations
│       └── vector_db.py
├── core/                       # App-Wide Configuration & Cross-Cutting Concerns
│   ├── config.py               # Pydantic BaseSettings for Env vars
│   ├── exceptions.py           # Custom Error definitions
│   └── security.py             # JWT hashing and validation logic
├── rag_engine/                 # Domain Logic (AI Operations)
│   ├── fusion.py               # Logic for Reciprocal Rank Fusion (RRF)
│   ├── context_builder.py      # Combines query and retrieved chunks into prompt
│   ├── output_formatter.py     # Structures LLM output into JSON/Quiz format
│   └── query_rewrite.py        # Condenses chat history into standalone queries
├── schemas/                    # Pydantic classes (domain/API validation)
│   └── vector_schemas.py
├── services/                   # Business Logic Orchestration
│   ├── auth_service.py         
│   ├── chat_service.py         # Ties together routers <-> rag_engine <-> data_access
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
* **Clients (`data_access/clients/`):** Solely responsible for external I/O (Database, API, File System). They should not contain application business logic.

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
* **Enforcement:** Data traversing the API boundary (Input/Output) MUST be validated using Pydantic models located in `schemas/`.

---

## III. Recommendations for Future Enhancement
*Strategic improvements and features planned for near-term implementation.*

### 1. Production Readiness Roadmap
* **Observability & Tracing:** Integrate a tracing layer (e.g., LangSmith, Phoenix, or OpenTelemetry) to monitor chunk retrieval quality, prompt construction details, and exact token usage per request.
* **Ingestion Strategy:** Establish explicit document chunking strategies. Textbook structures require specific parsing (e.g., Markdown-aware or Semantic chunking) rather than basic recursive character splitting.
* **Continuous RAG Evaluation:** Establish an automated CI/CD evaluation pipeline (using tools like Ragas or TruLens) to regularly regression-test precision, recall, and AI faithfulness to the source material.
* **Rate Limiting & Abuse Prevention:** Implement robust rate-limiting at the `api/` layer (e.g., using Redis caching) to protect expensive LLM and Vector DB calls.
