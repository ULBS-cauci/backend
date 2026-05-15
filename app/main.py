from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

logger = logging.getLogger("uvicorn.error")

# Important: We must import all SQLModel schemas here so that SQLModel.metadata is fully populated 
# before we try to create the tables natively.
from app.schemas.course_schemas import Course
from app.schemas.user_schemas import User
from app.schemas.knowledge_schemas import Material
from app.schemas.chat_schemas import Conversation, Message, Attachment, SharedLink
from app.schemas.admin_schemas import SystemPrompt, LlmTip

from app.api.dependencies import _get_async_engine

from app.api.routers import files

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
from app.api.routers import course

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

app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(course.router, prefix="/api/v1/courses", tags=["Courses"])
