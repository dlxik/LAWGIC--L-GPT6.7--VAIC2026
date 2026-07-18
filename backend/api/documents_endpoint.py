"""[P4] Backend cho van ban goc.

  GET /documents                   -> list metadata + entity/node counts
  GET /documents/{doc_id}          -> chi tiet 1 van ban (them so lieu tu graph)
  GET /documents/{doc_id}/file     -> tai file goc (.docx tu data/raw/legal_docs/)

Ly do khong dung MinIO: 3 file van ban dem lai 137KB, gitignore da mo cho
data/raw/legal_docs (`!qlt*.docx`), FastAPI stream len HTTP truc tiep. MinIO
them 1 service, 1 bucket, 1 SDK, 1 presigned-URL flow — cho zero user-benefit
so voi 1 endpoint stream file. Neu sau nay can upload van ban moi tu UI thi
moi doi sang MinIO/S3.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.api import mock_data
from backend.api.graph_source import get_source
from backend.core.config import get_settings

router = APIRouter(tags=["documents"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _list_from_neo4j() -> list[dict] | None:
    """Query graph tra ve metadata + counts. None neu Neo4j not ready."""
    if get_source() != "neo4j":
        return None
    try:
        from backend.graph.connection import run  # noqa: WPS433
        rows = run(
            """
            MATCH (d:LegalDocument)
            OPTIONAL MATCH (d)-[:HAS_ARTICLE]->(a:Article)
            OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(k:Clause)
            OPTIONAL MATCH (k)-[:HAS_POINT]->(p:Point)
            WITH d, count(DISTINCT a) AS n_articles,
                 count(DISTINCT k) AS n_clauses,
                 count(DISTINCT p) AS n_points
            RETURN
              d.doc_id       AS doc_id,
              d.doc_number   AS doc_number,
              d.title        AS title,
              d.issuer       AS issuer,
              toString(d.issued_date)    AS issued_date,
              toString(d.effective_date) AS effective_date,
              d.status       AS status,
              d.source_url   AS source_url,
              n_articles, n_clauses, n_points
            ORDER BY d.effective_date DESC
            """,
        )
        return [dict(r) for r in rows]
    except Exception as e:  # driver down, timeout, ...
        print(f"[documents] Neo4j query fail ({e.__class__.__name__}: {e})")
        return None


def _list_from_mock() -> list[dict]:
    out = []
    for doc_id, doc in mock_data.DOCUMENTS.items():
        n_nodes = sum(1 for n in mock_data.LEGAL_NODES.values() if n["doc_id"] == doc_id)
        out.append({**doc, "n_articles": 0, "n_clauses": 0, "n_points": n_nodes, "n_nodes": n_nodes})
    return out


import re as _re

_DOC_ID_RE = _re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _resolve_file(doc_id: str) -> Path | None:
    """Tra Path .docx neu ton tai. Chap nhan 3 vi tri de dev + prod.

    An toan chong path-traversal 2 lop:
      1. doc_id phai match _DOC_ID_RE (khong co dau '/', '..', ky tu la)
      2. Path.resolve() sau do is_relative_to base — chan symlink escape
    Cuoi cung .is_file() kiem tra file that su ton tai va la file (khong phai
    dir/symlink to noi khac).
    """
    if not _DOC_ID_RE.match(doc_id):
        return None
    base = get_settings().raw_legal_dir.resolve()
    for suffix in (".docx", ".pdf"):
        candidate = (base / f"{doc_id}{suffix}").resolve()
        try:
            if not candidate.is_relative_to(base):
                continue
        except AttributeError:  # Python <3.9 fallback (khong dung nhung an toan)
            if not str(candidate).startswith(str(base) + "/"):
                continue
        if candidate.is_file():
            return candidate
    return None


@router.get("/documents")
def list_documents() -> dict:
    """Danh sach 3 van ban trong he thong. Kem file_available de UI biet co
    file de tai hay khong (thuong 3 van ban thue duoc build tu .docx)."""
    docs = _list_from_neo4j() or _list_from_mock()
    for d in docs:
        d["file_available"] = _resolve_file(d["doc_id"]) is not None
    return {
        "total": len(docs),
        "documents": docs,
        "source": get_source(),
    }


@router.get("/documents/{doc_id}")
def get_document(doc_id: str) -> dict:
    docs = _list_from_neo4j() or _list_from_mock()
    for d in docs:
        if d["doc_id"] == doc_id:
            return {**d, "file_available": _resolve_file(doc_id) is not None}
    raise HTTPException(status_code=404, detail=f"document {doc_id!r} khong ton tai")


@router.get("/documents/{doc_id}/file")
def download_document(doc_id: str) -> FileResponse:
    """Stream van ban goc. Content-Disposition: attachment de trinh duyet mo
    thanh download thay vi in-browser render. Client-side co the tuy y attach
    ?inline=1 sau nay neu can preview."""
    path = _resolve_file(doc_id)
    if not path:
        raise HTTPException(
            status_code=404,
            detail=f"file goc cho {doc_id!r} chua co trong data/raw/legal_docs/",
        )
    media_type = _DOCX_MIME if path.suffix == ".docx" else "application/pdf"
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )
