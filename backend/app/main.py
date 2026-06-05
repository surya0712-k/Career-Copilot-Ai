from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, auth, goals, interviews, profiles, progress, roadmaps
from app.config import get_settings
from app.db.session import engine
from app.memory.qdrant_client import ensure_collection
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_collection()
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="Career Copilot AI",
    description="Agentic career coach with memory",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(goals.router, prefix="/goals", tags=["goals"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(roadmaps.router, prefix="/roadmaps", tags=["roadmaps"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])


@app.get("/health")
async def health():
    return {"status": "ok"}
