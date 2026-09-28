"""
AI for Controls — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import health, auth, policies, audit, control_runs, approvals



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup: ensure tables exist (Alembic is preferred for production)
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="AI for Controls",
    description="AI-powered Policy Control Automation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(policies.router)
app.include_router(audit.router)
app.include_router(control_runs.router)
app.include_router(approvals.router)


