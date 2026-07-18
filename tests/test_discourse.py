"""[P3] Regression test cho backend/discourse/.

Chạy:  pytest tests/test_discourse.py -v      (KHÔNG cần Neo4j, KHÔNG cần API key)

Mỗi test khoá lại một quyết định thiết kế hoặc một lỗi ĐÃ TỪNG XẢY RA.
Test đỏ nghĩa là có người vừa phá một trong hai thứ đó.

llm.extract_batch bị thay bằng fake -> chạy được trước khi Nguyên xong core/llm.py
(DIVISION.md deadline giờ 3). Đây là lý do P3 không đứng chờ P4.
"""

from __future__ import annotations

import pytest

from backend.discourse import classifier
from backend.discourse.threads import build_threads, load_posts

# ---------- Fixture ----------


@pytest.fixture(scope="module")
def real_posts():
    """Post thật của Quân. Số liệu chốt trong crawl_docs.md §1."""
    try:
        return load_posts()
    except FileNotFoundError:
        pytest.skip("Chưa có data/raw/social_posts.json")


def _thread(*posts):
    return list(posts)


def _post(post_id, content="nội dung", parent_id=None, created="2025-12-10T02:00:00+00:00"):
    return {
        "post_id": post_id,
        "platform": "vnexpress_comment",
        "url": "https://vnexpress.net/x-1234567.html",
        "author_hash": "deadbeefdeadbeef",
        "content": content,
        "created_at": created,
        "engagement": 0,
        "parent_id": parent_id,
    }


# ---------- Gom luồng ----------


def test_thread_numbers_match_handover(real_posts):
    """Số liệu sau khi thu hẹp phạm vi (bỏ 135 post VAT, re-root reply mồ côi).
    Lệch = gom luồng sai, mọi thứ sau đó sai theo."""
    threads = build_threads(real_posts)
    debated = [t for t in threads.values() if len(t) > 1]

    assert len(real_posts) == 3186
    assert len(threads) == 1459
    assert len(debated) == 296
    assert max(len(t) for t in threads.values()) == 87


def test_all_replies_live_in_debated_threads(real_posts):
    """296 luồng tranh luận phải chứa TOÀN BỘ 1.727 reply (sau khi thu hẹp phạm vi).

    Đây là lý do cắt việc thì cắt luồng 1-post trước: chúng không chứa reply nào.
    """
    threads = build_threads(real_posts)
    replies = sum(1 for p in real_posts if p.get("parent_id"))
    in_debated = sum(len(t) - 1 for t in threads.values() if len(t) > 1)

    assert replies == 1727
    assert in_debated == replies


def test_root_comes_first_in_thread(real_posts):
    """Gốc luôn ở đầu luồng — render_thread_for_llm dựa vào đó."""
    for thread in build_threads(real_posts).values():
        assert thread[0].get("parent_id") is None or len(thread) == 1


def test_orphan_reply_becomes_own_thread():
    """Reply mồ côi -> luồng riêng, KHÔNG bị vứt.

    Xảy ra khi crawl cắt giữa chừng. Thà mất ngữ cảnh còn hơn mất post.
    """
    posts = [_post("vne-1"), _post("vne-99", parent_id="vne-KHONG-TON-TAI")]
    threads = build_threads(posts)

    assert set(threads) == {"vne-1", "vne-99"}
    assert sum(len(t) for t in threads.values()) == 2


def test_no_post_lost_when_grouping(real_posts):
    """Tổng post sau khi gom == tổng post trước khi gom. Không mất, không nhân đôi."""
    threads = build_threads(real_posts)
    grouped = [p["post_id"] for t in threads.values() for p in t]

    assert len(grouped) == len(real_posts)
    assert len(set(grouped)) == len(real_posts)


# ---------- Render cho LLM ----------


def test_render_keeps_every_post_id():
    """LLM phải thấy đủ post_id, nếu không nó không thể trả đủ."""
    thread = _thread(_post("vne-1"), _post("vne-2", parent_id="vne-1"))
    rendered = classifier.render_thread_for_llm(thread)

    assert "post_id=vne-1" in rendered
    assert "post_id=vne-2" in rendered
    assert "[GỐC]" in rendered and "[TRẢ LỜI]" in rendered


def test_render_gives_reply_its_root_context():
    """Lý do tồn tại của cả thiết kế gộp luồng: reply phải thấy nội dung gốc.

    "Rất chính xác" (74 like) đọc riêng là rỗng.
    """
    thread = _thread(
        _post("vne-59955349", "Không rõ ràng giữa doanh thu và thu nhập"),
        _post("vne-59955350", "Rất chính xác", parent_id="vne-59955349"),
    )
    rendered = classifier.render_thread_for_llm(thread)

    assert "doanh thu và thu nhập" in rendered
    assert "Rất chính xác" in rendered


# ---------- classify_posts ----------


class FakeLLM:
    """Thay backend.core.llm. Ghi lại custom_id đã nhận để test kiểm chứng."""

    def __init__(self, responses, *, shuffle=False):
        self.responses = responses
        self.shuffle = shuffle
        self.seen_custom_ids = []
        self.calls = 0

    def load_prompt(self, name):
        return f"<hướng dẫn {name}>"

    def extract_batch(self, items, schema):
        self.calls += 1
        self.seen_custom_ids.append([cid for cid, _ in items])
        out = {cid: self.responses.get(cid) for cid, _ in items if cid in self.responses}
        if self.shuffle:  # Batches trả về KHÔNG theo thứ tự gửi
            out = dict(reversed(list(out.items())))
        return out


@pytest.fixture
def fake_llm(monkeypatch):
    def install(responses, **kw):
        fake = FakeLLM(responses, **kw)
        monkeypatch.setattr(classifier.llm, "extract_batch", fake.extract_batch)
        monkeypatch.setattr(classifier.llm, "load_prompt", fake.load_prompt)
        return fake

    return install


def test_custom_id_is_thread_id_not_post_id(fake_llm):
    """custom_id PHẢI là thread_id. (crawl_docs.md §7.2 rủi ro 2)

    Dùng post_id thì 1 luồng lỗi = mất 90 post mà retry không biết gọi lại cái gì.
    """
    posts = [_post("vne-1"), _post("vne-2", parent_id="vne-1")]
    fake = fake_llm({
        "vne-1": {"posts": [
            {"post_id": "vne-1", "topic": "khac", "is_legal_claim": False, "claims": []},
            {"post_id": "vne-2", "topic": "khac", "is_legal_claim": False, "claims": []},
        ]}
    })
    classifier.classify_posts(posts)

    assert fake.seen_custom_ids[0] == ["vne-1"]  # 1 custom_id cho cả luồng 2 post


def test_results_keyed_by_custom_id_not_order(fake_llm):
    """Batches trả về KHÔNG theo thứ tự gửi -> zip theo index là sai.

    Fake cố tình đảo ngược thứ tự trả về.
    """
    posts = [_post("vne-1"), _post("vne-2")]
    fake_llm(
        {
            "vne-1": {"posts": [{"post_id": "vne-1", "topic": "thue_khoan",
                                 "is_legal_claim": True, "claims": []}]},
            "vne-2": {"posts": [{"post_id": "vne-2", "topic": "hoa_don_chung_tu",
                                 "is_legal_claim": False, "claims": []}]},
        },
        shuffle=True,
    )
    out = classifier.classify_posts(posts)

    assert out["vne-1"]["topic"] == "thue_khoan"
    assert out["vne-2"]["topic"] == "hoa_don_chung_tu"


def test_claim_id_is_deterministic(fake_llm):
    """Chạy lại phải ra cùng claim_id, nếu không eval lệch."""
    posts = [_post("vne-1")]
    responses = {
        "vne-1": {"posts": [{
            "post_id": "vne-1", "topic": "nguong_doanh_thu", "is_legal_claim": True,
            "claims": ["Ngưỡng là 500 triệu", "Chỉ phần vượt bị tính thuế"],
        }]}
    }
    fake_llm(responses)
    first = classifier.classify_posts(posts)
    fake_llm(responses)
    second = classifier.classify_posts(posts)

    assert [c["claim_id"] for c in first["vne-1"]["claims"]] == ["vne-1-c0", "vne-1-c1"]
    assert first == second


def test_missing_post_triggers_retry(fake_llm):
    """LLM bỏ sót post trong luồng dài -> phải gọi lại. (crawl_docs.md §7.2 rủi ro 1)

    Không kiểm số lượng là mất post trong IM LẶNG — không lỗi, không cảnh báo.
    """
    posts = [_post("vne-1"), _post("vne-2", parent_id="vne-1")]
    fake = fake_llm({
        "vne-1": {"posts": [  # thiếu vne-2
            {"post_id": "vne-1", "topic": "khac", "is_legal_claim": False, "claims": []},
        ]}
    })
    classifier.classify_posts(posts)

    assert fake.calls > 1, "bỏ sót post mà không gọi lại"


def test_retry_only_sends_missing_posts(fake_llm):
    """Gọi lại CHỈ phần thiếu, không gửi lại cả luồng — luồng 90 post thì đắt."""
    posts = [_post("vne-1"), _post("vne-2", parent_id="vne-1")]
    fake = fake_llm({
        "vne-1": {"posts": [
            {"post_id": "vne-1", "topic": "khac", "is_legal_claim": False, "claims": []},
        ]}
    })
    classifier.classify_posts(posts)

    assert fake.calls == classifier.MAX_RETRY_ROUNDS + 1
    assert fake.seen_custom_ids[1] == ["vne-1"]  # vẫn key theo thread_id


def test_survives_thread_llm_never_answers(fake_llm):
    """Luồng LLM không trả gì -> hàm vẫn chạy xong, post khác vẫn có kết quả."""
    posts = [_post("vne-1"), _post("vne-2")]
    fake_llm({
        "vne-2": {"posts": [{"post_id": "vne-2", "topic": "khac",
                             "is_legal_claim": False, "claims": []}]}
    })
    out = classifier.classify_posts(posts)

    assert "vne-2" in out
    assert "vne-1" not in out  # mất, nhưng có báo — không giả vờ thành công


def test_topic_enum_is_closed():
    """Enum đóng: LLM tự đặt tên chủ đề -> /trends vỡ vì 50 biến thể đồng nghĩa."""
    with pytest.raises(ValueError):
        classifier.PostClassification(post_id="vne-1", topic="thue_gi_do_moi")
