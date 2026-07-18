"""[P2] Nạp JSON đã cấu trúc hoá vào Neo4j.

Hai quy tắc bất di bất dịch:
  1. MERGE theo id, không CREATE. Nạp lại N lần ra cùng một graph.
  2. Không SET text của Point đã tồn tại. Sửa luật = Point mới + đóng
     effective_to của Point cũ + nối SUPERSEDED_BY (xem diffing.py).

Ngày tháng phải chuyển sang kiểu date() của Neo4j, không để string —
nếu để string thì query time-travel so sánh theo thứ tự chữ cái, sai âm thầm.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.graph import connection

# ---------------------------------------------------------------------------
# Cypher
# ---------------------------------------------------------------------------

_MERGE_DOC = """
MERGE (d:LegalDocument {doc_id: $doc_id})
SET d.doc_number = $doc_number,
    d.title = $title,
    d.issuer = $issuer,
    d.issued_date = date($issued_date),
    d.effective_date = date($effective_date),
    d.expiry_date = CASE WHEN $expiry_date IS NULL THEN NULL ELSE date($expiry_date) END,
    d.status = $status,
    d.source_url = $source_url
"""

_MERGE_ARTICLE = """
MATCH (d:LegalDocument {doc_id: $doc_id})
MERGE (a:Article {article_id: $article_id})
SET a.number = $number,
    a.heading = $heading,
    a.text = $text,
    a.effective_from = date($effective_from),
    a.effective_to = CASE WHEN $effective_to IS NULL THEN NULL ELSE date($effective_to) END
MERGE (d)-[:HAS_ARTICLE]->(a)
"""

_MERGE_CLAUSE = """
MATCH (a:Article {article_id: $article_id})
MERGE (k:Clause {clause_id: $clause_id})
SET k.number = $number,
    k.text = $text,
    k.effective_from = date($effective_from),
    k.effective_to = CASE WHEN $effective_to IS NULL THEN NULL ELSE date($effective_to) END
MERGE (a)-[:HAS_CLAUSE]->(k)
"""

_MERGE_POINT = """
MATCH (k:Clause {clause_id: $clause_id})
MERGE (p:Point {point_id: $point_id})
SET p.letter = $letter,
    p.text = $text,
    p.effective_from = date($effective_from),
    p.effective_to = CASE WHEN $effective_to IS NULL THEN NULL ELSE date($effective_to) END
MERGE (k)-[:HAS_POINT]->(p)
"""

_MERGE_DOC_REL = """
MATCH (new:LegalDocument {doc_id: $new_doc_id})
MATCH (old:LegalDocument {doc_id: $old_doc_id})
MERGE (new)-[:%s]->(old)
"""

# Entity — dùng label riêng cho Obligation/Right/Prohibition (quyết định #4).
# Phần tử thứ 3 = prefix id DUY NHẤT: không dùng field[:3] vì tax_rates/tax_base
# đều ra "tax" -> trùng entity_id -> MERGE đè node -> mất nửa dữ liệu thuế (P1 báo).
_ENTITY_REL = {
    "obligations":  ("Obligation",  "IMPOSES",       "obl"),
    "rights":       ("Right",        "GRANTS",        "rig"),
    "prohibitions": ("Prohibition",  "PROHIBITS",     "pro"),
    "deadlines":    ("Deadline",     "HAS_DEADLINE",  "dea"),
    "tax_rates":    ("TaxRate",      "HAS_TAX_RATE",  "txr"),   # đặc thù luật thuế (P1)
    "tax_base":     ("TaxBase",      "HAS_TAX_BASE",  "txb"),
    "exemptions":   ("Exemption",    "HAS_EXEMPTION", "exm"),
}

# Chủ thể (APPLIES_TO) chỉ gắn cho entity có "người chịu tác động" thật sự.
# Thuế suất / căn cứ tính thuế không áp cho ai cụ thể -> bỏ, giữ APPLIES_TO sạch.
_NO_SUBJECT_FIELDS = {"tax_rates", "tax_base"}

_MERGE_ENTITY = """
MATCH (n) WHERE n.point_id = $node_id OR n.clause_id = $node_id OR n.article_id = $node_id
MERGE (e:%s {node_id: $entity_id})
SET e.text = $text
MERGE (n)-[:%s]->(e)
"""

_MERGE_SUBJECT = """
MATCH (e {node_id: $entity_id})
MERGE (s:Subject {normalized: $normalized})
SET s.name = $name
MERGE (e)-[:APPLIES_TO]->(s)
"""

_MERGE_PENALTY = """
MATCH (n) WHERE n.point_id = $node_id OR n.clause_id = $node_id OR n.article_id = $node_id
MERGE (pen:Penalty {penalty_id: $penalty_id})
SET pen.type = $type,
    pen.min_amount = $min_amount,
    pen.max_amount = $max_amount,
    pen.duration_months = $duration_months,
    pen.is_permanent = $is_permanent,
    pen.text = $text
MERGE (n)-[:PENALIZES]->(pen)
"""

_MERGE_POST = """
MERGE (p:Post {post_id: $post_id})
SET p.platform = $platform,
    p.url = $url,
    p.author_hash = $author_hash,
    p.content = $content,
    p.created_at = datetime($created_at),
    p.engagement = $engagement
"""

# Luồng thảo luận. MERGE node cha trước để reply nạp trước gốc vẫn nối được —
# thứ tự nạp không được phép quyết định graph có đúng hay không.
_MERGE_REPLY_TO = """
MATCH (child:Post {post_id: $post_id})
MERGE (parent:Post {post_id: $parent_id})
MERGE (child)-[:REPLY_TO]->(parent)
"""

_MERGE_TOPIC = """
MATCH (p:Post {post_id: $post_id})
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name
MERGE (p)-[:ABOUT]->(t)
"""

_MERGE_CLAIM = """
MATCH (p:Post {post_id: $post_id})
MERGE (c:Claim {claim_id: $claim_id})
SET c.text = $text,
    c.verdict = $verdict,
    c.confidence = $confidence,
    c.explanation = $explanation,
    c.correct_statement = $correct_statement
MERGE (p)-[:CONTAINS_CLAIM]->(c)
"""

_MERGE_REFERS_TO = """
MATCH (c:Claim {claim_id: $claim_id})
MATCH (n) WHERE n.point_id = $node_id OR n.clause_id = $node_id OR n.article_id = $node_id
MERGE (c)-[r:REFERS_TO]->(n)
SET r.confidence = $confidence, r.method = $method
"""

_MERGE_MISCONCEPTION = """
MERGE (m:Misconception {misconception_id: $misconception_id})
SET m.canonical_text = $canonical_text,
    m.first_seen = datetime($first_seen),
    m.last_seen = datetime($last_seen),
    m.count = $count,
    m.total_engagement = $total_engagement
"""

_MERGE_INSTANCE_OF = """
MATCH (c:Claim {claim_id: $claim_id})
MATCH (m:Misconception {misconception_id: $misconception_id})
MERGE (c)-[:INSTANCE_OF]->(m)
"""

_MERGE_CONTRADICTS = """
MATCH (m:Misconception {misconception_id: $misconception_id})
MATCH (n) WHERE n.point_id = $point_id OR n.clause_id = $point_id OR n.article_id = $point_id
MERGE (m)-[:CONTRADICTS]->(n)
"""


# ---------------------------------------------------------------------------
# Nạp văn bản
# ---------------------------------------------------------------------------


def load_document(doc: dict[str, Any]) -> None:
    """Nạp 1 LegalDocument + toàn bộ cây Điều-Khoản-Điểm. Idempotent.

    Cả văn bản đi trong MỘT transaction — nạp nửa cây rồi lỗi thì graph còn tệ
    hơn là rỗng, vì query sau đó trả kết quả thiếu mà không báo gì.
    """
    stmts: list[tuple[str, dict]] = [
        (
            _MERGE_DOC,
            {
                "doc_id": doc["doc_id"],
                "doc_number": doc["doc_number"],
                "title": doc["title"],
                "issuer": doc["issuer"],
                "issued_date": doc["issued_date"],
                "effective_date": doc["effective_date"],
                "expiry_date": doc.get("expiry_date"),
                "status": doc.get("status", "ACTIVE"),
                "source_url": doc["source_url"],
            },
        )
    ]

    for article in doc.get("articles", []):
        stmts.append(
            (
                _MERGE_ARTICLE,
                {
                    "doc_id": doc["doc_id"],
                    "article_id": article["article_id"],
                    "number": article["number"],
                    "heading": article.get("heading", ""),
                    "text": article.get("text", ""),
                    "effective_from": article["effective_from"],
                    "effective_to": article.get("effective_to"),
                },
            )
        )
        for clause in article.get("clauses", []):
            stmts.append(
                (
                    _MERGE_CLAUSE,
                    {
                        "article_id": article["article_id"],
                        "clause_id": clause["clause_id"],
                        "number": clause["number"],
                        "text": clause.get("text", ""),
                        "effective_from": clause["effective_from"],
                        "effective_to": clause.get("effective_to"),
                    },
                )
            )
            for point in clause.get("points", []):
                stmts.append(
                    (
                        _MERGE_POINT,
                        {
                            "clause_id": clause["clause_id"],
                            "point_id": point["point_id"],
                            "letter": point.get("letter", ""),
                            "text": point.get("text", ""),
                            "effective_from": point["effective_from"],
                            "effective_to": point.get("effective_to"),
                        },
                    )
                )

    # Quan hệ giữa văn bản: replaces / amends / references
    for key, rel in (("replaces", "REPLACES"), ("amends", "AMENDS")):
        if doc.get(key):
            stmts.append(
                (
                    _MERGE_DOC_REL % rel,
                    {"new_doc_id": doc["doc_id"], "old_doc_id": doc[key]},
                )
            )

    connection.write_batch(stmts)


def load_entities(entities: list[dict[str, Any]]) -> None:
    """Nạp ExtractedEntities (output của P1) và gắn vào node tương ứng."""
    stmts: list[tuple[str, dict]] = []

    for ent in entities:
        node_id = ent["node_id"]

        for field, (label, rel, prefix) in _ENTITY_REL.items():
            for i, text in enumerate(ent.get(field, [])):
                entity_id = f"{node_id}-{prefix}{i}"
                stmts.append(
                    (
                        _MERGE_ENTITY % (label, rel),
                        {"node_id": node_id, "entity_id": entity_id, "text": text},
                    )
                )
                if field in _NO_SUBJECT_FIELDS:
                    continue
                # Chủ thể gắn vào entity, không gắn thẳng vào Điểm
                for subject in ent.get("subjects", []):
                    stmts.append(
                        (
                            _MERGE_SUBJECT,
                            {
                                "entity_id": entity_id,
                                "normalized": _normalize(subject),
                                "name": subject,
                            },
                        )
                    )

        for i, pen in enumerate(ent.get("penalties", [])):
            stmts.append(
                (
                    _MERGE_PENALTY,
                    {
                        "node_id": node_id,
                        "penalty_id": f"{node_id}-pen{i}",
                        "type": pen["type"],
                        "min_amount": pen.get("min_amount"),
                        "max_amount": pen.get("max_amount"),
                        "duration_months": pen.get("duration_months"),
                        "is_permanent": pen.get("is_permanent", False),
                        "text": pen.get("text", ""),
                    },
                )
            )

    if stmts:
        connection.write_batch(stmts)


# ---------------------------------------------------------------------------
# Nạp dư luận
# ---------------------------------------------------------------------------


def load_post(post: dict[str, Any], claims: list[dict[str, Any]] | None = None) -> None:
    """Nạp 1 Post + Claim + REFERS_TO. Post không có claim vẫn nạp bình thường."""
    stmts: list[tuple[str, dict]] = [
        (
            _MERGE_POST,
            {
                "post_id": post["post_id"],
                "platform": post["platform"],
                "url": post["url"],
                "author_hash": post["author_hash"],
                "content": post["content"],
                "created_at": post["created_at"],
                "engagement": post.get("engagement", 0),
            },
        )
    ]

    # REPLY_TO: nối reply về comment gốc. Thiếu quan hệ này thì hiểu nhầm và
    # đính chính nằm rời nhau, misinformation.py mất ngữ cảnh.
    if post.get("parent_id"):
        stmts.append(
            (
                _MERGE_REPLY_TO,
                {"post_id": post["post_id"], "parent_id": post["parent_id"]},
            )
        )

    for claim in claims or []:
        topic = claim.get("topic")
        if topic:
            stmts.append(
                (
                    _MERGE_TOPIC,
                    {
                        "post_id": post["post_id"],
                        "topic_id": _normalize(topic),
                        "name": topic,
                    },
                )
            )
        stmts.append(
            (
                _MERGE_CLAIM,
                {
                    "post_id": post["post_id"],
                    "claim_id": claim["claim_id"],
                    "text": claim["text"],
                    "verdict": claim.get("verdict", "UNVERIFIABLE"),
                    "confidence": claim.get("confidence", 0.0),
                    "explanation": claim.get("explanation", ""),
                    "correct_statement": claim.get("correct_statement", ""),
                },
            )
        )
        for cit in claim.get("citations", []):
            stmts.append(
                (
                    _MERGE_REFERS_TO,
                    {
                        "claim_id": claim["claim_id"],
                        "node_id": cit["node_id"],
                        "confidence": cit.get("confidence", 0.0),
                        "method": cit.get("method", "hybrid"),
                    },
                )
            )

    connection.write_batch(stmts)


def load_misconceptions(miscs: list[dict[str, Any]]) -> None:
    """Nạp Misconception + INSTANCE_OF + CONTRADICTS."""
    stmts: list[tuple[str, dict]] = []
    for m in miscs:
        stmts.append(
            (
                _MERGE_MISCONCEPTION,
                {
                    "misconception_id": m["misconception_id"],
                    "canonical_text": m["canonical_text"],
                    "first_seen": m["first_seen"],
                    "last_seen": m["last_seen"],
                    "count": m.get("count", 0),
                    "total_engagement": m.get("total_engagement", 0),
                },
            )
        )
        for claim_id in m.get("_members", []):
            stmts.append(
                (
                    _MERGE_INSTANCE_OF,
                    {"claim_id": claim_id, "misconception_id": m["misconception_id"]},
                )
            )
        for point_id in m.get("contradicts", []):
            stmts.append(
                (
                    _MERGE_CONTRADICTS,
                    {"misconception_id": m["misconception_id"], "point_id": point_id},
                )
            )
    if stmts:
        connection.write_batch(stmts)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def load_processed(processed_dir: Path | None = None) -> list[str]:
    """Nạp văn bản THẬT của P1 từ data/processed/legal_docs_structured/*.json.

    Đây là đường chính của pipeline. Trả list doc_id đã nạp.

    Mock ở data/fixtures/ KHÔNG dùng ở đây nữa — nó chỉ còn sống trong tests/,
    vì nó là thứ duy nhất có đáp án viết sẵn (expected_diff, expected_q2...).
    Dữ liệu thật không có nhãn nên không làm regression test được.
    """
    from backend.core.config import ROOT

    d = processed_dir or ROOT / "data" / "processed" / "legal_docs_structured"
    files = sorted(d.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"không có văn bản nào trong {d}")

    loaded: list[str] = []
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        load_document(doc)
        n_art = len(doc.get("articles") or [])
        n_pt = sum(
            len(c.get("points") or [])
            for a in doc.get("articles") or []
            for c in a.get("clauses") or []
        )
        rel = doc.get("replaces") or doc.get("amends")
        print(
            f"  {doc['doc_id']:<12} {doc['doc_number']:<16} "
            f"{n_art:>3} Điều / {n_pt:>3} Điểm"
            + (f"  -> thay thế {rel}" if rel else "")
        )
        loaded.append(doc["doc_id"])

        # Entity: ưu tiên bản nhúng (fixtures/mock), nếu không có thì tìm file
        # riêng entities_<doc_id>.json — đây là cách P1 xuất (file tách rời).
        ents = doc.get("entities")
        if not ents:
            side = d.parent / f"entities_{doc['doc_id']}.json"
            if side.exists():
                ents = json.loads(side.read_text(encoding="utf-8"))
        if ents:
            load_entities(ents)
            print(f"  {'':<12} + entity cho {len(ents)} node")

    return loaded


def diff_all_replacements() -> None:
    """Chạy diffing cho mọi cặp (văn bản mới)-[:REPLACES]->(văn bản cũ) trong graph.

    Phải chạy SAU load_processed(): nó đóng effective_to của Điểm cũ, thiếu bước
    này thì query time-travel trả cả luật cũ lẫn luật mới cho cùng một ngày.
    """
    from backend.graph.diffing import diff_documents

    pairs = connection.run(
        "MATCH (new:LegalDocument)-[:REPLACES|AMENDS]->(old:LegalDocument) "
        "RETURN old.doc_id AS old, new.doc_id AS new"
    )
    if not pairs:
        print("  (không có cặp thay thế nào)")
        return

    for p in pairs:
        diffs = diff_documents(p["old"], p["new"])
        from collections import Counter

        c = Counter(d["change_type"] for d in diffs)
        paired = sum(v for k, v in c.items() if k not in ("ADDED", "REMOVED"))
        print(f"  {p['old']} -> {p['new']}: {paired} cặp ghép được | {dict(c)}")


def load_fixtures(fixtures_dir: Path | None = None) -> None:
    """Nạp data/fixtures/*.json — CHỈ dùng cho tests/, không dùng cho pipeline.

    Mock giữ lại vì nó có đáp án viết sẵn để làm regression test. Pipeline và
    demo dùng load_processed() với dữ liệu thật của P1.
    """
    from backend.core.config import ROOT

    d = fixtures_dir or ROOT / "data" / "fixtures"

    legal = json.loads((d / "mock_legal_docs.json").read_text(encoding="utf-8"))
    for doc in legal["documents"]:
        load_document(doc)
        print(f"  nạp văn bản {doc['doc_id']}")

    # entity giả lập output extractor.py của P1 — giờ 8 thay bằng đồ thật
    if legal.get("entities"):
        load_entities(legal["entities"])
        print(f"  nạp entity cho {len(legal['entities'])} node")

    posts = json.loads((d / "mock_posts.json").read_text(encoding="utf-8"))
    claims_by_post: dict[str, list[dict]] = {}
    for c in posts.get("claims", []):
        claims_by_post.setdefault(c["post_id"], []).append(c)
    for post in posts["posts"]:
        load_post(post, claims_by_post.get(post["post_id"], []))
    print(f"  nạp {len(posts['posts'])} post, {len(posts.get('claims', []))} claim")

    load_misconceptions(posts.get("misconceptions", []))
    print(f"  nạp {len(posts.get('misconceptions', []))} misconception")


def _normalize(text: str) -> str:
    return text.strip().lower().replace(" ", "_")


if __name__ == "__main__":
    # Đường chính: nạp văn bản THẬT của P1 rồi chạy diffing.
    #   python -m backend.graph.loader           -> nạp thêm vào graph hiện có
    #   python -m backend.graph.loader --wipe    -> xoá sạch rồi nạp lại
    import sys

    from backend.graph.schema import apply_schema, print_acceptance

    if "--wipe" in sys.argv:
        print("wipe graph...")
        connection.wipe()

    print("apply_schema...")
    apply_schema()

    print("nạp văn bản thật:")
    load_processed()

    print("diffing các cặp thay thế:")
    diff_all_replacements()

    if "--verify" in sys.argv:
        print("nghiệm thu (chạy trên fixture mock, cần --wipe trước):")
        print_acceptance()

    print("xong")
