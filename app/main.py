from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.api.dependencies import _get_async_engine
from app.api.routers import files, chat

# Import your routers here as you build them
# from app.api.routers import sessions, auth, files, admin

app = FastAPI(
    title="AI Tutor API",
    description="Backend API for the RAG-based AI Tutor system.",
    version="1.0.0"
)

# Configure CORS (Critical for allowing your frontend to talk to the backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change this to your actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    """
    This block runs when the server starts.
    Automatically creates tables in Postgres (DocumentMetadata, ChatMessageEntity etc.)
    if they don't already exist.
    """
    engine = _get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Tutor API is running. Go to /docs for Swagger UI."}

# Example of how you will attach routes later:
# app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"]) 