"""[P4] Subgraph quanh 1 node — cho frontend cytoscape.js vẽ + tương tác.

GET /graph/subgraph?node=tncn2025-d7-k1&depth=2
  -> {center, nodes:[{id,label,label_vi,display,text,is_center}],
      edges:[{source,target,type,type_vi}]}

Dùng khi Q&A trích 1 điều luật: hiện ngữ cảnh graph nhỏ quanh nó (Điều cha,
Khoản/Điểm anh em, chế tài, nghĩa vụ, chủ thể, và điều luật cũ nó thay thế).
Data LUÔN từ Neo4j; frontend chỉ nhận JSON rồi vẽ + click-expand (gọi lại API).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.graph_source import get_source

router = APIRouter(tags=["graph"])

MAX_NODES = 40  # trần số node/lần để graph không loạn (Điều depth=2 có thể ~70)

# Nhãn tiếng Việt cho loại node + loại quan hệ (hiện lên cho người dùng doanh nghiệp)
_LABEL_VI = {
    "Article": "Điều", "Clause": "Khoản", "Point": "Điểm", "Subject": "Chủ thể",
    "Obligation": "Nghĩa vụ", "Right": "Quyền", "Prohibition": "Điều cấm",
    "Penalty": "Chế tài", "Deadline": "Thời hạn", "TaxBase": "Căn cứ thuế",
    "TaxRate": "Thuế suất", "Exemption": "Miễn trừ", "LegalDocument": "Văn bản",
}
_REL_VI = {
    "HAS_ARTICLE": "có điều", "HAS_CLAUSE": "có khoản", "HAS_POINT": "có điểm",
    "SUPERSEDED_BY": "được thay thế bởi", "REPLACES": "thay thế",
    "APPLIES_TO": "áp dụng cho", "IMPOSES": "áp dụng chế tài", "GRANTS": "trao quyền",
    "PROHIBITS": "cấm", "HAS_DEADLINE": "có thời hạn", "HAS_TAX_BASE": "căn cứ thuế",
    "HAS_TAX_RATE": "thuế suất", "HAS_EXEMPTION": "miễn trừ", "PENALIZES": "xử phạt",
}

# CHỈ đi theo quan hệ LUẬT. Nếu không lọc, subgraphAll bò sang REFERS_TO (Claim->luật)
# và CONTRADICTS (Misconception->luật) -> kéo hàng chục node dư luận vào, đè hết cấu
# trúc luật (graph Q&A "loạn"). Whitelist relationshipFilter chặn tại gốc.
_LAW_RELS = (
    "HAS_ARTICLE|HAS_CLAUSE|HAS_POINT|SUPERSEDED_BY|REPLACES|APPLIES_TO|IMPOSES|"
    "GRANTS|PROHIBITS|HAS_DEADLINE|HAS_TAX_BASE|HAS_TAX_RATE|HAS_EXEMPTION|PENALIZES"
)

# Cypher: coalesce các loại id khác nhau (point_id/clause_id/... ) về 1 khóa chung.
# Trả list comprehension để giữ label + type (record.data() strip Node/Rel object).
_CYPHER = """
MATCH (c)
WHERE c.point_id=$node OR c.clause_id=$node OR c.article_id=$node
   OR c.penalty_id=$node OR c.node_id=$node
CALL apoc.path.subgraphAll(c, {maxLevel:$depth, relationshipFilter:$relfilter})
YIELD nodes, relationships
RETURN
  [n IN nodes | {
     id: coalesce(n.point_id,n.clause_id,n.article_id,n.penalty_id,n.node_id,
                  n.normalized,n.name,toString(id(n))),
     label: labels(n)[0], number: n.number, letter: n.letter, name: n.name,
     doc_number: n.doc_number, text: n.text
  }] AS nodes,
  [r IN relationships | {
     source: coalesce(startNode(r).point_id,startNode(r).clause_id,startNode(r).article_id,
                      startNode(r).penalty_id,startNode(r).node_id,startNode(r).normalized,
                      startNode(r).name,toString(id(startNode(r)))),
     target: coalesce(endNode(r).point_id,endNode(r).clause_id,endNode(r).article_id,
                      endNode(r).penalty_id,endNode(r).node_id,endNode(r).normalized,
                      endNode(r).name,toString(id(endNode(r)))),
     type: type(r)
  }] AS edges
"""


def _display(row: dict) -> str:
    """Nhãn hiển thị ngắn tiếng Việt cho 1 node."""
    label = row.get("label")
    if label == "Article":
        return f"Điều {row.get('number', '')}".strip()
    if label == "Clause":
        return f"Khoản {row.get('number', '')}".strip()
    if label == "Point":
        return f"Điểm {row.get('letter', '')}".strip()
    if label == "Subject":
        return (row.get("name") or "Chủ thể")[:40]
    if label == "LegalDocument":
        return row.get("doc_number") or "Văn bản"
    return _LABEL_VI.get(label, label or "Node")


@router.get("/graph/subgraph")
def subgraph(
    node: str = Query(..., min_length=2, description="node_id trung tâm, vd tncn2025-d7-k1"),
    depth: int = Query(2, ge=1, le=3, description="số bậc hàng xóm (1-3)"),
) -> dict:
    """Subgraph quanh 1 node để cytoscape.js vẽ. Click-expand: gọi lại với node mới."""
    if get_source() != "neo4j":
        raise HTTPException(status_code=503, detail="Graph chưa sẵn sàng (Neo4j offline)")

    from backend.graph.connection import run  # noqa: WPS433

    rows = run(_CYPHER, node=node, depth=depth, relfilter=_LAW_RELS)
    if not rows or not rows[0].get("nodes"):
        raise HTTPException(status_code=404, detail=f"Không tìm thấy node {node!r} trong graph")

    # Cap số node để graph không loạn (Điều ở depth=2 có thể ~70 node). APOC trả BFS
    # nên node gần trung tâm đứng trước -> cắt phần xa. Luôn giữ node trung tâm.
    raw = rows[0]["nodes"]
    kept = raw[:MAX_NODES]
    kept_ids = {r["id"] for r in kept}
    if node not in kept_ids:
        center_row = next((r for r in raw if r["id"] == node), None)
        if center_row:
            kept.append(center_row)
            kept_ids.add(node)

    nodes = [
        {
            "id": r["id"],
            "label": r.get("label"),
            "label_vi": _LABEL_VI.get(r.get("label"), r.get("label")),
            "display": _display(r),
            "text": (r.get("text") or r.get("name") or "")[:400],
            "is_center": r["id"] == node,
        }
        for r in kept
    ]
    edges = [
        {"source": e["source"], "target": e["target"],
         "type": e["type"], "type_vi": _REL_VI.get(e["type"], e["type"])}
        for e in rows[0]["edges"]
        if e.get("source") in kept_ids and e.get("target") in kept_ids
    ]
    return {"center": node, "nodes": nodes, "edges": edges, "truncated": len(raw) > len(kept)}
