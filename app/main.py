import logging

from fastapi import FastAPI

from app.api.routes import auth, notifications, ops, projects, tasks
from app.core.metrics import MetricsMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="TaskFlow API", version="0.1.0")
    app.add_middleware(MetricsMiddleware)

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(notifications.router)
    app.include_router(ops.router)
    return app


app = create_app()
