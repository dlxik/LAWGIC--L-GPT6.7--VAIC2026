"""[P3] Test cho backend/discourse/linker.py.

Chạy:  pytest tests/test_linker.py -v      (không cần Neo4j / API key)

Khoá lại phần hybrid retrieval + graph expansion — thứ P3 phải bảo vệ trước BGK.
LLM chọn ở bước 3 được thay bằng fake.
"""

from __future__ import annotations

import pytest

from backend.discourse import linker


@pytest.fixture(autouse=True)
def _offline_retrieval(monkeypatch):
    """Mọi test trong file này chạy TF-IDF thuần (không gọi embedding API).

    Test kiểm LOGIC linking, không kiểm chất lượng embedding. Để USE_EMBEDDINGS=True
    thì mỗi test đụng mạng -> chậm, treo khi cache phải dựng lại, không tái lập.
    Đường embedding được đo riêng bằng script, không phải trong unit test.
    """
    monkeypatch.setattr(linker, "USE_EMBEDDINGS", False)


# ---------- Bước 1: TF-IDF retrieval ----------


def test_retrieval_finds_threshold_node():
    """Claim về ngưỡng 500tr phải kéo được tncn2025-d7-k1 vào ứng viên."""
    cands = linker._retrieve("doanh thu 500 triệu không phải nộp thuế", linker.TOP_K)
    assert "tncn2025-d7-k1" in cands


def test_rumor_matches_old_law():
    """Tin đồn 'thuế khoán' khớp luật CŨ (qlt2019) — tiền đề của bước graph expand.

    Nếu một ngày nó khớp luật mới, giả định 'vector trả nhầm luật cũ' sai và phải biết.
    """
    cands = linker._retrieve("hộ kinh doanh đóng thuế khoán theo doanh thu", linker.TOP_K)
    assert any(c.startswith("qlt2019-d51") for c in cands)


# ---------- Bước 2: graph expansion (điểm ăn tiền) ----------


def test_supersede_bridge_adds_new_law(monkeypatch):
    """Ứng viên ở luật cũ -> expansion kéo node luật mới vào. Đây là điểm khác biệt.

    Không có bước này thì linker chỉ trả luật cũ mà tin đồn đang bám — đúng chỗ
    vector store bó tay.

    Ép ĐƯỜNG FALLBACK (doc-level) để test tái lập bất kể Neo4j có chạy hay không:
    khi Neo4j sống, đường graph dùng SUPERSEDED_BY thật (chỉ có cho cặp điểm ghép
    được, không có cho thuế khoán vốn bị XOÁ) — hành vi đó phụ thuộc dữ liệu graph,
    không hợp để khoá trong unit test. Đường fallback là logic thuần, khoá được.
    """
    monkeypatch.setattr("backend.graph.connection.healthcheck", lambda: False)
    _, _, _, nodes = linker._index()
    old = [n for n in linker._retrieve("thuế khoán hộ kinh doanh", linker.TOP_K)
           if nodes[n]["doc_id"] == "qlt2019"]
    assert old, "cần ít nhất 1 ứng viên luật cũ để test có nghĩa"

    expanded = linker._graph_expand(old, nodes)
    added_new_law = [n for n in expanded
                     if n not in old and nodes[n]["doc_id"] in ("qlt2025", "tncn2025")]
    assert added_new_law, "graph expansion không bắc cầu sang luật mới"


def test_parent_ids():
    assert linker._parent_ids("tncn2025-d7-k2-a") == ["tncn2025-d7-k2", "tncn2025-d7"]
    assert linker._parent_ids("tncn2025-d7") == []


def test_family_expand_pulls_sibling_clause():
    """Chạm Khoản 3 (cách tính) -> phải kéo được Khoản 1 (ngưỡng) cùng Điều vào.

    Đây là ca kinh điển: claim khớp text cách tính nhưng căn cứ đúng là ngưỡng miễn.
    """
    _, _, _, nodes = linker._index()
    expanded = linker._family_expand(["tncn2025-d7-k3-a"], nodes)
    assert "tncn2025-d7-k1" in expanded
    assert "tncn2025-d7-k2" in expanded


def test_retrieval_recall_on_gold_stays_above_floor(monkeypatch):
    """Recall mốc TF-IDF (chạy offline, không gọi embedding API): >=40% claim có căn cứ.

    Đây là đường FALLBACK (embedding hỏng/không key). Production dùng embedding:
    recall đo được ~85% ở cả MAX_CANDIDATES=20 và 55 (embedding xếp điều đúng lên đầu).
    Giảm ứng viên 55->20 (để LLM chọn dễ hơn) làm TF-IDF fallback tụt 55%->44% nhưng
    KHÔNG hại đường embedding. Floor 40% chốt chặn hồi quy cho fallback, không phải
    mục tiêu chất lượng — chất lượng thật đo bằng citation_accuracy trong run_eval.
    """
    from eval.run_eval import load_gold

    monkeypatch.setattr(linker, "USE_EMBEDDINGS", False)  # offline, tái lập
    with_cite = [r for r in load_gold() if r.get("expected_citation")]
    hits = 0
    for row in with_cite:
        candidates, _ = linker._candidate_set(row["text"])
        if row["expected_citation"] in candidates:
            hits += 1
    recall = hits / len(with_cite)
    assert recall >= 0.40, f"retrieval recall (TF-IDF fallback) tụt còn {recall:.0%} (<40%)"


# ---------- Bước 3: LLM chọn ----------


class FakeLLM:
    def __init__(self, node_ids, confidence=0.9):
        self.node_ids = node_ids
        self.confidence = confidence
        self.last_prompt = None

    def extract(self, prompt, schema):
        self.last_prompt = prompt
        return schema(node_ids=self.node_ids, confidence=self.confidence)


@pytest.fixture
def fake_llm(monkeypatch):
    def install(node_ids, **kw):
        fake = FakeLLM(node_ids, **kw)
        monkeypatch.setattr(linker.llm, "extract", fake.extract)
        return fake

    return install


def test_link_returns_citation_for_valid_pick(fake_llm):
    fake_llm(["tncn2025-d7-k1"], confidence=0.9)
    cites = linker.link_claim("doanh thu 500 triệu không phải nộp thuế", "nguong_doanh_thu")

    assert len(cites) == 1
    assert cites[0]["node_id"] == "tncn2025-d7-k1"
    assert cites[0]["node_label"] == "Clause"
    assert cites[0]["confidence"] == 0.9
    assert "500 triệu" in cites[0]["text"]


def test_hallucinated_node_id_dropped(fake_llm):
    """LLM bịa node_id ngoài danh sách ứng viên -> DROP. Lớp chặn của P3.

    Claim phải có ứng viên thật, nhưng LLM cố tình chọn cả một node ma.
    """
    fake_llm(["tncn2025-d7-k1", "nd168-d5-k2-a"])  # node ma của đề tài cũ
    cites = linker.link_claim("doanh thu 500 triệu không phải nộp thuế")
    ids = [c["node_id"] for c in cites]

    assert "tncn2025-d7-k1" in ids
    assert "nd168-d5-k2-a" not in ids


def test_no_pick_returns_empty(fake_llm):
    """LLM thấy không node nào liên quan -> [] -> verdict sẽ thành UNVERIFIABLE."""
    fake_llm([])
    assert linker.link_claim("hôm nay trời đẹp quá") == []


def test_candidates_shown_to_llm(fake_llm):
    """Prompt phải chứa node_id ứng viên để LLM chọn được."""
    fake = fake_llm([])
    linker.link_claim("doanh thu 500 triệu không phải nộp thuế")
    assert "tncn2025-d7-k1" in fake.last_prompt
