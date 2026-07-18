"""[P4] Du lieu mock cho dashboard khi Neo4j chua chay (dev offline hoac fallback).

Case chinh: nguong 500 trieu TNCN (khop demo/sample_case.md cua P3):
- tncn2025-d7-k1: Khoan (LEAF, khong co Diem con) — mien thue TNCN duoi 500tr
- qlt2019-d51: Dieu — phuong phap khoan (bi bo trong luat 2025)
- 1 tin don sai lech: "ho ~100-120 trieu da phai nop TNCN" — nho quy dinh cu

Cac endpoint doc `get_source()` -> tu dong dung mock khi Neo4j offline.
Khi Neo4j online, `get_source()` tra 'neo4j' va cac endpoint chuyen sang query
graph. Format tra ra khop 1-1 voi schemas.py + P2's graph_legend.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

# ---------- Corpus luat mock ----------

LEGAL_NODES: dict[str, dict] = {
    # Luat CU (QLT 38/2019/QH14) — phuong phap khoan, da bi bo trong luat 2025
    "qlt2019-d51": {
        "node_id": "qlt2019-d51",
        "node_label": "Article",  # Article-level: Dieu 51 khong co Khoan con trong mock
        "doc_id": "qlt2019",
        "doc_number": "38/2019/QH14",
        "display": "Điều 51 Luật Quản lý thuế 38/2019/QH14",
        "text": (
            "Cơ quan thuế xác định số tiền thuế phải nộp theo phương pháp khoán "
            "thuế (sau đây gọi là mức thuế khoán) đối với trường hợp hộ kinh doanh, "
            "cá nhân kinh doanh không thực hiện hoặc thực hiện không đầy đủ chế độ "
            "kế toán, hóa đơn, chứng từ."
        ),
        "effective_from": "2020-07-01",
        "effective_to": "2026-07-01",
        "status": "SUPERSEDED",
    },
    # Luat MOI QLT (108/2025/QH15) — dieu ke thua nhung bo phuong phap khoan
    "qlt2025-d25": {
        "node_id": "qlt2025-d25",
        "node_label": "Article",
        "doc_id": "qlt2025",
        "doc_number": "108/2025/QH15",
        "display": "Điều 25 Luật Quản lý thuế 108/2025/QH15",
        "text": (
            "Cơ quan thuế ấn định thuế đối với người nộp thuế trong trường hợp "
            "vi phạm pháp luật thuế theo quy định của Luật này. Luật này KHÔNG "
            "quy định phương pháp khoán thuế đối với hộ kinh doanh — hộ kinh "
            "doanh chuyển sang kê khai theo Luật Thuế thu nhập cá nhân."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    # Luat MOI TNCN (109/2025/QH15) — NGUONG 500 TRIEU: cau chuyen ngoi sao cua demo
    "tncn2025-d7-k1": {
        "node_id": "tncn2025-d7-k1",
        "node_label": "Clause",  # LEAF Clause: khong co Diem con
        "doc_id": "tncn2025",
        "doc_number": "109/2025/QH15",
        "display": "Khoản 1 Điều 7 Luật Thuế thu nhập cá nhân 109/2025/QH15",
        "text": (
            "Cá nhân cư trú có hoạt động sản xuất, kinh doanh có mức doanh thu "
            "năm từ 500.000.000 đồng trở xuống không phải nộp thuế thu nhập cá nhân."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    "tncn2025-d7-k2": {
        "node_id": "tncn2025-d7-k2",
        "node_label": "Clause",
        "doc_id": "tncn2025",
        "doc_number": "109/2025/QH15",
        "display": "Khoản 2 Điều 7 Luật Thuế thu nhập cá nhân 109/2025/QH15",
        "text": (
            "Cá nhân có doanh thu năm trên 500.000.000 đồng nộp thuế theo phương "
            "pháp kê khai: thu nhập chịu thuế bằng doanh thu trừ chi phí hợp lý, "
            "áp dụng thuế suất 15% (đối với doanh thu đến 3 tỷ đồng)."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    "tncn2025-d7-k3-a": {
        "node_id": "tncn2025-d7-k3-a",
        "node_label": "Point",
        "doc_id": "tncn2025",
        "doc_number": "109/2025/QH15",
        "display": "Điểm a Khoản 3 Điều 7 Luật Thuế thu nhập cá nhân 109/2025/QH15",
        "text": (
            "Trường hợp cá nhân đăng ký nộp thuế trên phần doanh thu vượt 500 "
            "triệu đồng, thuế suất áp dụng từ 0,5% đến 5% tùy ngành nghề."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
}


DOCUMENTS: dict[str, dict] = {
    "qlt2019": {
        "doc_id": "qlt2019",
        "doc_number": "38/2019/QH14",
        "title": "Luật Quản lý thuế",
        "issuer": "Quốc hội",
        "issued_date": "2019-06-13",
        "effective_date": "2020-07-01",
        "status": "SUPERSEDED",
        "source_url": "https://vbpl.vn/38-2019-qh14",
    },
    "qlt2025": {
        "doc_id": "qlt2025",
        "doc_number": "108/2025/QH15",
        "title": "Luật Quản lý thuế (sửa đổi)",
        "issuer": "Quốc hội",
        "issued_date": "2025-11-27",
        "effective_date": "2026-07-01",
        "status": "ACTIVE",
        "source_url": "https://vbpl.vn/108-2025-qh15",
    },
    "tncn2025": {
        "doc_id": "tncn2025",
        "doc_number": "109/2025/QH15",
        "title": "Luật Thuế thu nhập cá nhân (sửa đổi)",
        "issuer": "Quốc hội",
        "issued_date": "2025-11-27",
        "effective_date": "2026-07-01",
        "status": "ACTIVE",
        "source_url": "https://vbpl.vn/109-2025-qh15",
    },
}


# SUPERSEDED_BY — khac biet cot loi voi RAG vector
SUPERSEDES: list[dict] = [
    {
        "old_point_id": "qlt2019-d51",
        "new_point_id": "qlt2025-d25",
        "change_type": "TIGHTENED",
        "similarity": 0.72,
        "summary": (
            "Luat moi BO phuong phap khoan cho ho kinh doanh — chuyen sang ke khai "
            "theo Luat TNCN. Cum tu 'phuong phap khoan' xuat hien 0 lan trong luat "
            "2025 (nhieu lan trong luat 2019). Day la thay doi lon nhat, gay hieu "
            "nham nhieu nhat trong du luan."
        ),
        "effective_from": "2026-07-01",
    },
    {
        "old_point_id": None,
        "new_point_id": "tncn2025-d7-k1",
        "change_type": "ADDED",
        "similarity": 0.0,
        "summary": (
            "Luat TNCN 2025 THEM khoan mien thue: ho kinh doanh doanh thu <= 500 "
            "trieu/nam khong phai nop TNCN. Truoc day khong co nguong ro rang o cap "
            "luat — dan de bam vao muc khoan cu (~100tr) va tuong minh phai nop."
        ),
        "effective_from": "2026-07-01",
    },
]


# ---------- Post + Claim + Misconception mock ----------

MISCONCEPTIONS: list[dict] = [
    {
        "misconception_id": "misc-001",
        "canonical_text": "Ho kinh doanh thu nhap 100-120 trieu/nam la da phai nop thue TNCN",
        "contradicts": ["tncn2025-d7-k1", "qlt2019-d51"],
        "first_seen": "2025-06-09T14:30:00+00:00",
        "last_seen": "2025-12-19T09:45:00+00:00",
        "count": 6,
        "total_engagement": 98,
        "velocity": 0.42,
        "severity": "HIGH",
        "correction": (
            "Theo Khoan 1 Dieu 7 Luat 109/2025/QH15 (hieu luc 01/07/2026): ca nhan "
            "kinh doanh co DOANH THU nam tu 500 trieu tro xuong KHONG phai nop thue "
            "TNCN. Thu nhap 100-120 trieu tuong ung doanh thu thap hon nhieu — duoc "
            "mien hoan toan. Chi khi doanh thu vuot 500 trieu moi bat dau chiu thue."
        ),
    },
    {
        "misconception_id": "misc-002",
        "canonical_text": "Ho kinh doanh van tinh thue theo phuong phap khoan tu 1/7/2026",
        "contradicts": ["qlt2025-d25", "qlt2019-d51"],
        "first_seen": "2025-11-16T18:00:00+00:00",
        "last_seen": "2026-03-04T11:20:00+00:00",
        "count": 4,
        "total_engagement": 54,
        "velocity": 0.28,
        "severity": "MEDIUM",
        "correction": (
            "Luat 108/2025/QH15 (Dieu 25) da BO phuong phap khoan. Tu 01/07/2026, "
            "ho kinh doanh chuyen sang ke khai theo Luat TNCN 109/2025/QH15."
        ),
    },
    {
        "misconception_id": "misc-003",
        "canonical_text": "Doanh thu vuot 500 trieu la nop thue tren TOAN BO 500tr do",
        "contradicts": ["tncn2025-d7-k3-a"],
        "first_seen": "2026-01-10T08:15:00+00:00",
        "last_seen": "2026-04-02T10:10:00+00:00",
        "count": 3,
        "total_engagement": 41,
        "velocity": 0.34,
        "severity": "MEDIUM",
        "correction": (
            "Theo Diem a Khoan 3 Dieu 7 Luat 109/2025/QH15, chi tinh thue tren "
            "PHAN DOANH THU VUOT 500 trieu, khong tinh tren toan bo. Vi du doanh "
            "thu 700 trieu -> tinh thue tren 200 trieu vuot nguong."
        ),
    },
]


POSTS_FOR_MISC: dict[str, list[dict]] = {
    "misc-001": [
        {
            "post_id": "p-tax-001",
            "platform": "vnexpress_comment",
            "url": "https://vnexpress.net/example/comment/001",
            "author_hash": "e5a91b",
            "content": (
                "Nghe noi tu 1/7/2026, ho kinh doanh thu nhap tren 100 trieu la "
                "phai nop thue TNCN? Truoc gio moi don duoc 5 trieu/thang cung phai "
                "nop roi ma."
            ),
            "created_at": "2025-06-09T14:30:00+00:00",
            "engagement": 42,
        },
        {
            "post_id": "p-tax-002",
            "platform": "facebook_public",
            "url": "https://facebook.com/example/posts/002",
            "author_hash": "9d3c7f",
            "content": "Ho kinh doanh nho ma van bi tinh thue nhu doanh nghiep, luat moi qua gay.",
            "created_at": "2025-12-19T09:45:00+00:00",
            "engagement": 31,
        },
    ],
}


# ---------- Q&A retrieval mock (keyword-based, khong can Anthropic key) ----------

_KEYWORD_INDEX: list[tuple[list[str], list[str]]] = [
    (["500 trieu", "500.000.000", "nguong", "mien"], ["tncn2025-d7-k1", "tncn2025-d7-k2"]),
    (["khoan thue", "phuong phap khoan"], ["qlt2019-d51", "qlt2025-d25"]),
    (["ho kinh doanh", "ca nhan kinh doanh", "doanh thu"], ["tncn2025-d7-k1", "tncn2025-d7-k2", "tncn2025-d7-k3-a"]),
    (["tncn", "thu nhap ca nhan"], ["tncn2025-d7-k1", "tncn2025-d7-k2"]),
    (["1/7/2026", "hieu luc"], ["tncn2025-d7-k1", "qlt2025-d25"]),
    (["thue suat", "15%", "5%"], ["tncn2025-d7-k2", "tncn2025-d7-k3-a"]),
    (["400 trieu", "300 trieu", "100 trieu", "200 trieu"], ["tncn2025-d7-k1"]),
]


def mock_retrieve(question: str) -> list[dict]:
    """Tra list node ung vien cho cau hoi. Rat don gian, du de demo."""
    q = question.lower()
    hits: list[str] = []
    for kws, node_ids in _KEYWORD_INDEX:
        if any(kw in q for kw in kws):
            for nid in node_ids:
                if nid not in hits:
                    hits.append(nid)
    return [LEGAL_NODES[nid] for nid in hits if nid in LEGAL_NODES]


# ---------- Stats ----------


def mock_stats() -> dict:
    total_engagement = sum(m["total_engagement"] for m in MISCONCEPTIONS)
    return {
        "documents": len(DOCUMENTS),
        "articles": 3,
        "clauses": 8,
        "points": len(LEGAL_NODES),
        "supersedes_edges": len(SUPERSEDES),
        "posts_analysed": 3321,
        "claims_extracted": 91,
        "misconceptions_active": len(MISCONCEPTIONS),
        "total_engagement_flagged": total_engagement,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock",
    }


def mock_diff(doc_id: str) -> list[dict]:
    """Tra list diff cho 1 van ban (mock cho ca qlt2025 va tncn2025)."""
    if doc_id in ("qlt2025", "tncn2025"):
        return SUPERSEDES
    return []


__all__ = [
    "LEGAL_NODES",
    "DOCUMENTS",
    "SUPERSEDES",
    "MISCONCEPTIONS",
    "POSTS_FOR_MISC",
    "mock_retrieve",
    "mock_stats",
    "mock_diff",
]
