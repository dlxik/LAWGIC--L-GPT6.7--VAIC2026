"""[P2] Regression test cho backend/graph/ — chạy trên DỮ LIỆU THẬT.

Chạy:  pytest tests/ -v          (cần Neo4j đang chạy: docker compose up -d neo4j)

KHÔNG còn fixture giả lập. Test nạp thẳng 3 văn bản thuế thật của P1 từ
data/processed/ rồi kiểm các TÍNH CHẤT BẤT BIẾN + vài ca thật đã biết (Điều 52
-> Điều 25, ngưỡng cutover 01/07/2026). Mỗi test khoá một quyết định thiết kế
hoặc một lỗi ĐÃ TỪNG XẢY RA. Test đỏ = có người vừa phá một trong hai thứ đó.
"""

from __future__ import annotations

import json

import pytest

from backend.core.config import ROOT
from backend.graph import connection
from backend.graph.diffing import (
    _classify,
    _pair_points,
    diff_documents,
    law_as_of,
    point_history,
)
from backend.graph.loader import (
    diff_all_replacements,
    load_document,
    load_entities,
    load_processed,
)
from backend.graph.schema import apply_schema, verify_acceptance

# --- Ca thật đã verify trên graph (dùng làm mốc assert) ---------------------
OLD_DOC, NEW_DOC = "qlt2019", "qlt2025"        # qlt2025 REPLACES qlt2019
CUTOVER = "2026-07-01"                          # luật mới có hiệu lực
BEFORE = "2026-06-30"
# Điều 52 (cũ) -> Điều 25 (mới): supersession thật, ĐỔI SỐ HIỆU, đổi thuật ngữ
# "Người khai thuế" -> "Người nộp thuế" (REWORDED, sim ~0.82).
SUP_OLD, SUP_NEW = "qlt2019-d52-k1-c", "qlt2025-d25-k1-c"
DOCS = {"qlt2019", "qlt2025", "tncn2025"}


@pytest.fixture(scope="module", autouse=True)
def graph():
    """Graph sạch + DỮ LIỆU THẬT, dùng chung cho cả module (nạp 1 lần)."""
    if not connection.healthcheck():
        pytest.skip("Neo4j chưa chạy — docker compose up -d neo4j")
    connection.wipe()
    apply_schema()
    load_processed()          # 3 văn bản thuế thật + entity từ file riêng của P1
    diff_all_replacements()   # sinh SUPERSEDED_BY + đóng effective_to node cũ
    yield
    connection.close()


def _count() -> int:
    return connection.run("MATCH (n) RETURN count(n) AS n")[0]["n"]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_loader_idempotent():
    """Nạp lại KHÔNG được nhân đôi node. Khoá quyết định: MERGE theo id, không CREATE.

    Nạp lại văn bản nhỏ nhất (tncn2025) + entity của nó, đếm node phải giữ nguyên.
    """
    d = ROOT / "data" / "processed" / "legal_docs_structured"
    doc = json.loads((d / "tncn2025.json").read_text(encoding="utf-8"))
    ents = json.loads((d.parent / "entities_tncn2025.json").read_text(encoding="utf-8"))

    before = _count()
    load_document(doc)
    load_entities(ents)
    after = _count()
    assert before == after, f"nạp lại làm node tăng {before} -> {after} (CREATE thay vì MERGE?)"


def test_all_documents_present():
    docs = {r["id"] for r in connection.run("MATCH (d:LegalDocument) RETURN d.doc_id AS id")}
    assert docs == DOCS, f"thiếu/thừa văn bản: {docs}"


def test_no_orphan_leaf_nodes():
    """Mọi Điểm/Khoản/Điều phải truy ngược được lên tận LegalDocument.

    Cây Điều-Khoản-Điểm không được đứt ở giữa. Một Điểm không có Khoản cha =
    lỗi parser hoặc lỗi nạp, và nó sẽ vô hình với mọi query đi từ văn bản xuống.
    """
    orphan_p = connection.run(
        "MATCH (p:Point) WHERE NOT (:Clause)-[:HAS_POINT]->(p) RETURN count(p) AS n"
    )[0]["n"]
    orphan_k = connection.run(
        "MATCH (k:Clause) WHERE NOT (:Article)-[:HAS_CLAUSE]->(k) RETURN count(k) AS n"
    )[0]["n"]
    orphan_a = connection.run(
        "MATCH (a:Article) WHERE NOT (:LegalDocument)-[:HAS_ARTICLE]->(a) RETURN count(a) AS n"
    )[0]["n"]
    assert (orphan_p, orphan_k, orphan_a) == (0, 0, 0), (
        f"node mồ côi: {orphan_p} Điểm, {orphan_k} Khoản, {orphan_a} Điều"
    )


def test_dates_are_date_type_not_string():
    """effective_from phải là kiểu date của Neo4j, không phải string.

    Để string thì so sánh theo thứ tự chữ cái -> time-travel sai âm thầm.
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
    pen = connection.run("MATCH (p:Penalty) RETURN count(p) AS n")[0]["n"]
    subj = connection.run("MATCH (s:Subject) RETURN count(s) AS n")[0]["n"]
    assert pen > 0 and subj > 0, "entity thật chưa lên graph"

    # Subject phải gộp: số node Subject ít hơn hẳn số cạnh APPLIES_TO trỏ vào nó
    edges = connection.run("MATCH (:Subject)<-[r:APPLIES_TO]-() RETURN count(r) AS n")[0]["n"]
    assert subj < edges, "Subject không được nhân bản mỗi node quy định một cái"


def test_entity_labels_are_separate():
    """Obligation / Right / Prohibition là label riêng, không gộp :Provision. Quyết định #4."""
    labels = {
        r["l"] for r in connection.run("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")
    }
    assert {"Obligation", "Right", "Prohibition"} <= labels
    assert "Provision" not in labels, "đã gộp label — trái quyết định #4"


def test_tax_entities_loaded():
    """3 node đặc thù luật thuế (P1) phải lên graph — nếu không, mất câu chuyện demo.

    TaxRate/TaxBase/Exemption gắn qua HAS_TAX_RATE/HAS_TAX_BASE/HAS_EXEMPTION.
    Khoản 'ngưỡng 500 triệu' (tncn2025-d7-k1) phải có Exemption.
    """
    n = connection.run(
        "MATCH (:Exemption) RETURN count(*) AS n"
    )[0]["n"]
    assert n > 0, "không có node Exemption — 3 trường thuế của P1 bị rơi?"

    row = connection.run(
        "MATCH (k {clause_id:'tncn2025-d7-k1'})-[:HAS_EXEMPTION]->(e) RETURN e.text AS t"
    )
    assert row and "500 triệu" in row[0]["t"], "mất Exemption ngưỡng 500 triệu (node demo)"


def test_penalty_reachable_from_point():
    """Penalty là node riêng, đi tới được từ Point. Khoá quyết định #5."""
    rows = connection.run(
        "MATCH (p:Point)-[:PENALIZES]->(pen:Penalty) "
        "RETURN pen.type AS type LIMIT 5"
    )
    assert rows, "không Point nào dẫn tới Penalty"
    assert all(r["type"] for r in rows), "Penalty thiếu type"


def test_no_permanent_penalty_anywhere():
    """Luật thuế KHÔNG có mức phạt vĩnh viễn — bất biến dùng khi đối chiếu dư luận.

    Nếu dư luận đồn 'phạt vĩnh viễn' mà graph nói is_permanent=false ở mọi Penalty,
    đó chính là điểm bắt hiểu nhầm. Test đỏ = có dữ liệu phạt vĩnh viễn lọt vào,
    phải rà lại nguồn.
    """
    n = connection.run(
        "MATCH (pen:Penalty) WHERE pen.is_permanent = true RETURN count(pen) AS n"
    )[0]["n"]
    assert n == 0


# ---------------------------------------------------------------------------
# Diffing  (_pair_points / _classify là unit test thuần, không cần graph)
# ---------------------------------------------------------------------------


def test_structural_match_requires_text_corroboration():
    """LỖI ĐÃ XẢY RA (teammate bắt): vị trí trùng nhau bị coi là bằng chứng.

    Bản đầu ghép cặp theo (Điều, Khoản, Điểm) VÔ ĐIỀU KIỆN, không kiểm text.
    Dữ liệu thật: qlt2025 thay toàn bộ qlt2019 và đánh số lại (152 -> 53 Điều),
    nên 40/73 cặp là rác — tệ nhất sim=0.01, sinh SUPERSEDED_BY rác, hỏng im lặng.

    Hai Điểm dưới lấy nguyên văn từ dữ liệu thật, cùng Điều 34 Khoản 1 Điểm c,
    nội dung chẳng liên quan gì nhau.
    """
    old = [{
        "node_id": "qlt2019-d34-k1-c", "level": "Point",
        "letter": "c", "article": 34, "clause": 1,
        "text": "Số, ngày, tháng, năm của giấy chứng nhận đăng ký kinh doanh "
                "hoặc giấy phép thành lập và hoạt động;",
    }]
    new = [{
        "node_id": "qlt2025-d34-k1-c", "level": "Point",
        "letter": "c", "article": 34, "clause": 1,
        "text": "Áp dụng chế độ ưu tiên đối với người nộp thuế tuân thủ tốt "
                "pháp luật về thuế, sẵn sàng kết nối;",
    }]
    matched = {
        (o["node_id"] if o else None, n["node_id"] if n else None)
        for o, n in _pair_points(old, new)
    }
    assert ("qlt2019-d34-k1-c", "qlt2025-d34-k1-c") not in matched, (
        "trùng vị trí KHÔNG phải bằng chứng — text phải xác nhận"
    )
    assert ("qlt2019-d34-k1-c", None) in matched, "phải là REMOVED"
    assert (None, "qlt2025-d34-k1-c") in matched, "phải là ADDED"


def test_renumbered_point_still_found():
    """Ngược lại: Điểm bị đánh số lại nhưng giữ nội dung PHẢI ghép được.

    Cặp thật: Điều 52 -> Điều 25, luật mới đổi "Người khai thuế" ->
    "Người nộp thuế" khiến similarity tụt ~0.82 — ngưỡng fallback phải nhận.
    """
    old = [{
        "node_id": SUP_OLD, "level": "Point", "letter": "c", "article": 52, "clause": 1,
        "text": "Người khai thuế không chứng minh, giải trình hoặc quá thời hạn "
                "quy định mà không giải trình được;",
    }]
    new = [{
        "node_id": SUP_NEW, "level": "Point", "letter": "c", "article": 25, "clause": 1,
        "text": "Người nộp thuế không chứng minh, giải trình hoặc quá thời hạn "
                "quy định mà không giải trình được;",
    }]
    matched = {
        (o["node_id"] if o else None, n["node_id"] if n else None)
        for o, n in _pair_points(old, new)
    }
    assert (SUP_OLD, SUP_NEW) in matched, "đổi thuật ngữ kéo sim ~0.82 — fallback phải nhận"


def test_leaf_clause_and_point_never_paired_together():
    """Không được ghép một Khoản với một Điểm — khác tầng, khác đơn vị nội dung."""
    same = "Người nộp thuế có trách nhiệm nộp hồ sơ khai thuế đúng thời hạn."
    old = [{"node_id": "x-d1-k1", "level": "Clause", "letter": "", "article": 1, "clause": 1, "text": same}]
    new = [{"node_id": "y-d1-k1-a", "level": "Point", "letter": "a", "article": 1, "clause": 1, "text": same}]
    matched = {
        (o["node_id"] if o else None, n["node_id"] if n else None)
        for o, n in _pair_points(old, new)
    }
    assert ("x-d1-k1", "y-d1-k1-a") not in matched, "Khoản không thể ghép với Điểm"
    assert ("x-d1-k1", None) in matched and (None, "y-d1-k1-a") in matched


def test_tightened_detects_money_increase():
    """Phân loại TIGHTENED dựa vào SỐ, không dựa vào text.

    Hai câu gần giống nhau (sim ~0.87) nhưng tiền phạt tăng 3 lần -> phải ra
    TIGHTENED, không phải REWORDED. So text thuần sẽ mất phần 'văn bản mới siết gì'.
    """
    old = {"text": "Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng đối với hành vi khai sai."}
    new = {"text": "Phạt tiền từ 15.000.000 đồng đến 20.000.000 đồng đối với hành vi khai sai dẫn đến thiếu thuế."}
    change_type, sim, summary = _classify(old, new)
    assert change_type == "TIGHTENED", f"nhận {change_type}"
    assert "15,000,000" in summary or "15.000.000" in summary


def test_diff_is_idempotent():
    """Chạy diff 2 lần không tạo SUPERSEDED_BY trùng."""
    diff_documents(OLD_DOC, NEW_DOC)
    before = connection.run("MATCH ()-[r:SUPERSEDED_BY]->() RETURN count(r) AS n")[0]["n"]
    diff_documents(OLD_DOC, NEW_DOC)
    after = connection.run("MATCH ()-[r:SUPERSEDED_BY]->() RETURN count(r) AS n")[0]["n"]
    assert before == after


def test_real_supersession_is_reworded():
    """Ca thật: Điều 52 Khoản 1 Điểm c (cũ) -> Điều 25 Khoản 1 Điểm c (mới).

    Số hiệu Điều khác hẳn, hệ thống vẫn phải ghép và phân loại REWORDED (chỉ
    đổi 'Người khai thuế' -> 'Người nộp thuế', bản chất giữ nguyên).
    """
    diffs = diff_documents(OLD_DOC, NEW_DOC, write=False)
    got = {(d["old_point_id"], d["new_point_id"]): d["change_type"] for d in diffs}
    assert (SUP_OLD, SUP_NEW) in got, f"mất cặp thật {SUP_OLD} -> {SUP_NEW}"
    assert got[(SUP_OLD, SUP_NEW)] == "REWORDED", f"nhận {got[(SUP_OLD, SUP_NEW)]}"


def test_point_history_walks_supersede_chain():
    hist = [h["point_id"] for h in point_history(SUP_OLD)]
    assert hist == [SUP_OLD, SUP_NEW], f"chuỗi lịch sử sai: {hist}"


# ---------------------------------------------------------------------------
# Time-travel — phần khác biệt cốt lõi
# ---------------------------------------------------------------------------


def test_law_as_of_changes_at_cutover():
    """Cùng câu hỏi, khác ngày -> khác luật. Đây là điểm bán hàng của dự án.

    Trước cutover và sau cutover phải trả về BỘ node khác nhau (luật mới thay cũ).
    """
    before = {r["point_id"] for r in law_as_of(None, BEFORE)}
    after = {r["point_id"] for r in law_as_of(None, CUTOVER)}
    assert before and after, "một trong hai ngày trả rỗng"
    assert before != after, "luật trước/sau cutover phải khác nhau"


def test_law_as_of_returns_leaf_clauses_not_just_points():
    """LỖI ĐÃ XẢY RA: Q2 chỉ MATCH (p:Point) -> bỏ sót ~53% nội dung.

    Luật Việt Nam: phần lớn Khoản KHÔNG có Điểm — text của Khoản chính là quy định.
    Quy tắc: node SÂU NHẤT giữ sự thật -> Q2 trả node LÁ bất kể Point/Clause/Article.
    Ca thật: Khoản qlt2025-d2-k2 không có Điểm nào, phải xuất hiện; còn Khoản có
    Điểm (qlt2025-d25-k1) thì KHÔNG (nếu không sẽ trùng với các Điểm con của nó).
    """
    rows = {r["point_id"]: r for r in law_as_of(None, CUTOVER)}
    assert "qlt2025-d2-k2" in rows, "Khoản không có Điểm phải xuất hiện — chính nó là node lá"
    assert rows["qlt2025-d2-k2"]["level"] == "Clause"
    assert "qlt2025-d25-k1" not in rows, "Khoản CÓ Điểm không phải node lá"


def test_law_as_of_returns_each_node_once():
    """LỖI ĐÃ XẢY RA: Điểm có 2 Penalty -> Q2 trả 2 lần (thiếu collect()).

    Bug ẩn khi chưa có entity, chỉ nổ với dữ liệu thật nơi Điểm nào cũng có phạt.
    """
    ids = [r["point_id"] for r in law_as_of(None, BEFORE)]
    assert len(ids) == len(set(ids)), "node bị nhân bản trong kết quả law_as_of"


def test_law_as_of_carries_penalties_as_list():
    """Q2 kèm mức phạt gộp thành LIST; node chưa có phạt là [] chứ không phải [null]."""
    rows = law_as_of(None, BEFORE)
    for r in rows:
        assert isinstance(r["penalties"], list)
        assert None not in r["penalties"], "penalties chứa null — thiếu lọc trong collect()"
    assert any(r["penalties"] for r in rows), "không node nào kèm được Penalty"


def test_no_gap_day_at_cutover():
    """LỖI ĐÃ XẢY RA: ngày 30/6 trả rỗng — một ngày luật biến mất.

    Quy ước half-open [from, to): effective_to là ngày ĐẦU TIÊN HẾT hiệu lực.
    Ngày xa cutover pass kể cả khi sai -> phải kiểm sát ngay 4 ngày quanh mốc.
    """
    for date in ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"):
        assert law_as_of(None, date), f"ngày {date} không có luật nào — có ngày hở"


def test_superseded_node_and_replacement_never_both_active():
    """Một quy định và bản THAY THẾ nó không được cùng hiệu lực một ngày (tránh đếm đôi).

    CHÚ Ý: hai VĂN BẢN qlt2019/qlt2025 ĐƯỢC PHÉP chồng nhau trong giai đoạn
    chuyển tiếp — đó chính là hiệu lực so le (Điều 13 luật mới sống từ 01/01/2026
    trong khi phần lớn luật cũ còn sống tới 30/06). Bất biến đúng nằm ở mức NODE:
    cặp (cũ)-[:SUPERSEDED_BY]->(mới) không bao giờ cùng xuất hiện trong law_as_of.
    """
    pairs = connection.run(
        """MATCH (o)-[:SUPERSEDED_BY]->(n)
           RETURN coalesce(o.point_id, o.clause_id, o.article_id) AS old,
                  coalesce(n.point_id, n.clause_id, n.article_id) AS new"""
    )
    for date in (BEFORE, CUTOVER, "2026-01-15"):
        active = {r["point_id"] for r in law_as_of(None, date)}
        for p in pairs:
            assert not (p["old"] in active and p["new"] in active), (
                f"ngày {date}: cả {p['old']} lẫn bản thay thế {p['new']} cùng hiệu lực — đếm đôi"
            )


def test_law_as_of_survives_rerun_of_diff():
    """Chạy lại diffing không được làm lệch effective_to (kết quả không phụ thuộc ai chạy sau)."""
    before = sorted(r["point_id"] for r in law_as_of(None, BEFORE))
    diff_documents(OLD_DOC, NEW_DOC)
    after = sorted(r["point_id"] for r in law_as_of(None, BEFORE))
    assert before == after


# ---------------------------------------------------------------------------
# Nghiệm thu tổng
# ---------------------------------------------------------------------------


def test_acceptance_queries_all_pass():
    failed = [k for k, v in verify_acceptance().items() if not v]
    assert not failed, f"query nghiệm thu fail: {failed}"
