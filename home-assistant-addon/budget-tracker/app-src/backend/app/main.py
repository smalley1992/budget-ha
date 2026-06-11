from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import ai_import, attachments, backups, budget_lines, categories, debts, income, months, savings, summary, users
from .services.common import seed_default_categories
from .services.migrations import ensure_user_profile_columns


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_user_profile_columns(engine)
    with SessionLocal() as db:
        seed_default_categories(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Budget Tracker API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(users.router)
    app.include_router(ai_import.router)
    app.include_router(backups.router)
    app.include_router(months.router)
    app.include_router(summary.router)
    app.include_router(categories.router)
    app.include_router(income.router)
    app.include_router(budget_lines.router)
    app.include_router(debts.router)
    app.include_router(savings.router)
    app.include_router(attachments.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    if settings.frontend_dist_dir and settings.frontend_dist_dir.exists():
        app.mount("/", StaticFiles(directory=settings.frontend_dist_dir, html=True), name="frontend")

    return app


app = create_app()
