from fastapi import FastAPI
from backend.routers import auth, system

app = FastAPI(title="ServerDash")
app.include_router(auth.router)
app.include_router(system.router)
