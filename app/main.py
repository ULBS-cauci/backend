import asyncio
from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

logger = logging.getLogger("uvicorn.error")

# Important: We must import all SQLModel schemas here so that SQLModel.metadata is fully
# populated before we try to create the tables natively.
from app.schemas.course_schemas import Course
from app.schemas.user_schemas import User, UserSetting
from app.schemas.knowledge_schemas import Material
from app.schemas.chat_schemas import Conversation, Message, Attachment, SharedLink, OutputFormat
from app.schemas.admin_schemas import SystemPrompt, LlmTip, TipCategory

from app.api.dependencies import (
    _get_async_engine,
    _get_bgem3_sparse_encoder,
    _get_cross_encoder_reranker,
    _get_docling_converter,
    _get_minio_client,
    create_ingestion_executor,
)
from app.core.config import MINIO_ATTACHMENTS_BUCKET, MINIO_MATERIALS_BUCKET


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AI Tutor API...")

    executor = create_ingestion_executor()
    app.state.executor = executor
    logger.info("Ingestion ThreadPoolExecutor started.")

    engine = _get_async_engine()
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables initialized.")

    logger.info("Pre-warming BGE-M3 sparse encoder (downloads model if not cached, ~570 MB)...")
    await asyncio.to_thread(_get_bgem3_sparse_encoder)
    logger.info("BGE-M3 sparse encoder ready.")

    logger.info("Pre-warming cross-encoder reranker (downloads model if not cached)...")
    await asyncio.to_thread(_get_cross_encoder_reranker)
    logger.info("Cross-encoder reranker ready.")

    logger.info("Pre-warming Docling DocumentConverter (OCR + layout models)...")
    await asyncio.to_thread(_get_docling_converter)
    logger.info("Docling DocumentConverter ready.")

    minio = _get_minio_client()
    await minio.connect()
    await minio.create_bucket(MINIO_MATERIALS_BUCKET)
    await minio.create_bucket(MINIO_ATTACHMENTS_BUCKET)
    logger.info("MinIO client connected.")

    try:
        yield
    finally:
        logger.info("Shutting down: waiting for in-flight ingestion tasks...")
        await asyncio.to_thread(executor.shutdown, True)
        logger.info("ThreadPoolExecutor shut down cleanly.")

        await minio.close()
        logger.info("MinIO client closed.")

        await engine.dispose()
        logger.info("Database engine disposed.")


from app.api.routers import sessions, course, user

app = FastAPI(
    title="AI Tutor API",
    description="Backend API for the RAG-based AI Tutor system.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(course.router,   prefix="/api/v1/courses",  tags=["Courses"])
app.include_router(user.router,     prefix="/api/v1/user",     tags=["User"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Tutor API is running. Go to /docs for Swagger UI."}
