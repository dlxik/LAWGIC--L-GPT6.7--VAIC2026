"""[eval] Chấm Q&A kiểu RAGAS bằng SEMANTIC (FPT embedding) — công bằng hơn exact-match.

Vì sao KHÔNG dùng package RAGAS: RAGAS 0.2/0.4 xung đột langchain 1.x (thử 4 combo
đều deadlock). Và RAGAS-judge chạy gpt-oss-20b (model nhỏ) làm judge kém tin cậy.
=> Tính THẲNG các metric semantic của RAGAS bằng cosine trên FPT Vietnamese_Embedding
— đúng tinh thần "so nghĩa, không so chữ", đáng tin hơn LLM-judge yếu.

Metric (0..1, cao = tốt), ánh xạ RAGAS:
  answer_similarity   ~ answer_correctness : cos(answer, ground_truth)
  answer_relevancy    ~ answer_relevancy   : cos(answer, question)
  context_recall      ~ context_recall     : max cos(ground_truth, context_i)  (context có chứa đáp án?)
  faithfulness        ~ faithfulness       : max cos(answer, context_i)         (answer bám context?)

Chạy (venv project):  python eval/qa_semantic_eval.py <ragas_dataset.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.core import llm  # noqa: E402

EMB_MODEL = "Vietnamese_Embedding"


def embed(texts: list[str]) -> np.ndarray:
    vecs = llm.embed(texts, model=EMB_MODEL)
    m = np.asarray(vecs, dtype=np.float32)
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "ragas_dataset.json"
    rows = json.load(open(path))

    # gom mọi text -> embed 1 lượt (batched trong llm.embed)
    per = []
    flat: list[str] = []
    for r in rows:
        ctx = r["contexts"][:8]
        idx = {
            "q": len(flat), "a": len(flat) + 1, "gt": len(flat) + 2,
            "ctx": list(range(len(flat) + 3, len(flat) + 3 + len(ctx))),
        }
        flat += [r["question"], r["answer"], r["ground_truth"], *ctx]
        per.append(idx)

    E = embed(flat)

    ans_sim, ans_rel, ctx_rec, faith = [], [], [], []
    for idx in per:
        q, a, gt = E[idx["q"]], E[idx["a"]], E[idx["gt"]]
        C = E[idx["ctx"]] if idx["ctx"] else np.zeros((1, E.shape[1]), np.float32)
        ans_sim.append(float(a @ gt))
        ans_rel.append(float(a @ q))
        ctx_rec.append(float((C @ gt).max()))
        faith.append(float((C @ a).max()))

    def avg(x):
        return sum(x) / len(x)

    print(f"=== Q&A SEMANTIC EVAL (kiểu RAGAS, embedding, {len(rows)} mẫu) ===")
    print(f"  answer_similarity  (~answer_correctness): {avg(ans_sim):.2f}")
    print(f"  answer_relevancy                        : {avg(ans_rel):.2f}")
    print(f"  context_recall                          : {avg(ctx_rec):.2f}")
    print(f"  faithfulness                            : {avg(faith):.2f}")
    print("\n  (thang 0..1; cos>=0.6 ~ khớp nghĩa tốt cho tiếng Việt pháp lý)")


if __name__ == "__main__":
    main()
