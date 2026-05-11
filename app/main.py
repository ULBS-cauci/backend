from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

logger = logging.getLogger("uvicorn.error")

# Important: We must import all SQLModel schemas here so that SQLModel.metadata is fully populated 
# before we try to create the tables natively.
from schemas.course_schemas import Course
from schemas.user_schemas import User
from schemas.knowledge_schemas import FileEntity
from schemas.chat_schemas import ChatSession, Message, Attachment, SharedLink
from schemas.admin_schemas import SystemPrompt, LlmTip

from api.dependencies import _get_async_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI. 
    Code before 'yield' runs on application startup.
    Code after 'yield' runs on application shutdown.
    """
    logger.info("Starting up AI Tutor API...") 
    engine = _get_async_engine()
    
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        # run_sync is required because create_all is a synchronous SQLAlchemy function
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables initialized successfully.")
    
    yield
    
    # Optionally: Clean up engine on shutdown
    await engine.dispose()

# Import your routers here as you build them
# from app.api.routers import sessions, auth, files, admin
from app.api.routers import sessions

app = FastAPI(
    title="AI Tutor API",
    description="Backend API for the RAG-based AI Tutor system.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Tutor API is running. Go to /docs for Swagger UI."}


# Example of how you will attach routes later:
# app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
