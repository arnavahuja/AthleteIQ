import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.data_pipeline.ingest import ingest_all
from backend.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ingest data + initialize RAG. Shutdown: cleanup."""
    # Phase 1: Ingest CSVs into SQLite (idempotent)
    if not os.path.exists(settings.db_path):
        print("Database not found. Running data ingestion...")
        ingest_all()
    else:
        print(f"Database already exists at {settings.db_path}")

    # Phase 2: Initialize RAG engine (will be wired in Phase 2)
    try:
        from backend.rag.retriever import initialize_rag
        await initialize_rag()
        print("RAG engine initialized.")
    except ImportError:
        print("RAG module not yet available, skipping initialization.")

    yield

    print("Shutting down.")


app = FastAPI(
    title="AthleteIQ",
    description="RAG-powered voice/text query system for athlete performance analytics",
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

app.include_router(router)

# Serve frontend static files in production
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve the React SPA for any non-API route."""
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
