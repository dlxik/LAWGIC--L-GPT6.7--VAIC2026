"""[P3] Test cho backend/discourse/misinformation.py.

Chạy:  pytest tests/test_misinformation.py -v      (không cần Neo4j / API key)
"""

from __future__ import annotations


from backend.discourse import misinformation as mis


# ---------- verdict_for_claim ----------


def test_no_citation_is_unverifiable_without_llm(monkeypatch):
    """Không citation -> UNVERIFIABLE ngay, KHÔNG gọi LLM.

    Vừa đúng ngữ nghĩa (không căn cứ = chưa kiểm chứng được), vừa tiết kiệm 1 call.
    """
    def explode(*a, **k):
        raise AssertionError("không được gọi LLM khi không có citation")

    monkeypatch.setattr(mis.llm, "extract", explode)
    result = mis.verdict_for_claim("doanh thu 200tr phải nộp thuế", [])
    assert result["verdict"] == "UNVERIFIABLE"
    assert result["confidence"] == 0.0


def test_verdict_uses_llm_when_citations_present(monkeypatch):
    captured = {}

    def fake_samples(prompt, schema, *, n, temperature, system=None):
        captured["prompt"] = prompt
        captured["n"] = n
        return [schema(verdict="INACCURATE", confidence=0.9,
                       explanation="200 < 500", correct_statement="...")] * n

    monkeypatch.setattr(mis.llm, "extract_samples", fake_samples)
    monkeypatch.setattr(mis.llm, "load_prompt", lambda name: "<hd>")

    cites = [{"node_id": "tncn2025-d7-k1", "display": "Điều 7 Khoản 1",
              "text": "doanh thu năm từ 500 triệu trở xuống không phải nộp thuế"}]
    result = mis.verdict_for_claim("doanh thu 200tr phải nộp thuế", cites)

    assert result["verdict"] == "INACCURATE"
    assert captured["n"] == mis.VERDICT_SAMPLES     # self-consistency: nhiều mẫu
    assert "tncn2025-d7-k1" in captured["prompt"]   # điều luật được đưa vào prompt


def test_verdict_majority_vote_wins(monkeypatch):
    """Bỏ phiếu đa số: 3 PARTIAL vs 2 INACCURATE -> PARTIALLY_INACCURATE thắng."""
    from backend.discourse.misinformation import _VerdictResult

    def fake_samples(prompt, schema, *, n, temperature, system=None):
        return [
            _VerdictResult(verdict="PARTIALLY_INACCURATE", confidence=0.6),
            _VerdictResult(verdict="PARTIALLY_INACCURATE", confidence=0.7),
            _VerdictResult(verdict="PARTIALLY_INACCURATE", confidence=0.5),
            _VerdictResult(verdict="INACCURATE", confidence=0.95),
            _VerdictResult(verdict="INACCURATE", confidence=0.95),
        ]

    monkeypatch.setattr(mis.llm, "extract_samples", fake_samples)
    monkeypatch.setattr(mis.llm, "load_prompt", lambda name: "<hd>")

    cites = [{"node_id": "tncn2025-d7-k1", "display": "Điều 7 Khoản 1", "text": "..."}]
    result = mis.verdict_for_claim("claim", cites)
    assert result["verdict"] == "PARTIALLY_INACCURATE"  # 3 phiếu > 2, dù INAC confidence cao hơn


# ---------- cluster_misconceptions ----------


def _claim(cid, text, verdict, engagement=0, node="tncn2025-d7-k1", created="2025-12-10T00:00:00+00:00"):
    return {"claim_id": cid, "text": text, "verdict": verdict, "engagement": engagement,
            "created_at": created, "citations": [{"node_id": node}]}


def test_only_wrong_claims_clustered():
    """ACCURATE / UNVERIFIABLE không phải hiểu nhầm -> không vào cụm nào."""
    claims = [
        _claim("c1", "doanh thu 200tr phải nộp thuế", "INACCURATE"),
        _claim("c2", "doanh thu 500tr được miễn thuế", "ACCURATE"),
        _claim("c3", "VAT chồng thuế", "UNVERIFIABLE"),
    ]
    miscs = mis.cluster_misconceptions(claims)
    all_members = [cid for m in miscs for cid in m["member_claim_ids"]]
    assert "c1" in all_members
    assert "c2" not in all_members and "c3" not in all_members


def test_similar_wrong_claims_group_together():
    """Biến thể sát mặt chữ của cùng một tin đồn gom về 1 misconception.

    Clusterer TỪ VỰNG (char n-gram) — gom được cách diễn đạt gần giống, đúng kiểu
    tin đồn lan bằng việc người ta chép lại câu của nhau. Không kỳ vọng nó gom hai
    câu cùng nghĩa mà khác hẳn chữ (đó là việc của embedding ngữ nghĩa, để sau).
    """
    claims = [
        _claim("c1", "doanh thu 200 triệu một năm là phải đóng thuế rồi", "INACCURATE"),
        _claim("c2", "doanh thu 200 triệu một năm đã phải đóng thuế", "INACCURATE"),
        _claim("c3", "doanh thu 200 triệu một năm là phải nộp thuế", "INACCURATE"),
    ]
    miscs = mis.cluster_misconceptions(claims)
    assert len(miscs) == 1
    assert miscs[0]["count"] == 3


def test_unrelated_wrong_claims_stay_separate():
    """Hai tin đồn KHÁC nhau không bị gom nhầm về một cụm."""
    claims = [
        _claim("c1", "doanh thu 200 triệu phải đóng thuế ngay", "INACCURATE"),
        _claim("c2", "hộ kinh doanh vẫn đóng thuế khoán như luật cũ", "INACCURATE"),
    ]
    miscs = mis.cluster_misconceptions(claims)
    assert len(miscs) == 2


def test_canonical_is_highest_engagement():
    """canonical_text = claim có engagement cao nhất trong cụm."""
    claims = [
        _claim("c1", "doanh thu 200 triệu một năm phải đóng thuế", "INACCURATE", engagement=5),
        _claim("c2", "doanh thu 200 triệu một năm là phải đóng thuế rồi", "INACCURATE", engagement=759),
    ]
    miscs = mis.cluster_misconceptions(claims)
    assert len(miscs) == 1
    assert miscs[0]["total_engagement"] == 764
    assert miscs[0]["canonical_text"] == "doanh thu 200 triệu một năm là phải đóng thuế rồi"


def test_empty_when_no_wrong_claims():
    assert mis.cluster_misconceptions([_claim("c1", "x", "ACCURATE")]) == []


# ---------- detect_trends ----------


def _misc(count, engagement, last_seen="2025-12-10T00:00:00+00:00"):
    return {"misconception_id": "m", "canonical_text": "tin đồn", "count": count,
            "total_engagement": engagement, "last_seen": last_seen, "contradicts": []}


def test_trend_window_empty_at_today():
    """Cửa sổ 48h tính từ HÔM NAY (2026-07) trả rỗng vì post cũ (2025-12).

    Đây là bug đã biết (crawl_docs.md §7.1) — test khoá lại để nhớ phải neo as_of.
    """
    miscs = [_misc(10, 1000, last_seen="2025-12-10T00:00:00+00:00")]
    alerts = mis.detect_trends(miscs, as_of="2026-07-17", window_hours=48, min_occurrences=5)
    assert alerts == []


def test_trend_appears_when_anchored_to_active_period():
    """Neo as_of về đúng lúc dư luận sôi -> misconception hiện ra."""
    miscs = [_misc(10, 1000, last_seen="2025-12-10T00:00:00+00:00")]
    alerts = mis.detect_trends(miscs, as_of="2025-12-11", window_hours=48, min_occurrences=5)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "HIGH"  # engagement 1000 >= 500


def test_below_threshold_filtered():
    miscs = [_misc(3, 1000, last_seen="2025-12-10T00:00:00+00:00")]
    alerts = mis.detect_trends(miscs, as_of="2025-12-11", window_hours=48, min_occurrences=5)
    assert alerts == []


def test_severity_by_engagement():
    assert mis._severity(600) == "HIGH"
    assert mis._severity(200) == "MEDIUM"
    assert mis._severity(10) == "LOW"


def test_trends_sorted_by_reach():
    miscs = [
        _misc(10, 50, last_seen="2025-12-10T00:00:00+00:00"),
        _misc(10, 900, last_seen="2025-12-10T00:00:00+00:00"),
    ]
    alerts = mis.detect_trends(miscs, as_of="2025-12-11", window_hours=48, min_occurrences=5)
    assert alerts[0]["misconception"]["total_engagement"] == 900
