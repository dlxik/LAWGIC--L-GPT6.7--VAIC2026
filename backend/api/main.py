"""[P4] FastAPI app. Chay: uvicorn backend.api.main:app --reload

Serve luon frontend tinh o /  -> mo http://localhost:8000/ la thay dashboard.
CORS mo cho * de dev khi mo file:// hay port khac. Prod thi siet lai.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import dashboard_endpoint, documents_endpoint, qa_endpoint
from backend.api.graph_source import get_source

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "frontend" / "static"

app = FastAPI(title="LAWGIC API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qa_endpoint.router)
app.include_router(dashboard_endpoint.router)
app.include_router(documents_endpoint.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "graph_source": get_source()}


# Mount dashboard cuoi cung de khong nuot cac API route o tren
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
