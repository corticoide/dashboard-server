import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.limiter import limiter
from backend.middleware.security import SecurityHeadersMiddleware
from backend.routers import auth, system, services
from backend.routers.files import router as files_router
from backend.routers.scripts import router as scripts_router
from backend.routers.crontab import router as crontab_router
from backend.routers.logs import router as logs_router
from backend.routers.metrics_history import router as metrics_history_router
from backend.routers.admin import router as admin_router
from backend.config import settings
from backend.database import engine, Base
from backend.core.logging import init_logging
from backend.core.health import router as health_router
import backend.models.script  # ensure script tables are registered  # noqa: F401
import backend.models.execution_log  # ensure execution_logs table is registered  # noqa: F401
import backend.models.metrics_snapshot  # ensure metrics_snapshots table is registered  # noqa: F401
import backend.models.permission  # ensure permissions table is registered  # noqa: F401

init_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.scheduler import init_scheduler, shutdown_scheduler
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="ServerDash", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Sudo-Password"],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# GZIP compression
app.add_middleware(GZipMiddleware, minimum_size=500)

# Create tables that don't exist yet (non-destructive)
Base.metadata.create_all(bind=engine)

app.include_router(health_router)
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(services.router)
app.include_router(files_router)
app.include_router(scripts_router)
app.include_router(crontab_router)
app.include_router(logs_router)
app.include_router(metrics_history_router)
app.include_router(admin_router)

# Serve Vue SPA (built files)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        index = os.path.join(static_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.port,
        ssl_certfile=settings.cert_file,
        ssl_keyfile=settings.key_file,
        reload=True,
    )
