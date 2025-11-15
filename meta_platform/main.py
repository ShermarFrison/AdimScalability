"""FastAPI entrypoint for the ADIM meta platform."""
from __future__ import annotations

from fastapi import FastAPI

from .app import models  # noqa: F401 - ensures models imported for metadata creation
from .app.database import Base, engine
from .app.routers import auth, otps, workspaces, provisioning

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ADIM Meta Platform", version="1.0.0")

app.include_router(auth.router, prefix="/api/auth")
app.include_router(workspaces.router, prefix="/api")
app.include_router(otps.router, prefix="/api")
app.include_router(provisioning.router, prefix="/api")


@app.get("/health/")
def health():
    return {"status": "ok"}
