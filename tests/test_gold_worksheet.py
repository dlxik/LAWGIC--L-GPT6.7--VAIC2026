"""[P3] Test cho bàn gắn nhãn gold set (make_worksheet + check_gold).

Chạy:  pytest tests/test_gold_worksheet.py -v      (không cần Neo4j / API key)

Khoá lại: worksheet chọn đúng vũ trụ mẫu, và check_gold BẮT được đúng những lỗi
làm hỏng con số accuracy — vì con số đó là thứ P3 mang ra trước BGK.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.check_gold import check, ci95
from scripts import make_worksheet as mw
from scripts.show_law import load_nodes

NODES = load_nodes()


# ---------- Bản đồ luật ----------


def test_law_map_points_at_real_nodes():
    """Mọi node_id trong LAW_MAP phải có thật — worksheet in bản đồ này ra làm chuẩn."""
    for _group, node_ids in mw.LAW_MAP:
        for node_id in node_ids:
            assert node_id in NODES, f"LAW_MAP trỏ node ma: {node_id}"


def test_thue_khoan_only_in_old_law():
    """Phương pháp khoán thuế chỉ còn ở luật cũ — mạch SUPERSEDED_BY của case demo.

    Khớp CẢ CỤM 'phương pháp khoán', không khớp 'khoán' trần: 'khoán' trần trúng
    cả 'khoáng sản' và 'khoản', cho kết quả sai.
    Nếu một ngày qlt2025 cũng có phương pháp khoán, giả định demo sai và phải biết.
    """
    import re
    pat = re.compile(r"khoán thuế|thuế khoán|phương pháp khoán|nộp thuế khoán|mức khoán", re.I)
    khoan = [n for n in NODES.values() if pat.search(n["text"])]
    assert khoan, "không tìm thấy 'phương pháp khoán' ở đâu cả — dữ liệu đổi?"
    assert any(n["doc_id"] == "qlt2019" for n in khoan)
    assert not any(n["doc_id"] == "qlt2025" for n in khoan)


# ---------- Chọn ứng viên ----------


def test_candidates_are_deterministic():
    """Seed cố định -> chạy lại ra đúng danh sách. Nhãn đã gắn không bị xáo."""
    posts = mw.load_posts()
    first = [p["post_id"] for p in mw.pick_candidates(posts)]
    second = [p["post_id"] for p in mw.pick_candidates(posts)]
    assert first == second


def test_candidates_respect_length_cap():
    """Không lấy bài luận dài — ép nó vào 1 citation là câu hỏi thi không đáp án."""
    posts = mw.load_posts()
    for post in mw.pick_candidates(posts):
        assert mw.MIN_LEN <= len(post["content"]) <= mw.MAX_LEN


def test_candidates_come_from_debated_threads():
    """Vũ trụ mẫu là 314 luồng có tranh luận — nơi hiểu nhầm lộ ra."""
    posts = mw.load_posts()
    threads = mw.build_threads(posts)
    debated_ids = {p["post_id"] for t in threads.values() if len(t) > 1 for p in t}
    for post in mw.pick_candidates(posts):
        assert post["post_id"] in debated_ids


# ---------- check_gold bắt lỗi ----------


def _row(cid, verdict, citation, text="claim", note="vì sao"):
    return {"claim_id": cid, "text": text, "expected_verdict": verdict,
            "expected_citation": citation, "note": note}


def _full_set(**overrides):
    """40 dòng hợp lệ, phân bổ cân (3 lớp). overrides thay một dòng cụ thể để test."""
    rows = []
    plan = [("INACCURATE", 20), ("ACCURATE", 10), ("UNVERIFIABLE", 10)]
    i = 0
    for verdict, n in plan:
        for _ in range(n):
            i += 1
            cid = f"g{i:03d}"
            citation = "" if verdict == "UNVERIFIABLE" else "tncn2025-d7-k1"
            rows.append(overrides.get(cid) or _row(cid, verdict, citation, text=f"claim {i}"))
    return rows


def test_clean_gold_passes():
    assert check(_full_set(), NODES) == 0


def test_fake_node_id_is_error():
    bad = _full_set(g001=_row("g001", "INACCURATE", "nd168-d5-k2-a"))
    assert check(bad, NODES) == 1


def test_invalid_verdict_is_error():
    bad = _full_set(g001=_row("g001", "SAI_CHINH_TA", "tncn2025-d7-k1"))
    assert check(bad, NODES) == 1


def test_duplicate_text_is_error():
    bad = _full_set(
        g001=_row("g001", "INACCURATE", "tncn2025-d7-k1", text="trùng"),
        g002=_row("g002", "INACCURATE", "tncn2025-d7-k1", text="trùng"),
    )
    assert check(bad, NODES) == 1


def test_todo_still_present_is_not_ready():
    bad = _full_set(g001=_row("g001", "TODO", "TODO"))
    assert check(bad, NODES) == 1


def test_underfilled_class_is_error():
    """Lớp < 8 mẫu -> F1 vô nghĩa -> phải báo lỗi, không âm thầm cho qua."""
    rows = [_row(f"g{i:03d}", "INACCURATE", "tncn2025-d7-k1", text=f"c{i}") for i in range(40)]
    rows += [_row(f"h{i:03d}", "ACCURATE", "tncn2025-d7-k1", text=f"a{i}") for i in range(3)]
    assert check(rows, NODES) == 1


def test_ci95_shrinks_with_n():
    """Sai số phải hẹp lại khi n tăng — cơ sở của 'cần 50 mẫu'."""
    assert ci95(0.8, 20) > ci95(0.8, 50) > ci95(0.8, 100)
    assert round(ci95(0.8, 50), 2) == 0.11
