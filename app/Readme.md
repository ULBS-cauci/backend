# AI Tutor Backend: Architectural Specification

## I. Architecture & System Flow
*What the application does, how data moves through the system, and its structural layout.*

### 1. Overview
This document outlines the architectural design, processing pipeline, and software engineering principles for a highly scalable, RAG-based AI Tutor. The system is designed to process university textbooks and notes, allowing students to prompt the chatbot for specific study outputs (quizzes, info cards, detailed explanations). 

The architecture prioritizes modularity, testability, and robust memory management over premature framework complexity (e.g., deferring LangGraph until non-linear agentic loops are strictly required).

### 2. The Prompt Processing Pipeline
When a user submits a prompt, the system executes the following linear flow orchestrated by the Business Logic (Service) layer:
* **A. Input Processing & Validation:** The API endpoint receives the user's query and requested output format. The system initializes a study session and fetches recent conversation history. Validating early ensures bad payloads don't waste compute.
* **B. Query Transformation & Conditional Routing:** The raw user query is first evaluated using a lightweight heuristic check(or a cheap classifier prompt or small model score, then fallback to heuristic only. Heuristic could miss more often.) to determine if it relies on previous chat context (e.g., checking for pronouns like "it" or "this"). If context resolution is required, the raw query and the chat history are passed to a QueryRewriter powered by a dedicated high-speed, low-cost model to minimize latency. It condenses the conversation into a highly specific, standalone search query, allowing the Vector DB to match accurately. If the query is entirely self-contained, the rewriter is bypassed entirely to save compute and reduce Time to First Token (TTFT), and the raw query is passed directly to the retrieval phase.
* **C. Hybrid Retrieval & Fusion Strategy:** The system executes a parallel retrieval process:
    * Semantic Search: The optimized query is embedded via the EmbeddingClient and sent to Qdrant to find conceptual matches.

    * Lexical Search (BM25): Simultaneously, the system performs a keyword-based search to capture exact terminology, acronyms, and unique identifiers.

    * Reciprocal Rank Fusion (RRF): The results from both searches—which use different scoring scales—are merged using the RRF algorithm. This normalizes the scores to create a single, prioritized list of the most relevant chunks.

    * (Optional) Cross-Encoder Re-ranking: To ensure maximum precision, the top-scoring fused results are passed through a Re-ranker model that evaluates the direct relationship between the query and each chunk, filtering out low-relevance noise.
* **D. Prompt Assembly (Dynamic Context):** The retrieved chunks are evaluated. If no relevant chunks are found, the system triggers the **"I don't know" fallback**, preventing hallucinations. If relevant chunks exist, a `ContextBuilder` formats the chunks and the requested output type into a final system prompt.  
>In the future, define strict retrieval thresholds and fallback tiers:
>1. high confidence: answer with citations
>2. medium confidence: answer with uncertainty + clarifying question
>3. low confidence: “I don’t know”
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

### 1. 100% Asynchronous I/O Execution

To allow high concurrency during slow network/LLM requests, blocking code is forbidden on the main thread.

* **Rule**: Every database query, network call, and file read/write MUST use async/await.
* **Enforcement**: Never use requests, use httpx or aiohttp. Never use time.sleep(), use asyncio.sleep(). DB operations must use async drivers (like asyncpg). Workloads that are heavily CPU-bound (like parsing giant PDFs) should be offloaded to workers/ or executed via asyncio.run_in_executor.

Code Example:

```python
# ❌ BAD: Blocking code (will freeze the FastAPI server)
import requests
def fetch_llm_response(prompt: str):
    return requests.post("https://api.openai.com/...", json={"prompt": prompt})

# ✅ GOOD: Async code (data_access/clients/llm_client.py)
import httpx
import asyncio

async def fetch_llm_response_async(prompt: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.openai.com/...", json={"prompt": prompt})
        return response.json()
```

    
### 2. Strict Dependency Injection (DI) via Interfaces

Hidden global states cause flakey tests and tightly coupled, brittle codebases. Furthermore, our business logic must never rely on specific vendor implementations (like Qdrant or OpenAI).

* **Rule**: Resource clients MUST be injected via Contract Interfaces (Abstract Base Classes), never as their concrete client types.
* **Enforcement**: Define the interface in data_access/interfaces/. Use FastAPI's Depends() in api/dependencies.py to yield the concrete implementation, but type-hint it as the interface in your Services. This makes it trivial to swap databases or inject mocks during pytest.

Code Example:

```Python
# 1. Define the Contract (data_access/interfaces/vector_db.py)
from abc import ABC, abstractmethod

class IVectorDB(ABC):
    @abstractmethod
    async def search(self, query_vector: list[float]) -> list[str]:
        pass

# 2. Concrete Implementation (data_access/clients/qdrant_client.py)
class QdrantRepository(IVectorDB):
    async def search(self, query_vector: list[float]) -> list[str]:
        # Qdrant specific SDK logic goes here
        return ["chunk 1", "chunk 2"]

# 3. Inject it (api/dependencies.py)
from fastapi import Depends

def get_vector_db() -> IVectorDB:
    # We yield the concrete class, but FastAPI treats it as the Interface
    return QdrantRepository() 

# 4. Use it decoupled (services/chat_service.py)
class ChatService:
    # Notice: The service knows NOTHING about Qdrant. 
    # It only knows it has an object that can .search()
    def __init__(self, vector_db: IVectorDB):
        self.vector_db = vector_db
```

### 3. Strict Type Hinting & Validation

Python is dynamic, but this codebase operates under strict type-checking assumptions to catch errors before runtime.

* **Rule**: All function signatures must include type hints for arguments and return types.
* **Enforcement**: Data traversing the API boundary (Input/Output) MUST be validated using Pydantic models located in schemas/. Do not pass raw dictionaries around the application.

Code Example:

```Python
# 1. Define the Schema (schemas/vector_schemas.py)
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    session_id: str
    query: str = Field(..., min_length=3, description="The student's question")
    output_type: str = Field(default="explanation")

# 2. Enforce it at the boundary (api/routers/sessions.py)
from fastapi import APIRouter
from schemas.vector_schemas import AskRequest

router = APIRouter()

# FastAPI automatically validates incoming JSON against AskRequest.
# If the user sends a query with 2 letters, FastAPI instantly returns a 422 Error.
@router.post("/{session_id}/ask")
async def ask_question(payload: AskRequest) -> dict:
    # We get IDE autocomplete: payload.session_id, payload.query
    return {"status": "processing", "query": payload.query}
```

### 4. The LangChain Boundary

LangChain is a powerful framework, but it is notoriously prone to "leaky abstractions" when used for database operations. It must be strictly confined to the AI Formatting Layer.

* **Rule**: LangChain is strictly reserved for Prompt Templating, LLM Abstraction, and JSON Parsing. It is explicitly forbidden to use LangChain for Vector Database operations (e.g., do not use QdrantVectorStore).
* **Why**: LangChain's generic retrieval interfaces break down the moment complex metadata filtering is required (e.g., filtering a search to a specific textbook chapter). Using the native qdrant-client SDK inside our custom repository preserves maximum performance and query control.

### 5. Database Lifecycle (Engine vs. Session)

Handling database connections improperly in an async framework will cause catastrophic thread crashes and data bleed between users.

* **Rule**: The Database Engine (Connection Pool) must be instantiated exactly once at application startup. The Database Session (Transaction Workspace) must be instantiated per-request via Dependency Injection.
* **Enforcement**: Never store a Session globally.

Code Example:

```Python
# 1. GLOBAL ENGINE (Created once in data_access/clients/relational_db_client.py)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db", pool_size=20)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# 2. PER-REQUEST SESSION (api/dependencies.py)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 6. Data Modeling with SQLModel

We use SQLModel instead of raw SQLAlchemy for our relational database.

* **What it is**: SQLModel is a library written by the creator of FastAPI. It combines standard SQLAlchemy (for database tables) with Pydantic (for API data validation) into a single tool.
* **Why we use it**: Normally, you have to write two identical classes: a User class for the database, and a UserSchema class for the API. SQLModel lets you write one class that does both, cutting boilerplate code in half. The sepparation is still posible by just omiting ```table=True``` in the definition of the class.

* **Rule**: All relational database tables and core API schemas must be defined using sqlmodel.SQLModel.

Code Example:

```Python
from sqlmodel import Field, SQLModel
from typing import Optional
from datetime import datetime

# 1. Base Model (For shared fields, optional but good practice)
class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: str
    is_active: bool = Field(default=True)

# 2. The Database Table (table=True makes it a database entity)
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str # We save this to the DB...

# 3. The API Schema / DTO (table=False by default)
class UserPublic(UserBase):
    id: int
    # Notice hashed_password is NOT here. 
    # FastAPI will use this to strip the password before sending JSON to the frontend!

# Let's make a Chat Session table
class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id") # Foreign key to the User table
    title: str = Field(min_length=3, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Usage in a router (It validates the incoming JSON automatically!)
@router.post("/sessions")
async def create_session(session_data: ChatSession, db: AsyncSession = Depends(get_db)):
    db.add(session_data)
    await db.commit()
    return session_data
```

Ideea for ```schemas/user_schemas.py```

```py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

# ---------------------------------------------------------
# 1. THE BASE (Shared fields - Never used directly)
# ---------------------------------------------------------
class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: str

# ---------------------------------------------------------
# 2. THE DB ENTITY (Strictly for the database layer)
#    Equivalent to Java @Entity
# ---------------------------------------------------------
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ---------------------------------------------------------
# 3. THE INPUT DTOs (What the user is allowed to send)
# ---------------------------------------------------------
class UserCreate(UserBase):
    # The user MUST send a raw password to register
    password: str 
    # Notice: No 'is_admin' field here! They cannot make themselves an admin.

class UserUpdate(SQLModel):
    # Everything is optional. They can update one or both.
    email: Optional[str] = None
    full_name: Optional[str] = None

# ---------------------------------------------------------
# 4. THE OUTPUT DTO (What the API is allowed to return)
# ---------------------------------------------------------
class UserPublic(UserBase):
    id: int
    created_at: datetime
    # Notice: No passwords here! Safe to send to the frontend.
```


## III. Recommendations for Future Enhancement
*Strategic improvements and features planned for near-term implementation.*

### 1. Production Readiness Roadmap
* **Observability & Tracing:** Integrate a tracing layer (e.g., LangSmith, Phoenix, or OpenTelemetry) to monitor chunk retrieval quality, prompt construction details, and exact token usage per request.
* **Ingestion Strategy:** Establish explicit document chunking strategies. Textbook structures require specific parsing (e.g., Markdown-aware or Semantic chunking) rather than basic recursive character splitting.
* **Continuous RAG Evaluation:** Establish an automated CI/CD evaluation pipeline (using tools like Ragas or TruLens) to regularly regression-test precision, recall, and AI faithfulness to the source material.
* **Rate Limiting & Abuse Prevention:** Implement robust rate-limiting at the `api/` layer (e.g., using Redis caching) to protect expensive LLM and Vector DB calls.
