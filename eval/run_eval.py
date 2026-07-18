"""[P3] Đo độ chính xác. BGK CHẮC CHẮN hỏi "làm sao biết phân loại đúng?"

Chạy: python eval/run_eval.py
Đọc eval/gold_set.jsonl -> chạy pipeline (link_claim + verdict_for_claim) trên từng
claim -> in accuracy / per-class F1 / confusion matrix + tỷ lệ citation đúng.

Mục tiêu tối thiểu để demo: 50 claim gắn nhãn tay, verdict accuracy >= 80%.

BÁO VERDICT VÀ CITATION TÁCH RIÊNG. Hai con số trả lời hai câu khác nhau:
  verdict_accuracy  — phân loại đúng/sai có chuẩn không
  citation_accuracy — có trỏ đúng điều luật làm căn cứ không
Gộp lại là mất điểm: model có thể đoán đúng verdict mà trích sai điều, hoặc ngược lại.

IN CẢ BASELINE (đoán bừa nhãn phổ biến nhất). Không có baseline thì 80% vô nghĩa.

CẦN core/llm.py của P4. Chưa có -> chạy sẽ báo NotImplementedError rõ ràng.
Test trong tests/test_eval.py chạy bằng fake, không cần key.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.discourse import linker, misinformation  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLD_FILE = ROOT / "eval" / "gold_set.jsonl"
VERDICTS = ["ACCURATE", "PARTIALLY_INACCURATE", "INACCURATE", "UNVERIFIABLE"]
SKIP = "SKIP"


def load_gold() -> list[dict]:
    if not GOLD_FILE.exists() or not GOLD_FILE.read_text(encoding="utf-8").strip():
        sys.exit("Gold set trống. Chạy: python scripts/make_worksheet.py rồi gắn nhãn.")
    rows = [
        json.loads(line)
        for line in GOLD_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    labelled = [r for r in rows if r.get("expected_verdict") not in (SKIP, "TODO", None)]
    if not labelled:
        sys.exit("Gold set chưa gắn nhãn. Xem eval/WORKSHEET.md.")
    return labelled


def run_pipeline(claim_text: str, topic: str = "") -> dict:
    """Chạy đúng pipeline thật: link_claim -> verdict_for_claim.

    Điểm mấu chốt của eval: đo pipeline THẬT, không phải một hàm riêng chỉ dùng để
    chấm điểm. Nếu ở đây gọi khác lúc chạy production thì con số nói dối.

    Một claim làm model trả JSON hỏng KHÔNG được làm sập cả eval (llm.py hiện ném
    lỗi không retry). Bắt lỗi -> claim đó tính UNVERIFIABLE, đúng tinh thần 'không
    xử được thì không kết luận', và eval vẫn ra số cho 47 claim còn lại.
    """
    try:
        citations = linker.link_claim(claim_text, topic)
    except Exception as exc:  # noqa: BLE001
        print(f"    ! link lỗi: {exc}")
        citations = []
    try:
        verdict = misinformation.verdict_for_claim(claim_text, citations)
    except Exception as exc:  # noqa: BLE001
        print(f"    ! verdict lỗi: {exc}")
        verdict = {"verdict": "UNVERIFIABLE"}
    return {"verdict": verdict["verdict"], "citations": [c["node_id"] for c in citations]}


def _f1_per_class(gold: list[str], pred: list[str]) -> dict[str, dict]:
    stats = {}
    for cls in VERDICTS:
        tp = sum(g == cls and p == cls for g, p in zip(gold, pred))
        fp = sum(g != cls and p == cls for g, p in zip(gold, pred))
        fn = sum(g == cls and p != cls for g, p in zip(gold, pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        stats[cls] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    return stats


def _confusion(gold: list[str], pred: list[str]) -> dict:
    matrix = defaultdict(Counter)
    for g, p in zip(gold, pred):
        matrix[g][p] += 1
    return matrix


def _ci95(acc: float, n: int) -> float:
    return 1.96 * math.sqrt(max(acc * (1 - acc), 1e-9) / n) if n else 0.0


def evaluate(gold: list[dict] | None = None) -> dict:
    """Trả {verdict_accuracy, citation_accuracy, per_class_f1, confusion_matrix, ...}."""
    gold = gold if gold is not None else load_gold()

    gold_verdicts, pred_verdicts = [], []
    citation_hits = citation_total = 0

    total = len(gold)
    for i, row in enumerate(gold, 1):
        print(f"  [{i}/{total}] {row['text'][:50]}...", flush=True)
        result = run_pipeline(row["text"], row.get("topic", ""))
        gold_verdicts.append(row["expected_verdict"])
        pred_verdicts.append(result["verdict"])

        # citation_accuracy chỉ tính trên claim CÓ expected_citation (loại
        # UNVERIFIABLE không căn cứ). Trộn claim không citation vào sẽ thổi phồng.
        expected_cite = row.get("expected_citation", "")
        if expected_cite:
            citation_total += 1
            if expected_cite in result["citations"]:
                citation_hits += 1

    n = len(gold)
    correct = sum(g == p for g, p in zip(gold_verdicts, pred_verdicts))
    verdict_acc = correct / n if n else 0.0
    citation_acc = citation_hits / citation_total if citation_total else 0.0

    dist = Counter(gold_verdicts)
    top_verdict, top_n = dist.most_common(1)[0]

    return {
        "n": n,
        "verdict_accuracy": verdict_acc,
        "verdict_ci95": _ci95(verdict_acc, n),
        "citation_accuracy": citation_acc,
        "citation_total": citation_total,
        "baseline": top_n / n if n else 0.0,
        "baseline_label": top_verdict,
        "per_class_f1": _f1_per_class(gold_verdicts, pred_verdicts),
        "confusion_matrix": {
            g: dict(row) for g, row in _confusion(gold_verdicts, pred_verdicts).items()
        },
    }


def print_report(result: dict) -> None:
    n = result["n"]
    print(f"\n  === EVAL trên {n} claim gold ===\n")
    print(f"  verdict_accuracy  : {result['verdict_accuracy']:.1%}  (±{result['verdict_ci95']:.0%})")
    print(f"  citation_accuracy : {result['citation_accuracy']:.1%}"
          f"  (trên {result['citation_total']} claim có căn cứ)")
    print(f"  baseline (đoán bừa {result['baseline_label']!r}): {result['baseline']:.1%}")
    gap = result["verdict_accuracy"] - result["baseline"]
    print(f"  -> vượt baseline {gap:+.1%}"
          + ("  ✓" if gap > 0.1 else "  ⚠ chưa vượt rõ, xem confusion matrix"))

    print("\n  Per-class F1:")
    print(f"    {'verdict':<24}{'P':>6}{'R':>6}{'F1':>7}{'n':>5}")
    for cls, s in result["per_class_f1"].items():
        print(f"    {cls:<24}{s['precision']:>6.2f}{s['recall']:>6.2f}{s['f1']:>7.2f}{s['support']:>5}")

    print("\n  Confusion matrix (hàng = gold, cột = dự đoán):")
    print(f"    {'gold/pred':<22}" + "".join(f"{c[:4]:>6}" for c in VERDICTS))
    for g in VERDICTS:
        row = result["confusion_matrix"].get(g, {})
        print(f"    {g:<22}" + "".join(f"{row.get(p, 0):>6}" for p in VERDICTS))
    print()


def main() -> None:
    print_report(evaluate())


if __name__ == "__main__":
    main()
