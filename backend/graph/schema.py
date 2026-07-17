"""[P2] Schema Neo4j — node, relationship, constraint. CONTRACT CHUNG.

NODES
  LegalDocument {doc_id, doc_number, title, issuer, issued_date,
                 effective_date, expiry_date, status, source_url}
  Article {article_id, number, heading, text}
  Clause  {clause_id, number, text}
  Point   {point_id, letter, text}
  Subject {name, normalized}
  Penalty {type, min_amount, max_amount, duration_months, is_permanent, text}
  Obligation | Right | Prohibition | Deadline {node_id, text}
  Topic   {topic_id, name}
  Post    {post_id, platform, url, author_hash, content, created_at, engagement}
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
  (Claim)-[:REFERS_TO {confidence, method}]->(Point|Clause|Article)
  (Claim)-[:INSTANCE_OF]->(Misconception)
  (Misconception)-[:CONTRADICTS]->(Point)

SUPERSEDED_BY ở mức Điểm là thứ RAG vector thuần không làm được — nó cho phép
truy vấn "luật nói gì tại ngày X" và "điều này đã đổi thế nào".
"""

CONSTRAINTS: list[str] = [
    # TODO[P2]: mỗi node key một constraint UNIQUE
    # "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:LegalDocument) REQUIRE n.doc_id IS UNIQUE",
]

INDEXES: list[str] = [
    # TODO[P2]: index cho tra cứu theo thời gian + full-text cho Point.text
]


def apply_schema() -> None:
    """Chạy 1 lần khi khởi tạo DB. Idempotent."""
    raise NotImplementedError
