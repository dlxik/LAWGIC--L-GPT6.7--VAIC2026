"""[P4] FastAPI app. Chay: uvicorn backend.api.main:app --reload"""

from fastapi import FastAPI

app = FastAPI(title="LAWGIC API", version="0.1.0")

# TODO[P4]: include_router(qa_endpoint.router)
# TODO[P4]: include_router(dashboard_endpoint.router)
# TODO[P4]: mount frontend/static


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
