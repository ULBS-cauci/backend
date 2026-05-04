from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "AI Tutor API is running. Go to /docs for Swagger UI."}

# Example of how you will attach routes later:
# app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
