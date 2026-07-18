"""[P3] Test cho eval/run_eval.py.

Chạy:  pytest tests/test_eval.py -v      (không cần Neo4j / API key)

Khoá lại cách TÍNH con số — vì đây là con số P3 mang ra trước BGK. Sai công thức
metric mà không ai biết thì tệ hơn cả không có eval.
"""

from __future__ import annotations

import pytest

from eval import run_eval


def _gold(cid, text, verdict, citation=""):
    return {"claim_id": cid, "text": text, "expected_verdict": verdict,
            "expected_citation": citation, "topic": ""}


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Thay link_claim + verdict_for_claim bằng bảng tra cứng {text: (verdict, [nodes])}."""
    def install(table):
        def fake_link(claim_text, topic=""):
            _, nodes = table[claim_text]
            return [{"node_id": n, "node_label": "Clause", "display": n,
                     "text": "", "confidence": 0.9} for n in nodes]

        def fake_verdict(claim_text, citations):
            verdict, _ = table[claim_text]
            return {"verdict": verdict, "confidence": 0.9, "explanation": "", "correct_statement": ""}

        monkeypatch.setattr(run_eval.linker, "link_claim", fake_link)
        monkeypatch.setattr(run_eval.misinformation, "verdict_for_claim", fake_verdict)

    return install


def test_perfect_pipeline_scores_100(fake_pipeline):
    gold = [
        _gold("g1", "a", "INACCURATE", "tncn2025-d7-k1"),
        _gold("g2", "b", "ACCURATE", "tncn2025-d7-k3-a"),
    ]
    fake_pipeline({
        "a": ("INACCURATE", ["tncn2025-d7-k1"]),
        "b": ("ACCURATE", ["tncn2025-d7-k3-a"]),
    })
    result = run_eval.evaluate(gold)
    assert result["verdict_accuracy"] == 1.0
    assert result["citation_accuracy"] == 1.0


def test_verdict_and_citation_scored_independently(fake_pipeline):
    """Đúng verdict nhưng SAI citation -> verdict_acc cao, citation_acc thấp.

    Đây là lý do báo tách hai con số: gộp lại thì lỗi này biến mất.
    """
    gold = [_gold("g1", "a", "INACCURATE", "tncn2025-d7-k1")]
    fake_pipeline({"a": ("INACCURATE", ["qlt2019-d51"])})  # verdict đúng, citation sai
    result = run_eval.evaluate(gold)
    assert result["verdict_accuracy"] == 1.0
    assert result["citation_accuracy"] == 0.0


def test_unverifiable_excluded_from_citation_metric(fake_pipeline):
    """Claim UNVERIFIABLE (không expected_citation) KHÔNG được tính vào citation_acc.

    Trộn vào sẽ thổi phồng mẫu số bằng những claim vốn không có căn cứ để trỏ.
    """
    gold = [
        _gold("g1", "a", "INACCURATE", "tncn2025-d7-k1"),
        _gold("g2", "b", "UNVERIFIABLE", ""),
    ]
    fake_pipeline({
        "a": ("INACCURATE", ["tncn2025-d7-k1"]),
        "b": ("UNVERIFIABLE", []),
    })
    result = run_eval.evaluate(gold)
    assert result["citation_total"] == 1  # chỉ g1, không tính g2


def test_baseline_is_majority_class(fake_pipeline):
    gold = [
        _gold("g1", "a", "INACCURATE"), _gold("g2", "b", "INACCURATE"),
        _gold("g3", "c", "INACCURATE"), _gold("g4", "d", "ACCURATE"),
    ]
    fake_pipeline({k: ("ACCURATE", []) for k in ["a", "b", "c", "d"]})
    result = run_eval.evaluate(gold)
    assert result["baseline_label"] == "INACCURATE"
    assert result["baseline"] == 0.75  # 3/4


def test_confusion_matrix_counts(fake_pipeline):
    gold = [
        _gold("g1", "a", "ACCURATE"),
        _gold("g2", "b", "ACCURATE"),
    ]
    fake_pipeline({
        "a": ("ACCURATE", []),               # đúng
        "b": ("INACCURATE", []),             # gold ACCURATE, dự đoán INACCURATE
    })
    result = run_eval.evaluate(gold)
    cm = result["confusion_matrix"]
    assert cm["ACCURATE"]["ACCURATE"] == 1
    assert cm["ACCURATE"]["INACCURATE"] == 1


def test_f1_computed(fake_pipeline):
    gold = [_gold("g1", "a", "ACCURATE"), _gold("g2", "b", "ACCURATE")]
    fake_pipeline({"a": ("ACCURATE", []), "b": ("ACCURATE", [])})
    result = run_eval.evaluate(gold)
    assert result["per_class_f1"]["ACCURATE"]["f1"] == 1.0
    assert result["per_class_f1"]["ACCURATE"]["support"] == 2


def test_load_gold_skips_unlabelled():
    """load_gold bỏ SKIP và TODO — chỉ chấm claim đã gắn nhãn thật."""
    gold = run_eval.load_gold()
    assert all(r["expected_verdict"] in run_eval.VERDICTS for r in gold)
    assert len(gold) >= 30  # gold set sau thu hẹp phạm vi (3 lớp, bỏ VAT): 37 nhãn
