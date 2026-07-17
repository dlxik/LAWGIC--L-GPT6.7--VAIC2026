"""[P2] Regression test cho backend/graph/.

Chạy:  pytest tests/ -v          (cần Neo4j đang chạy: docker compose up -d neo4j)

Mỗi test dưới đây khoá lại một quyết định thiết kế hoặc một lỗi ĐÃ TỪNG XẢY RA.
Test đỏ nghĩa là có người vừa phá một trong hai thứ đó.
"""

from __future__ import annotations

import json

import pytest

from backend.core.config import ROOT
from backend.graph import connection
from backend.graph.diffing import diff_documents, law_as_of, point_history
from backend.graph.loader import load_fixtures
from backend.graph.schema import apply_schema, verify_acceptance

FIXTURE = json.loads(
    (ROOT / "data" / "fixtures" / "mock_legal_docs.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module", autouse=True)
def graph():
    """Graph sạch + fixture, dùng chung cho cả module."""
    if not connection.healthcheck():
        pytest.skip("Neo4j chưa chạy — docker compose up -d neo4j")
    connection.wipe()
    apply_schema()
    load_fixtures()
    yield
    connection.close()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_loader_idempotent():
    """Nạp lại lần 2 KHÔNG được nhân đôi node.

    Khoá quyết định: MERGE theo id, không CREATE. Fixture sẽ được nạp lại hàng
    chục lần trong 24h; CREATE là nhân đôi âm thầm rồi query trả kết quả sai.
    """
    before = connection.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    load_fixtures()
    after = connection.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    assert before == after, f"nạp lại làm node tăng {before} -> {after}"


def test_document_tree_complete():
    """Cây Điều-Khoản-Điểm phải đủ 4 tầng, không đứt ở giữa."""
    rows = connection.run(
        """
        MATCH (d:LegalDocument)-[:HAS_ARTICLE]->(a:Article)
              -[:HAS_CLAUSE]->(k:Clause)-[:HAS_POINT]->(p:Point)
        RETURN d.doc_id AS doc, count(p) AS points
        ORDER BY doc
        """
    )
    assert {r["doc"]: r["points"] for r in rows} == {"mock-old": 3, "mock-new": 3}


def test_dates_are_date_type_not_string():
    """effective_from phải là kiểu date của Neo4j, không phải string.

    Để string thì so sánh theo thứ tự chữ cái -> time-travel sai âm thầm,
    không báo lỗi gì.
    """
    row = connection.run(
        "MATCH (p:Point) WHERE p.effective_from IS NOT NULL "
        "RETURN valueType(p.effective_from) AS t LIMIT 1"
    )[0]
    assert "DATE" in row["t"].upper(), f"effective_from đang là {row['t']}"


# ---------------------------------------------------------------------------
# Entity (output extractor.py của P1)
# ---------------------------------------------------------------------------


def test_entities_loaded():
    exp = FIXTURE["expected_entities"]
    n = connection.run("MATCH (p:Penalty) RETURN count(p) AS n")[0]["n"]
    assert n == exp["penalty_count"]

    n = connection.run("MATCH (s:Subject) RETURN count(s) AS n")[0]["n"]
    assert n == exp["subject_count"], "Subject phải gộp, không nhân bản mỗi node một cái"


def test_entity_labels_are_separate():
    """Obligation / Right / Prohibition là label riêng, không gộp :Provision.

    Khoá quyết định #4 — để query đọc được và Neo4j Browser tô màu khác nhau.
    """
    labels = {
        r["l"]
        for r in connection.run("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")
    }
    assert "Prohibition" in labels
    assert "Obligation" in labels
    assert "Provision" not in labels, "đã gộp label — trái quyết định #4"


def test_penalty_reachable_from_point():
    """Penalty là node riêng, đi tới được từ Point. Khoá quyết định #5."""
    rows = connection.run(
        """
        MATCH (p:Point {point_id: 'mock-new-d5-k2-a'})-[:PENALIZES]->(pen:Penalty)
        RETURN pen.type AS type, pen.duration_months AS months,
               pen.is_permanent AS perm
        ORDER BY type
        """
    )
    types = {r["type"] for r in rows}
    assert types == {"FINE", "LICENSE_SUSPENSION"}


def test_no_permanent_penalty_anywhere():
    """KHÔNG có mức phạt vĩnh viễn nào trong luật.

    Đây là toàn bộ luận điểm của case demo: tin đồn nói "tước bằng vĩnh viễn",
    graph nói 12 tháng. Test đỏ nghĩa là case demo sụp.
    """
    n = connection.run(
        "MATCH (pen:Penalty) WHERE pen.is_permanent = true RETURN count(pen) AS n"
    )[0]["n"]
    assert n == 0


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------


def test_diff_matches_expected():
    """Diff phải ra đúng 4 nhãn ghi trong fixture."""
    diffs = diff_documents("mock-old", "mock-new")
    got = {(d["old_point_id"], d["new_point_id"]): d["change_type"] for d in diffs}
    for exp in FIXTURE["expected_diff"]:
        key = (exp["old_point_id"], exp["new_point_id"])
        assert key in got, f"thiếu cặp {key}"
        assert got[key] == exp["change_type"], (
            f"{key}: mong đợi {exp['change_type']}, nhận {got[key]}"
        )


def test_unrelated_points_not_paired():
    """LỖI ĐÃ XẢY RA: ngưỡng 0.55 ghép mock-old-c với mock-new-d.

    Hai hành vi hoàn toàn khác nhau ("không có báo hiệu" 1-2 triệu vs "tái phạm
    nồng độ cồn" 20-22 triệu) nhưng sim=0.61 vì văn bản luật tiếng Việt quá
    khuôn mẫu. Hạ SIMILARITY_PAIR_THRESHOLD xuống là test này đỏ.
    """
    diffs = diff_documents("mock-old", "mock-new", write=False)
    pairs = {(d["old_point_id"], d["new_point_id"]) for d in diffs}
    assert ("mock-old-d5-k2-c", "mock-new-d5-k2-d") not in pairs
    assert ("mock-old-d5-k2-c", None) in pairs, "phải là REMOVED"
    assert (None, "mock-new-d5-k2-d") in pairs, "phải là ADDED"


def test_diff_is_idempotent():
    """Chạy diff 2 lần không tạo SUPERSEDED_BY trùng."""
    diff_documents("mock-old", "mock-new")
    before = connection.run("MATCH ()-[r:SUPERSEDED_BY]->() RETURN count(r) AS n")[0]["n"]
    diff_documents("mock-old", "mock-new")
    after = connection.run("MATCH ()-[r:SUPERSEDED_BY]->() RETURN count(r) AS n")[0]["n"]
    assert before == after


def test_tightened_detects_money_increase():
    """Phân loại TIGHTENED phải dựa vào SỐ, không dựa vào text.

    Điểm a: text gần y hệt (sim 0.99) nhưng tiền phạt tăng 3 lần. So text thuần
    sẽ ra REWORDED -> mất luôn phần "văn bản mới siết cái gì" của demo.
    """
    diffs = diff_documents("mock-old", "mock-new", write=False)
    d = next(x for x in diffs if x["new_point_id"] == "mock-new-d5-k2-a")
    assert d["change_type"] == "TIGHTENED"
    assert d["similarity"] > 0.95, "text gần giống — chính vì thế mới cần so số"
    assert "18,000,000" in d["summary"] or "18000000" in d["summary"]


def test_point_history_walks_supersede_chain():
    diff_documents("mock-old", "mock-new")
    hist = point_history("mock-old-d5-k2-a")
    assert [h["point_id"] for h in hist] == [
        "mock-old-d5-k2-a",
        "mock-new-d5-k2-a",
    ]


# ---------------------------------------------------------------------------
# Time-travel — phần khác biệt cốt lõi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("date,expected", FIXTURE["expected_q2_law_as_of"].items())
def test_law_as_of(date, expected):
    got = sorted(r["point_id"] for r in law_as_of(None, date))
    assert got == sorted(expected)


def test_law_as_of_returns_each_point_once():
    """LỖI ĐÃ XẢY RA: Điểm có 2 Penalty thì Q2 trả Điểm đó 2 lần.

    OPTIONAL MATCH sang Penalty làm mỗi Penalty đẻ một dòng. Điểm a có FINE +
    LICENSE_SUSPENSION -> xuất hiện 2 lần. Bug này ẩn khi chưa có entity (0
    penalty = 1 dòng null) và chỉ nổ với dữ liệu thật của P1, nơi Điểm nào cũng
    có vài mức phạt. Bỏ collect() trong Q2 là test này đỏ.
    """
    ids = [r["point_id"] for r in law_as_of(None, "2026-06-30")]
    assert len(ids) == len(set(ids)), f"Điểm bị nhân bản: {ids}"


def test_law_as_of_carries_penalties():
    """Q2 vẫn phải kèm mức phạt — gộp thành list, không mất dữ liệu."""
    rows = {r["point_id"]: r for r in law_as_of(None, "2026-07-01")}
    pens = rows["mock-new-d5-k2-a"]["penalties"]
    assert {p["type"] for p in pens} == {"FINE", "LICENSE_SUSPENSION"}
    susp = next(p for p in pens if p["type"] == "LICENSE_SUSPENSION")
    assert susp["duration_months"] == 12 and susp["is_permanent"] is False

    # Điểm chưa có entity -> list rỗng, không phải [null]
    assert rows["mock-new-d5-k2-d"]["penalties"] == []


def test_no_gap_day_at_cutover():
    """LỖI ĐÃ XẢY RA: ngày 30/6 trả về rỗng — một ngày luật biến mất.

    Nguyên nhân: fixture ghi effective_to=2026-06-30 nhưng query dùng
    'effective_to > date' (loại trừ). Quy ước: effective_to là ngày ĐẦU TIÊN
    HẾT hiệu lực. Ngày 15/6 và 15/7 pass kể cả khi sai -> chúng che bug.
    """
    for date in ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"):
        assert law_as_of(None, date), f"ngày {date} không có luật nào — có ngày hở"


def test_no_overlap_at_cutover():
    """Không được vừa luật cũ vừa luật mới cùng có hiệu lực một ngày."""
    for date in ("2026-06-30", "2026-07-01"):
        docs = {r["point_id"].rsplit("-d5", 1)[0] for r in law_as_of(None, date)}
        assert len(docs) == 1, f"ngày {date} có {docs} cùng hiệu lực"


def test_law_as_of_survives_rerun_of_diff():
    """Chạy lại diffing không được làm lệch effective_to.

    Fixture ghi effective_to, diffing cũng ghi effective_to. Hai đường phải ra
    cùng một giá trị, nếu không thì kết quả phụ thuộc vào việc ai chạy sau.
    """
    before = sorted(r["point_id"] for r in law_as_of(None, "2026-06-30"))
    diff_documents("mock-old", "mock-new")
    after = sorted(r["point_id"] for r in law_as_of(None, "2026-06-30"))
    assert before == after


# ---------------------------------------------------------------------------
# Nghiệm thu tổng
# ---------------------------------------------------------------------------


def test_acceptance_queries_all_pass():
    results = verify_acceptance()
    failed = [k for k, v in results.items() if not v]
    assert not failed, f"query nghiệm thu fail: {failed}"
