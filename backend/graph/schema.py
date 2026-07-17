"""[P2] Schema Neo4j — node, relationship, constraint. CONTRACT CHUNG.

NODES
  LegalDocument {doc_id, doc_number, title, issuer, issued_date,
                 effective_date, expiry_date, status, source_url}
  Article {article_id, number, heading, text, effective_from, effective_to}
  Clause  {clause_id, number, text, effective_from, effective_to}
  Point   {point_id, letter, text, effective_from, effective_to}
  Subject {name, normalized}
  Penalty {penalty_id, type, min_amount, max_amount, duration_months,
           is_permanent, text}
  Obligation | Right | Prohibition | Deadline {node_id, text}
  Topic   {topic_id, name}
  Post    {post_id, platform, url, author_hash, content, created_at, engagement}
          (parent_id chở bằng quan hệ REPLY_TO, không lưu làm property)
  Claim   {claim_id, text, verdict, confidence, explanation}
  Misconception {misconception_id, canonical_text, first_seen, last_seen, count}

RELATIONSHIPS
  (LegalDocument)-[:HAS_ARTICLE]->(Article)-[:HAS_CLAUSE]->(Clause)-[:HAS_POINT]->(Point)
  (Article|Clause|Point)-[:IMPOSES]->(Obligation)
  (Article|Clause|Point)-[:GRANTS]->(Right)
  (Article|Clause|Point)-[:PROHIBITS]->(Prohibition)
  (Article|Clause|Point)-[:PENALIZES]->(Penalty)
  (Obligation|Right|Prohibition)-[:APPLIES_TO]->(Subject)
  (LegalDocument)-[:AMENDS|REPLACES|REFERENCES]->(LegalDocument)
  (Point)-[:SUPERSEDED_BY {change_type, similarity, effective_from}]->(Point)
  (Post)-[:ABOUT]->(Topic)
  (Post)-[:CONTAINS_CLAIM]->(Claim)
  (Post)-[:REPLY_TO]->(Post)          -- reply -> comment gốc; luồng thảo luận
  (Claim)-[:REFERS_TO {confidence, method}]->(Point|Clause|Article)
  (Claim)-[:INSTANCE_OF]->(Misconception)
  (Misconception)-[:CONTRADICTS]->(Point)

===============================================================================
NĂM QUYẾT ĐỊNH ĐÃ CHỐT — không sửa một mình, phải báo cả team
===============================================================================

1. HIỆU LỰC Ở MỨC NODE, KHÔNG PHẢI MỨC VĂN BẢN.
   effective_from / effective_to nằm trên Article, Clause, Point.
   Nghị định mới thường chỉ sửa vài Điểm của nghị định cũ; phần còn lại vẫn sống.
   Gắn hiệu lực ở LegalDocument thì không diễn tả nổi "Điểm a chết, Điểm b sống"
   -> query time-travel (Q2 dưới) gãy -> mất luôn phần khác biệt của dự án.

2. NODE BẤT BIẾN. Không bao giờ SET text của Point đã tồn tại.
   Sửa luật = tạo Point mới thuộc văn bản mới + đóng effective_to của Point cũ
   + nối SUPERSEDED_BY. Sửa tại chỗ = mất lịch sử = Q2 chết.

3. ID DETERMINISTIC: <doc_id>-d<số>-k<số>-<chữ>. Sinh từ vị trí trong văn bản.
   Parser chạy 2 lần ra cùng ID -> MERGE idempotent -> nạp lại không nhân đôi.

4. OBLIGATION / RIGHT / PROHIBITION là 3 label riêng, không gộp :Provision {type}.
   Query đọc được ngay, và Neo4j Browser tô màu khác nhau lúc demo.

5. PENALTY LÀ NODE, không phải property. Nhiều Điểm cùng dẫn tới một mức phạt;
   câu "hành vi nào bị tước bằng có thời hạn" chỉ trả lời được khi Penalty là node.

VERDICT: ACCURATE | PARTIALLY_INACCURATE | INACCURATE | UNVERIFIABLE
CHANGE_TYPE: UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED
"""

# ---------------------------------------------------------------------------
# Constraint — chạy trước khi nạp bất kỳ dữ liệu nào
# ---------------------------------------------------------------------------

CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:LegalDocument) REQUIRE n.doc_id IS UNIQUE",
    "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.article_id IS UNIQUE",
    "CREATE CONSTRAINT clause_id IF NOT EXISTS FOR (n:Clause) REQUIRE n.clause_id IS UNIQUE",
    "CREATE CONSTRAINT point_id IF NOT EXISTS FOR (n:Point) REQUIRE n.point_id IS UNIQUE",
    "CREATE CONSTRAINT subject_norm IF NOT EXISTS FOR (n:Subject) REQUIRE n.normalized IS UNIQUE",
    "CREATE CONSTRAINT penalty_id IF NOT EXISTS FOR (n:Penalty) REQUIRE n.penalty_id IS UNIQUE",
    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.topic_id IS UNIQUE",
    "CREATE CONSTRAINT post_id IF NOT EXISTS FOR (n:Post) REQUIRE n.post_id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.claim_id IS UNIQUE",
    "CREATE CONSTRAINT misconception_id IF NOT EXISTS FOR (n:Misconception) REQUIRE n.misconception_id IS UNIQUE",
]

INDEXES: list[str] = [
    # Q2 time-travel quét theo khoảng hiệu lực -> index bắt buộc
    "CREATE INDEX point_effective IF NOT EXISTS FOR (n:Point) ON (n.effective_from, n.effective_to)",
    "CREATE INDEX clause_effective IF NOT EXISTS FOR (n:Clause) ON (n.effective_from, n.effective_to)",
    "CREATE INDEX article_effective IF NOT EXISTS FOR (n:Article) ON (n.effective_from, n.effective_to)",
    # Q3 trend lọc theo thời gian post
    "CREATE INDEX post_created IF NOT EXISTS FOR (n:Post) ON (n.created_at)",
    # Linker (P3) tìm ứng viên Điểm theo full-text
    "CREATE FULLTEXT INDEX point_text IF NOT EXISTS FOR (n:Point) ON EACH [n.text]",
    "CREATE FULLTEXT INDEX clause_text IF NOT EXISTS FOR (n:Clause) ON EACH [n.text]",
]


# ---------------------------------------------------------------------------
# ACCEPTANCE TEST — 3 query demo bắt buộc chạy được.
# Schema trả lời được 3 câu này thì chốt. Đây là tiêu chí chốt, không phải cãi nhau.
# ---------------------------------------------------------------------------

Q1_CITATION_TRACE = """
// Truy vết citation — xương sống của Q&A (P4 dùng)
MATCH (c:Claim {claim_id: $claim_id})-[r:REFERS_TO]->(p:Point)
MATCH (p)<-[:HAS_POINT]-(k:Clause)<-[:HAS_CLAUSE]-(d:Article)<-[:HAS_ARTICLE]-(doc:LegalDocument)
RETURN doc.doc_number AS doc, d.number AS dieu, k.number AS khoan,
       p.letter AS diem, p.text AS text, r.confidence AS confidence
"""

Q2_LAW_AS_OF = """
// Time-travel — thứ RAG vector không làm được. Câu quan trọng nhất.
//
// TRẢ VỀ NODE LÁ, không phải chỉ Point. "Node sâu nhất giữ sự thật":
// quy định nằm ở Điểm nếu Khoản có Điểm, nằm ở Khoản nếu Khoản không có Điểm,
// nằm ở Điều nếu Điều không có Khoản.
//
// LỖI ĐÃ XẢY RA: bản đầu chỉ MATCH (p:Point) -> bỏ sót 53% nội dung văn bản.
// Đo trên dữ liệu thật: 775/988 Khoản KHÔNG có Điểm nào (luật Việt Nam thật
// thì text của Khoản chính là quy định), 16 Điều không có Khoản. Điều 89
// "Hóa đơn điện tử" của Luật 2019 có 5 Khoản, 0 Điểm -> vô hình hoàn toàn.
// Mock không lộ ra vì fixture cho mọi Khoản đều có Điểm.
MATCH (n)
WHERE (n:Point OR n:Clause OR n:Article)
  AND NOT (n)-[:HAS_POINT|HAS_CLAUSE]->()   // chỉ lấy node lá
  AND n.effective_from <= date($date)
  AND (n.effective_to IS NULL OR n.effective_to > date($date))
  AND ($topic IS NULL OR EXISTS {
      MATCH (n)<-[:HAS_POINT|HAS_CLAUSE|HAS_ARTICLE*0..3]-(doc:LegalDocument)
      WHERE doc.title CONTAINS $topic
  })
// collect() BẮT BUỘC, không được trả pen.type thẳng. Một node thường có nhiều
// Penalty (phạt tiền + tước bằng) -> mỗi Penalty đẻ một dòng -> cùng một node
// trả về 2-3 lần. Lỗi này ẩn hoàn toàn khi chưa có entity (0 penalty = 1 dòng
// null), và chỉ nổ khi P1 giao dữ liệu thật. collect() gộp về đúng 1 dòng/node.
OPTIONAL MATCH (n)-[:PENALIZES]->(pen:Penalty)
RETURN coalesce(n.point_id, n.clause_id, n.article_id) AS point_id,
       labels(n)[0] AS level,
       n.text AS text,
       collect(DISTINCT pen{.type, .min_amount, .max_amount,
                            .duration_months, .is_permanent}) AS penalties
ORDER BY point_id
"""

Q3_TRENDING_MISCONCEPTIONS = """
// Trend hiểu nhầm — output cảnh báo chính (P3 sinh, P4 hiển thị)
MATCH (m:Misconception)<-[:INSTANCE_OF]-(cl:Claim)<-[:CONTAINS_CLAIM]-(post:Post)
WHERE post.created_at > datetime() - duration({hours: $window_hours})
WITH m, count(post) AS occurrences, sum(post.engagement) AS reach
WHERE occurrences >= $min_occurrences
OPTIONAL MATCH (m)-[:CONTRADICTS]->(p:Point)
RETURN m.misconception_id AS id, m.canonical_text AS text,
       occurrences, reach, collect(p.point_id) AS contradicts
ORDER BY occurrences DESC
"""

# Bonus: diff giữa 2 văn bản — dùng cho dashboard /document/{id}/diff
Q4_DOCUMENT_DIFF = """
MATCH (old:Point)-[s:SUPERSEDED_BY]->(new:Point)
WHERE old.point_id STARTS WITH $old_doc_id AND new.point_id STARTS WITH $new_doc_id
RETURN old.point_id AS old_id, old.text AS old_text,
       new.point_id AS new_id, new.text AS new_text,
       s.change_type AS change_type, s.similarity AS similarity
ORDER BY old.point_id
"""

ACCEPTANCE_QUERIES: dict[str, str] = {
    "Q1_citation_trace": Q1_CITATION_TRACE,
    "Q2_law_as_of": Q2_LAW_AS_OF,
    "Q3_trending_misconceptions": Q3_TRENDING_MISCONCEPTIONS,
    "Q4_document_diff": Q4_DOCUMENT_DIFF,
}


def apply_schema() -> None:
    """Chạy 1 lần khi khởi tạo DB. Idempotent (mọi câu đều IF NOT EXISTS)."""
    from backend.graph import connection

    for stmt in CONSTRAINTS + INDEXES:
        connection.write(stmt)


def verify_acceptance() -> dict[str, bool]:
    """Chạy 4 query nghiệm thu trên fixture. Pass hết -> schema chốt được.

    Đối chiếu với expected_* ghi sẵn trong data/fixtures/*.json. Đây là tiêu chí
    chốt schema, không phải cãi nhau bằng miệng.
    """
    import json

    from backend.core.config import ROOT
    from backend.graph import connection

    fixture = json.loads(
        (ROOT / "data" / "fixtures" / "mock_legal_docs.json").read_text(encoding="utf-8")
    )
    results: dict[str, bool] = {}

    # Q2 — câu quan trọng nhất: mô hình hiệu lực mức Điểm có đúng không
    for date, expected_ids in fixture["expected_q2_law_as_of"].items():
        rows = connection.run(Q2_LAW_AS_OF, date=date, topic=None)
        got = sorted(r["point_id"] for r in rows)
        ok = got == sorted(expected_ids)
        results[f"Q2_law_as_of[{date}]"] = ok
        if not ok:
            print(f"  Q2 {date}: mong đợi {sorted(expected_ids)}, nhận {got}")

    # Q3 — trend
    exp3 = json.loads(
        (ROOT / "data" / "fixtures" / "mock_posts.json").read_text(encoding="utf-8")
    )["expected_q3"]
    rows = connection.run(
        Q3_TRENDING_MISCONCEPTIONS,
        window_hours=24 * 365 * 100,  # fixture có ngày cố định -> mở rộng cửa sổ
        min_occurrences=exp3["min_occurrences"],
    )
    got_ids = sorted(r["id"] for r in rows)
    exp_ids = sorted(r["id"] for r in exp3["result"])
    results["Q3_trending"] = got_ids == exp_ids
    if got_ids != exp_ids:
        print(f"  Q3: mong đợi {exp_ids}, nhận {got_ids}")

    # Q1 — citation trace phải ra đủ 4 cấp Điều/Khoản/Điểm/văn bản
    rows = connection.run(Q1_CITATION_TRACE, claim_id="mock-c001")
    results["Q1_citation_trace"] = bool(rows) and all(
        rows[0].get(k) is not None for k in ("doc", "dieu", "khoan", "diem")
    )

    return results


def print_acceptance() -> bool:
    """In bảng nghiệm thu cho cả team xem. Trả True nếu pass hết."""
    results = verify_acceptance()
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    passed = all(results.values())
    print("SCHEMA CHỐT ĐƯỢC" if passed else "SCHEMA CHƯA ĐẠT — xem log trên")
    return passed
