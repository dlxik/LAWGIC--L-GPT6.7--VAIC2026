"""[P4] API cho dashboard.

GET /trends              -> list[TrendAlert]  (canh bao hieu nham dang lan truyen)
GET /misconception/{id}  -> chi tiet + dieu luat bi hieu sai + post lien quan
GET /document/{id}/diff  -> thay doi so voi van ban cu (SUPERSEDED_BY)
GET /stats               -> so lieu tong quan cho trang chu

Cac endpoint tu chuyen giua mock <-> Neo4j nho graph_source.get_source().
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api import mock_data
from backend.api.graph_source import get_source

router = APIRouter(tags=["dashboard"])


@router.get("/stats")
def stats() -> dict:
    if get_source() == "mock":
        return mock_data.mock_stats()
    # TODO[P4]: 1 truy van Neo4j tra ve counts + generated_at + mode="neo4j"
    return mock_data.mock_stats() | {"mode": "neo4j-incomplete"}


@router.get("/trends")
def trends() -> list[dict]:
    """Sap xep theo severity roi velocity giam dan."""
    if get_source() == "mock":
        items = list(mock_data.MISCONCEPTIONS)
    else:
        # TODO[P4]: match (m:Misconception) return ... order by velocity desc
        items = list(mock_data.MISCONCEPTIONS)

    sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda m: (sev_rank.get(m["severity"], 3), -m["velocity"]))
    return items


@router.get("/misconception/{misc_id}")
def misconception_detail(misc_id: str) -> dict:
    for m in mock_data.MISCONCEPTIONS:
        if m["misconception_id"] == misc_id:
            contradicts = [
                mock_data.LEGAL_NODES[n]
                for n in m["contradicts"]
                if n in mock_data.LEGAL_NODES
            ]
            return {
                "misconception": m,
                "contradicts": contradicts,
                "posts": mock_data.POSTS_FOR_MISC.get(misc_id, []),
            }
    raise HTTPException(status_code=404, detail=f"misconception {misc_id!r} khong ton tai")


@router.get("/document/{doc_id}/diff")
def document_diff(doc_id: str) -> dict:
    if doc_id not in mock_data.DOCUMENTS:
        raise HTTPException(status_code=404, detail=f"document {doc_id!r} khong ton tai")

    diffs = mock_data.mock_diff(doc_id)
    enriched = []
    for d in diffs:
        enriched.append(
            {
                **d,
                "old_point": mock_data.LEGAL_NODES.get(d["old_point_id"]) if d["old_point_id"] else None,
                "new_point": mock_data.LEGAL_NODES.get(d["new_point_id"]) if d["new_point_id"] else None,
            }
        )
    return {
        "document": mock_data.DOCUMENTS[doc_id],
        "diffs": enriched,
    }
