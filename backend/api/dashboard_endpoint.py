"""[P4] API cho dashboard.

GET /trends              -> list[TrendAlert]  (canh bao hieu nham dang lan truyen)
GET /misconception/{id}  -> chi tiet + dieu luat bi hieu sai + post lien quan
GET /document/{id}/diff  -> thay doi so voi van ban cu (SUPERSEDED_BY)
GET /stats               -> so lieu tong quan cho trang chu

Cac endpoint tu chuyen giua mock <-> Neo4j nho graph_source.get_source().
Khi mock data khong con y nghia (P2 nap graph that), cac endpoint chay tren
Cypher va tra ve so lieu that. TODO cu da xoa.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.api import mock_data
from backend.api.graph_source import get_source

router = APIRouter(tags=["dashboard"])


# ---------------------------------------------------------------------------
# Helpers - Neo4j path
# ---------------------------------------------------------------------------


def _stats_from_neo4j() -> dict | None:
    """Counts tong quan qua CALL{} de moi count doc lap.

    LOI CU (Wave 4 audit): chuoi OPTIONAL MATCH... WITH...OPTIONAL MATCH... tao
    cartesian product o buoc cuoi, sum(mp.engagement) bi nhan len n_miscs lan.
    Sua: moi count trong 1 CALL{} rieng, gop lai o RETURN — Neo4j 5 hoat dong
    dung y muon voi CALL{} subquery.
    """
    try:
        from backend.graph.connection import run  # noqa: WPS433
        rows = run(
            """
            CALL { MATCH (d:LegalDocument) RETURN count(d) AS docs }
            CALL { MATCH (a:Article)       RETURN count(a) AS articles }
            CALL { MATCH (k:Clause)        RETURN count(k) AS clauses }
            CALL { MATCH (p:Point)         RETURN count(p) AS points }
            CALL { MATCH ()-[s:SUPERSEDED_BY]->() RETURN count(s) AS supersedes }
            CALL { MATCH (po:Post)         RETURN count(po) AS posts }
            CALL { MATCH (cl:Claim)        RETURN count(cl) AS claims }
            CALL { MATCH (m:Misconception) RETURN count(m) AS miscs }
            CALL {
                MATCH (mp:Post)-[:CONTAINS_CLAIM]->(:Claim)-[:INSTANCE_OF]->(:Misconception)
                RETURN coalesce(sum(mp.engagement), 0) AS total_engagement
            }
            RETURN docs, articles, clauses, points, supersedes,
                   posts, claims, miscs, total_engagement
            """,
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "documents": r.get("docs", 0),
            "articles": r.get("articles", 0),
            "clauses": r.get("clauses", 0),
            "points": r.get("points", 0),
            "supersedes_edges": r.get("supersedes", 0),
            "posts_analysed": r.get("posts", 0),
            "claims_extracted": r.get("claims", 0),
            "misconceptions_active": r.get("miscs", 0),
            "total_engagement_flagged": r.get("total_engagement", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "neo4j",
        }
    except Exception as e:
        print(f"[stats] Neo4j fail ({e.__class__.__name__}: {e})")
        return None


def _trends_from_neo4j() -> list[dict] | None:
    """Xep hang Misconception theo severity + velocity. None neu graph sap."""
    try:
        from backend.graph.connection import run  # noqa: WPS433
        rows = run(
            """
            MATCH (m:Misconception)
            // correction = correct_statement cua claim thanh vien tin cay nhat (KHONG
            // phai canonical_text — do la cau SAI). Lay cau dung nhat de dinh chinh.
            CALL {
                WITH m
                OPTIONAL MATCH (m)<-[:INSTANCE_OF]-(cc:Claim)
                WHERE cc.correct_statement IS NOT NULL AND cc.correct_statement <> ''
                RETURN cc.correct_statement AS correction
                ORDER BY cc.confidence DESC LIMIT 1
            }
            OPTIONAL MATCH (m)<-[:INSTANCE_OF]-(cl:Claim)<-[:CONTAINS_CLAIM]-(p:Post)
            OPTIONAL MATCH (m)-[:CONTRADICTS]->(target)
            WITH m, correction, count(DISTINCT cl) AS cnt,
                 coalesce(sum(p.engagement), 0) AS total_eng,
                 collect(DISTINCT coalesce(target.point_id, target.clause_id, target.article_id)) AS contradicts
            RETURN
                m.misconception_id AS misconception_id,
                m.canonical_text   AS canonical_text,
                correction AS correction,
                [c IN contradicts WHERE c IS NOT NULL] AS contradicts,
                toString(m.first_seen) AS first_seen,
                toString(m.last_seen)  AS last_seen,
                cnt AS count,
                total_eng AS total_engagement,
                CASE
                    WHEN total_eng >= 500 THEN 'HIGH'
                    WHEN total_eng >= 100 THEN 'MEDIUM'
                    ELSE 'LOW'
                END AS severity,
                CASE
                    WHEN m.last_seen IS NOT NULL AND m.first_seen IS NOT NULL
                        AND m.last_seen.epochSeconds > m.first_seen.epochSeconds
                    THEN toFloat(cnt) / (toFloat(m.last_seen.epochSeconds - m.first_seen.epochSeconds) / 3600.0)
                    ELSE 0.0
                END AS velocity
            ORDER BY total_eng DESC
            """,
        )
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[trends] Neo4j fail ({e.__class__.__name__}: {e})")
        return None


def _misconception_detail_from_neo4j(misc_id: str) -> dict | None:
    try:
        from backend.graph.connection import run  # noqa: WPS433
        m_rows = run("MATCH (m:Misconception {misconception_id:$id}) RETURN m", id=misc_id)
        if not m_rows:
            return None
        m = m_rows[0]["m"]
        contradicts_rows = run(
            """
            MATCH (m:Misconception {misconception_id:$id})-[:CONTRADICTS]->(t)
            RETURN
              coalesce(t.point_id, t.clause_id, t.article_id) AS node_id,
              labels(t)[0] AS node_label,
              t.text AS text
            """,
            id=misc_id,
        )
        posts_rows = run(
            """
            MATCH (m:Misconception {misconception_id:$id})<-[:INSTANCE_OF]-(:Claim)<-[:CONTAINS_CLAIM]-(p:Post)
            RETURN
              p.post_id AS post_id, p.platform AS platform, p.url AS url,
              p.author_hash AS author_hash, p.content AS content,
              toString(p.created_at) AS created_at, p.engagement AS engagement
            ORDER BY p.engagement DESC LIMIT 10
            """,
            id=misc_id,
        )
        # neo4j.time.DateTime (first_seen/last_seen) khong serialize JSON -> ep chuoi
        misc = {
            k: (str(v) if type(v).__module__.startswith("neo4j.time") else v)
            for k, v in dict(m).items()
        }
        # correction = correct_statement cua claim thanh vien tin cay nhat (khong phai
        # canonical_text = cau SAI). Thieu thi de trong, frontend an dong dinh chinh.
        corr_rows = run(
            """
            MATCH (m:Misconception {misconception_id:$id})<-[:INSTANCE_OF]-(c:Claim)
            WHERE c.correct_statement IS NOT NULL AND c.correct_statement <> ''
            RETURN c.correct_statement AS correction ORDER BY c.confidence DESC LIMIT 1
            """,
            id=misc_id,
        )
        misc["correction"] = corr_rows[0]["correction"] if corr_rows else ""
        return {
            "misconception": misc,
            "contradicts": contradicts_rows,
            "posts": posts_rows,
        }
    except Exception as e:
        print(f"[misc-detail] Neo4j fail ({e.__class__.__name__}: {e})")
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats")
def stats() -> dict:
    if get_source() == "neo4j":
        real = _stats_from_neo4j()
        if real is not None:
            return real
    return mock_data.mock_stats()


def _rescore_via_p3(items: list[dict]) -> list[dict]:
    """Neu P3's detect_trends co san, dung no de tinh lai velocity + severity.

    Feature-flagged. Neu import fail hoac ham crash, tra lai items nguyen ban.
    Frontend van doc severity/velocity/correction — trai nghiem khong doi.
    """
    try:
        from backend.discourse.misinformation import detect_trends  # noqa: WPS433
    except ImportError:
        return items
    try:
        alerts = detect_trends(items, as_of=None)
    except Exception as e:
        print(f"[trends] detect_trends fail ({e.__class__.__name__}: {e}) -> fallback")
        return items
    # detect_trends bo misconception vao key nested; giu shape phang cho frontend
    merged = []
    for a in alerts:
        m = a.get("misconception", {})
        # ƯU TIÊN correction THẬT từ Neo4j (correct_statement) hơn detect_trends
        # (no set = canonical_text = câu SAI). m tu _trends_from_neo4j da co correction dung.
        merged.append({**m, "velocity": a.get("velocity", 0), "severity": a.get("severity", "LOW"),
                       "correction": m.get("correction") or a.get("correction", "")})
    return merged or items


@router.get("/trends")
def trends() -> list[dict]:
    """Sap xep theo severity roi velocity giam dan."""
    if get_source() == "neo4j":
        real = _trends_from_neo4j()
        items = real if real is not None else list(mock_data.MISCONCEPTIONS)
    else:
        items = list(mock_data.MISCONCEPTIONS)

    items = _rescore_via_p3(items)

    sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda m: (sev_rank.get(m.get("severity"), 3), -m.get("velocity", 0)))
    return items


@router.get("/misconception/{misc_id}")
def misconception_detail(misc_id: str) -> dict:
    if get_source() == "neo4j":
        real = _misconception_detail_from_neo4j(misc_id)
        if real is not None:
            return real
        # fallthrough: mock co the co, hoac 404
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
    # Neo4j path: query SUPERSEDED_BY tu doc nay
    if get_source() == "neo4j":
        try:
            from backend.graph.connection import run  # noqa: WPS433
            doc_rows = run(
                "MATCH (d:LegalDocument {doc_id:$id}) RETURN d",
                id=doc_id,
            )
            if doc_rows:
                # neo4j.time.Date/DateTime khong serialize JSON duoc -> ep ve chuoi
                doc = {
                    k: (str(v) if type(v).__module__.startswith("neo4j.time") else v)
                    for k, v in dict(doc_rows[0]["d"]).items()
                }
                diff_rows = run(
                    """
                    MATCH (d:LegalDocument {doc_id:$id})-[:HAS_ARTICLE|HAS_CLAUSE|HAS_POINT*1..3]->(n)-[s:SUPERSEDED_BY]->(newn)
                    OPTIONAL MATCH (newd:LegalDocument)-[:HAS_ARTICLE|HAS_CLAUSE|HAS_POINT*1..3]->(newn)
                    WITH n, newn, s, d, newd
                    RETURN
                      coalesce(n.point_id, n.clause_id, n.article_id) AS old_point_id,
                      coalesce(newn.point_id, newn.clause_id, newn.article_id) AS new_point_id,
                      s.change_type AS change_type,
                      s.similarity  AS similarity,
                      toString(s.effective_from) AS effective_from,
                      '' AS summary,
                      { node_id: coalesce(n.point_id, n.clause_id, n.article_id),
                        node_label: labels(n)[0], text: n.text, doc_number: d.doc_number } AS old_point,
                      { node_id: coalesce(newn.point_id, newn.clause_id, newn.article_id),
                        node_label: labels(newn)[0], text: newn.text,
                        doc_number: coalesce(newd.doc_number, d.doc_number) } AS new_point
                    LIMIT 100
                    """,
                    id=doc_id,
                )
                return {"document": doc, "diffs": diff_rows}
        except Exception as e:
            print(f"[diff] Neo4j fail ({e.__class__.__name__}: {e}) -> mock fallback")

    # Mock path
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
