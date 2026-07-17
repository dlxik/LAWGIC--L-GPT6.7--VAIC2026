"""[P4] Du lieu mock cho dashboard chay truoc khi P2/P3 nap du lieu that.

Case chinh: Nghi dinh 168/2025/ND-CP - nong do con
- 1 diem cua nghi dinh 100/2019/ND-CP (cu) bi SUPERSEDED_BY 1 diem cua nd168 (moi)
- 1 tin don sai lech (tuoc bang vinh vien) khi thuc te la co thoi han

Cac endpoint doc `get_source()` -> tu dong dung mock khi Neo4j chua co du lieu.
Khi P2 nap xong graph that, `get_source()` tra 'neo4j' va cac endpoint chuyen
sang query graph. Format tra ra khop 1-1 voi schemas.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

# ---------- Corpus luat mock ----------

LEGAL_NODES: dict[str, dict] = {
    # Nghi dinh CU (100/2019) - da bi thay the mot phan
    "nd100-d5-k10-a": {
        "node_id": "nd100-d5-k10-a",
        "node_label": "Point",
        "doc_id": "nd100",
        "doc_number": "100/2019/ND-CP",
        "display": "Điểm a Khoản 10 Điều 5 Nghị định 100/2019/NĐ-CP",
        "text": (
            "Phat tien tu 30.000.000 dong den 40.000.000 dong doi voi nguoi dieu "
            "khien xe o to ma trong mau hoac hoi tho co nong do con vuot qua "
            "80 miligam/100 mililit mau hoac vuot qua 0,4 miligam/1 lit khi tho."
        ),
        "effective_from": "2020-01-01",
        "effective_to": "2026-06-30",
        "status": "SUPERSEDED",
    },
    # Nghi dinh MOI (168/2025) - hieu luc 2026-07-01
    "nd168-d5-k2-a": {
        "node_id": "nd168-d5-k2-a",
        "node_label": "Point",
        "doc_id": "nd168",
        "doc_number": "168/2025/ND-CP",
        "display": "Điểm a Khoản 2 Điều 5 Nghị định 168/2025/NĐ-CP",
        "text": (
            "Phat tien tu 6.000.000 dong den 8.000.000 dong doi voi nguoi dieu "
            "khien xe o to ma trong mau hoac hoi tho co nong do con nhung chua "
            "vuot qua 50 miligam/100 mililit mau hoac chua vuot qua 0,25 miligam/"
            "1 lit khi tho. Ngoai ra bi tuoc quyen su dung Giay phep lai xe tu "
            "10 thang den 12 thang."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    "nd168-d5-k9-a": {
        "node_id": "nd168-d5-k9-a",
        "node_label": "Point",
        "doc_id": "nd168",
        "doc_number": "168/2025/ND-CP",
        "display": "Điểm a Khoản 9 Điều 5 Nghị định 168/2025/NĐ-CP",
        "text": (
            "Phat tien tu 30.000.000 dong den 40.000.000 dong doi voi nguoi dieu "
            "khien xe o to ma trong mau hoac hoi tho co nong do con vuot qua "
            "80 miligam/100 mililit mau hoac vuot qua 0,4 miligam/1 lit khi tho. "
            "Bi tuoc quyen su dung Giay phep lai xe tu 22 thang den 24 thang. "
            "KHONG tuoc vinh vien."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    # Mot dieu khong lien quan de test "khong du can cu"
    "nd168-d6-k1-a": {
        "node_id": "nd168-d6-k1-a",
        "node_label": "Point",
        "doc_id": "nd168",
        "doc_number": "168/2025/ND-CP",
        "display": "Điểm a Khoản 1 Điều 6 Nghị định 168/2025/NĐ-CP",
        "text": (
            "Phat tien tu 400.000 dong den 600.000 dong doi voi nguoi dieu khien "
            "xe mo to khong doi mu bao hiem khi tham gia giao thong."
        ),
        "effective_from": "2026-07-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
}


DOCUMENTS: dict[str, dict] = {
    "nd168": {
        "doc_id": "nd168",
        "doc_number": "168/2025/ND-CP",
        "title": "Nghi dinh quy dinh xu phat vi pham hanh chinh ve trat tu, an toan giao thong duong bo",
        "issuer": "Chinh phu",
        "issued_date": "2025-12-26",
        "effective_date": "2026-07-01",
        "status": "ACTIVE",
        "source_url": "https://vanban.chinhphu.vn/?pageid=27160&docid=168-2025",
    },
    "nd100": {
        "doc_id": "nd100",
        "doc_number": "100/2019/ND-CP",
        "title": "Nghi dinh quy dinh xu phat vi pham hanh chinh trong linh vuc giao thong duong bo va duong sat",
        "issuer": "Chinh phu",
        "issued_date": "2019-12-30",
        "effective_date": "2020-01-01",
        "status": "SUPERSEDED",
        "source_url": "https://vanban.chinhphu.vn/?pageid=27160&docid=100-2019",
    },
}


# SUPERSEDED_BY o muc Diem — day la khac biet cot loi so voi RAG vector
SUPERSEDES: list[dict] = [
    {
        "old_point_id": "nd100-d5-k10-a",
        "new_point_id": "nd168-d5-k9-a",
        "change_type": "REWORDED",
        "similarity": 0.87,
        "summary": (
            "Cung khung phat 30-40 trieu VND cho muc cao nhat, nhung nghi dinh moi "
            "quy dinh RO tuoc GPLX 22-24 thang (khong vinh vien) — vi vay tin don "
            "\"vinh vien\" gan voi van ban CU nhung dien giai sai."
        ),
        "effective_from": "2026-07-01",
    },
    {
        "old_point_id": None,
        "new_point_id": "nd168-d5-k2-a",
        "change_type": "ADDED",
        "similarity": 0.0,
        "summary": (
            "Nghi dinh moi bo sung khung phat NHE cho nong do con thap "
            "(6-8 trieu VND, tuoc GPLX 10-12 thang) — nd100 khong co muc nay."
        ),
        "effective_from": "2026-07-01",
    },
]


# ---------- Post + Claim + Misconception mock ----------

MISCONCEPTIONS: list[dict] = [
    {
        "misconception_id": "misc-001",
        "canonical_text": "Uong 1 lon bia bi tuoc bang lai xe vinh vien",
        "contradicts": ["nd168-d5-k2-a", "nd168-d5-k9-a"],
        "first_seen": "2026-07-15T08:12:00+00:00",
        "last_seen": "2026-07-17T09:45:00+00:00",
        "count": 47,
        "total_engagement": 12_384,
        "velocity": 0.98,  # 47 / 48h
        "severity": "HIGH",
        "correction": (
            "Theo Diem a Khoan 9 Dieu 5 Nghi dinh 168/2025/ND-CP: muc phat cao nhat "
            "(nong do con > 80mg/100ml mau) la 30-40 trieu VND kem tuoc GPLX 22-24 "
            "thang — KHONG tuoc vinh vien. Muc nhat (nong do con thap) chi phat "
            "6-8 trieu VND, tuoc GPLX 10-12 thang."
        ),
    },
    {
        "misconception_id": "misc-002",
        "canonical_text": "Nghi dinh 168 tang muc phat len 40 trieu la muc moi",
        "contradicts": ["nd168-d5-k9-a"],
        "first_seen": "2026-07-16T14:30:00+00:00",
        "last_seen": "2026-07-17T10:20:00+00:00",
        "count": 12,
        "total_engagement": 3_120,
        "velocity": 0.55,
        "severity": "MEDIUM",
        "correction": (
            "Muc phat 30-40 trieu VND KHONG phai la muc moi — Nghi dinh 100/2019 "
            "cu da co muc nay (Diem a Khoan 10 Dieu 5). Diem KHAC BIET: nghi dinh "
            "moi bo sung khung nhe 6-8 trieu cho nong do con thap."
        ),
    },
    {
        "misconception_id": "misc-003",
        "canonical_text": "Chi can ngoi tren xe ma co nong do con la bi phat",
        "contradicts": ["nd168-d5-k2-a"],
        "first_seen": "2026-07-17T02:15:00+00:00",
        "last_seen": "2026-07-17T09:10:00+00:00",
        "count": 8,
        "total_engagement": 1_540,
        "velocity": 1.14,  # tang nhanh
        "severity": "MEDIUM",
        "correction": (
            "Van ban chi phat NGUOI DIEU KHIEN xe (Diem a Khoan 2 Dieu 5). "
            "Ngoi tren xe khong dieu khien khong thuoc pham vi dieu chinh cua muc nay."
        ),
    },
]


POSTS_FOR_MISC: dict[str, list[dict]] = {
    "misc-001": [
        {
            "post_id": "p-001",
            "platform": "facebook_public",
            "url": "https://facebook.com/example/posts/001",
            "author_hash": "a3f9b1",
            "content": "Nghe noi tu 1/7 uong 1 lon bia bi tuoc bang vinh vien lun ae!",
            "created_at": "2026-07-15T08:12:00+00:00",
            "engagement": 3421,
        },
        {
            "post_id": "p-002",
            "platform": "news_comment",
            "url": "https://vnexpress.net/example/comment/002",
            "author_hash": "b7c2d0",
            "content": "Luat moi qua vo ly, chi 1 lon bia ma tuoc vinh vien",
            "created_at": "2026-07-16T11:04:00+00:00",
            "engagement": 892,
        },
    ],
}


# ---------- Q&A retrieval mock (keyword-based, khong can Anthropic key) ----------

_KEYWORD_INDEX: list[tuple[list[str], list[str]]] = [
    (["vinh vien", "tuoc bang"], ["nd168-d5-k9-a", "nd168-d5-k2-a"]),
    (["nong do con", "bia", "ruou", "1 lon"], ["nd168-d5-k2-a", "nd168-d5-k9-a", "nd100-d5-k10-a"]),
    (["mu bao hiem"], ["nd168-d6-k1-a"]),
    (["1/7", "hieu luc", "2026-07"], ["nd168-d5-k2-a"]),
]


def mock_retrieve(question: str) -> list[dict]:
    """Tra list Point ung vien cho cau hoi. Rat don gian, du de demo."""
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
        "articles": 6,
        "clauses": 18,
        "points": len(LEGAL_NODES),
        "supersedes_edges": len(SUPERSEDES),
        "posts_analysed": 512,
        "claims_extracted": 74,
        "misconceptions_active": len(MISCONCEPTIONS),
        "total_engagement_flagged": total_engagement,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock",
    }


def mock_diff(doc_id: str) -> list[dict]:
    """Tra list diff cho 1 van ban."""
    if doc_id == "nd168":
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
