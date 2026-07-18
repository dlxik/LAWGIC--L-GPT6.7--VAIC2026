"""[P4] FastAPI app. Chay: uvicorn backend.api.main:app --reload

Serve luon frontend tinh o /  -> mo http://localhost:8000/ la thay dashboard.
CORS mo cho * de dev khi mo file:// hay port khac. Prod thi siet lai.

Lifespan:
  Khi Neo4j online -> chay apply_schema() idempotent lan boot dau. Loader du
  lieu (load_processed) van la 1-shot script — khong tu chay khi API start
  vi ton thoi gian va can cli tuong tac. Xem README '3. Nap graph' de biet
  cach chay.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import (
    dashboard_endpoint,
    documents_endpoint,
    graph_endpoint,
    law_endpoint,
    qa_endpoint,
    ratelimit,
)
from backend.api.graph_source import get_source

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """apply_schema idempotent len boot dau — CHI khi Neo4j da song.

    Neo4j driver mac dinh retry ket noi ~30s (Transaction retry loop). Neu goi
    thang apply_schema khi Neo4j tat, uvicorn treo may chuc giay truoc khi
    binding cong 8000. Fail-fast: healthcheck() bao voi timeout ngan, KHONG
    dat -> bo qua. get_source() ben dashboard/qa endpoint tu re-probe sau.
    """
    try:
        from backend.graph.connection import get_driver, healthcheck  # noqa: WPS433
        try:
            get_driver().verify_connectivity()  # sync, timeout 30s default nhung network tra loi ngay
        except Exception:
            print("[lifespan] Neo4j offline — skip apply_schema (endpoint tu re-probe sau)")
            yield
            return
        if healthcheck():
            from backend.graph.schema import apply_schema  # noqa: WPS433
            apply_schema()
            print("[lifespan] apply_schema OK")
    except NotImplementedError:
        print("[lifespan] apply_schema chua san sang — skip")
    except Exception as e:
        print(f"[lifespan] boot task fail ({e.__class__.__name__}: {e}) — skip")
    yield


app = FastAPI(title="LAWGIC API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit theo IP truoc khi router dispatch — chan curl bypass client-side quota
app.middleware("http")(ratelimit.middleware)

app.include_router(qa_endpoint.router)
app.include_router(dashboard_endpoint.router)
app.include_router(documents_endpoint.router)
app.include_router(graph_endpoint.router)
app.include_router(law_endpoint.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "graph_source": get_source()}


# Mount dashboard cuoi cung de khong nuot cac API route o tren
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
