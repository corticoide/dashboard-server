import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import auth, system
from backend.config import settings

app = FastAPI(title="ServerDash", docs_url="/api/docs", redoc_url=None)

app.include_router(auth.router)
app.include_router(system.router)

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
