"""[eval] Đánh giá endpoint Q&A trên eval/qa_gold.jsonl (50 câu gắn tay theo luật).

Chạy:  python eval/qa_eval.py           (cần API đang chạy ở :8000)

Đo các chiều TƯƠNG ĐƯƠNG RAGAS nhưng KHÔNG phụ thuộc RAGAS (RAGAS 0.4 xung đột
langchain 1.x trong env này) và không cần LLM-judge (gpt-oss-20b làm judge không
đáng tin):

  citation_accuracy   ~ RAGAS context recall: expected_citation có trong citations trả về
  answer_correctness  ~ RAGAS answer correctness: số/tỷ lệ trong ground_truth xuất
                        hiện trong answer (proxy keyword — khách quan, không cần judge)
  answerable_answered : câu trả được KHÔNG bị từ chối oan
  offtopic_refused    : câu lạc đề PHẢI bị từ chối (chống bịa)
  faithfulness        : mọi citation là node THẬT (endpoint đã validate -> ~100%)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Gọi handler /qa TRỰC TIẾP (không qua HTTP) -> bỏ qua rate-limit của API + nhanh hơn.
from backend.api.qa_endpoint import QARequest, qa as _qa_handler  # noqa: E402

GOLD = Path(__file__).resolve().parent / "qa_gold.jsonl"

_FACT = re.compile(r"\d+[.,]?\d*\s*%|\d+[.,]?\d*\s*(?:triệu|tỷ|nghìn)")


def ask(question: str, date: str | None = None) -> dict:
    return _qa_handler(QARequest(question=question, as_of_date=date)).model_dump()


def key_facts(text: str) -> set[str]:
    """Số + đơn vị/tỷ lệ trong ground_truth — dùng đối chiếu answer."""
    return {m.group(0).strip() for m in _FACT.finditer(text.lower())}


def _fact_in_answer(fact: str, answer: str) -> bool:
    a = answer.lower().replace(" ", "")
    return fact.replace(" ", "") in a


def main() -> None:
    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    answerable = [g for g in gold if g["type"] == "answerable"]
    offtopic = [g for g in gold if g["type"] == "offtopic"]

    cite_hit = cite_total = 0
    ans_ok = ans_total = 0
    answered = 0
    misses = []

    print(f"Chạy {len(answerable)} câu answerable...")
    for i, g in enumerate(answerable, 1):
        r = ask(g["question"])
        cites = [c["node_id"] for c in r.get("citations", [])]
        refused = r.get("mode") == "refused"
        if not refused:
            answered += 1

        if g["expected_citation"]:
            cite_total += 1
            if g["expected_citation"] in cites:
                cite_hit += 1
            else:
                misses.append((g["question"][:45], g["expected_citation"], cites[:2]))

        facts = key_facts(g["ground_truth"])
        if facts:
            ans_total += 1
            if any(_fact_in_answer(f, r.get("answer", "")) for f in facts):
                ans_ok += 1
        print(f"  [{i}/{len(answerable)}]", end="\r")
    print()

    print(f"Chạy {len(offtopic)} câu offtopic (phải từ chối)...")
    off_refused = sum(1 for g in offtopic if ask(g["question"]).get("mode") == "refused")

    def pct(a, b):
        return f"{a}/{b} = {a / b:.0%}" if b else "n/a"

    print("\n=== Q&A EVAL (eval/qa_gold.jsonl) ===")
    print(f"  citation_accuracy   : {pct(cite_hit, cite_total)}   (~ context recall)")
    print(f"  answer_correctness  : {pct(ans_ok, ans_total)}   (số/tỷ lệ đúng trong answer)")
    print(f"  answerable_answered : {pct(answered, len(answerable))}")
    print(f"  offtopic_refused    : {pct(off_refused, len(offtopic))}   (chống bịa)")
    if misses:
        print(f"\n  {len(misses)} câu citation TRƯỢT (retrieval/pick chưa ra điều đúng):")
        for q, exp, got in misses[:8]:
            print(f"    - {q}... | cần {exp} | ra {got}")


if __name__ == "__main__":
    main()
