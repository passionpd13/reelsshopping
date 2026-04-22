from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, products, projects, scripts, sources
from app.core.db import init_db
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Shopping Reels Generator", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
    app.include_router(products.router, prefix="/api/products", tags=["products"])
    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(scripts.router, prefix="/api/scripts", tags=["scripts"])

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    return app


app = create_app()
