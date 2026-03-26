import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import auth, system, services
from backend.routers.files import router as files_router
from backend.routers.scripts import router as scripts_router
from backend.routers.crontab import router as crontab_router
from backend.config import settings
from backend.database import engine, Base
import backend.models.script  # ensure script tables are registered  # noqa: F401

app = FastAPI(title="ServerDash", docs_url="/api/docs", redoc_url=None)

# Create tables that don't exist yet (non-destructive)
Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(system.router)
app.include_router(services.router)
app.include_router(files_router)
app.include_router(scripts_router)
app.include_router(crontab_router)

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
