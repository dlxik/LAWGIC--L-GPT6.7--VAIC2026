"""[P1 benchmark] Đo parser (tất định) + extractor (LLM).

File RIÊNG của P1. eval/run_eval.py là của P3 (đo claim/verdict) — không đụng.

Hai bài toán KHÁC BẢN CHẤT -> hai cách đo khác nhau:

  PARSER    tất định  -> có "đáp án đúng" khách quan (văn bản tự khai số Điều)
                      -> đối chiếu tự động, KHÔNG cần người gán nhãn
  EXTRACTOR LLM       -> không có đáp án máy
                      -> gán nhãn tay (eval/gold_entities.jsonl), so P/R/F1

Metrics chọn theo đúng dạng bài:
  - Entity extraction = so khớp TẬP HỢP span tự do -> Precision/Recall/F1,
    không dùng accuracy (accuracy vô nghĩa khi output là tập hợp).
  - Micro F1 (gộp mọi span) + Macro F1 (trung bình theo trường) — báo cả hai vì
    micro thiên về trường nhiều dữ liệu, macro coi mọi trường như nhau.
  - Hallucination rate = FP / tổng span trích — chống LLM bịa (quan trọng nhất
    với văn bản luật: bịa chủ thể = sai lệch pháp lý).
  - Empty-correct rate — node đáng rỗng thì LLM có trả rỗng không (chống LLM lười
    nặn bừa cho đủ).
  - Penalty type accuracy — type chế tài gán đúng enum không (chống dồn vào OTHER).

Chạy:  python eval/benchmark_p1.py
"""

from __future__ import annotations

import glob
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ingestion.parser import validate  # noqa: E402

ENTITY_FIELDS = [
    "subjects", "obligations", "rights", "prohibitions", "deadlines", "references",
    "tax_rates", "tax_base", "exemptions",  # dac thu luat thue
]
MATCH_THRESHOLD = 0.60  # nguong tuong dong coi 2 span la "khop"


# ---------------------------------------------------------------------------
# PARSER — đối chiếu tự động, không cần gold
# ---------------------------------------------------------------------------


def _reconstruct_raw(doc: dict) -> str:
    """Ghép text các node lại để validate() đo coverage. Xấp xỉ văn bản gốc."""
    parts = []
    for a in doc["articles"]:
        parts.append(f"Điều {a['number']}. {a['heading']}")
        if a["text"]:
            parts.append(a["text"])
        for k in a["clauses"]:
            parts.append(f"{k['number']}. {k['text']}")
            for p in k["points"]:
                parts.append(f"{p['letter']}) {p['text']}")
    return "\n".join(parts)


def benchmark_parser() -> dict:
    result = {"documents": {}}
    tot_nodes = tot_err = 0
    recall_sum = 0.0
    n = 0
    for path in sorted(glob.glob(str(ROOT / "data/processed/qlt*.json")) +
                       glob.glob(str(ROOT / "data/processed/tncn*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        errors = validate(doc, _reconstruct_raw(doc))

        n_art = len(doc["articles"])
        n_node = (n_art + sum(len(a["clauses"]) for a in doc["articles"])
                  + sum(len(k["points"]) for a in doc["articles"] for k in a["clauses"]))
        max_art = max((a["number"] for a in doc["articles"]), default=0)
        recall = n_art / max_art if max_art else 1.0

        result["documents"][doc["doc_id"]] = {
            "nodes": n_node, "articles": n_art,
            "article_recall": round(recall, 4),
            "invariant_errors": len(errors), "errors": errors[:5],
        }
        tot_nodes += n_node
        tot_err += len(errors)
        recall_sum += recall
        n += 1

    result["totals"] = {
        "nodes": tot_nodes, "invariant_errors": tot_err,
        "article_recall": round(recall_sum / n, 4) if n else 0.0,
    }
    return result


# ---------------------------------------------------------------------------
# EXTRACTOR — so LLM với gold, P/R/F1
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower().strip()
    s = re.sub(r"[.,;:\"'()]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _similar(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:  # luat hay co "phai X" vs "X" -> chua nhau = khop
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _match_sets(gold: list[str], pred: list[str]) -> tuple[int, int, int]:
    """Ghép greedy 1-1 hai tập span -> (TP, FP, FN)."""
    used = set()
    tp = 0
    for g in gold:
        best_j, best = -1, MATCH_THRESHOLD
        for j, p in enumerate(pred):
            if j in used:
                continue
            sim = _similar(g, p)
            if sim >= best:
                best, best_j = sim, j
        if best_j >= 0:
            used.add(best_j)
            tp += 1
    return tp, len(pred) - len(used), len(gold) - tp


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def benchmark_extractor() -> dict:
    gold = {}
    for line in (ROOT / "eval/gold_entities.jsonl").read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        if "node_id" in obj:
            gold[obj["node_id"]] = obj

    pred = {}
    for f in glob.glob(str(ROOT / "data/processed/entities_*.json")):
        for e in json.loads(Path(f).read_text(encoding="utf-8")):
            pred[e["node_id"]] = e

    agg = {f: {"tp": 0, "fp": 0, "fn": 0} for f in ENTITY_FIELDS}
    empty_tot = empty_ok = pen_tot = pen_ok = missing = 0

    for nid, g in gold.items():
        p = pred.get(nid)
        if p is None:
            missing += 1
            continue
        for field in ENTITY_FIELDS:
            tp, fp, fn = _match_sets(g.get(field, []), p.get(field, []))
            agg[field]["tp"] += tp
            agg[field]["fp"] += fp
            agg[field]["fn"] += fn

        g_empty = not any(g.get(f) for f in ENTITY_FIELDS) and not g.get("penalties")
        p_empty = not any(p.get(f) for f in ENTITY_FIELDS) and not p.get("penalties")
        if g_empty:
            empty_tot += 1
            empty_ok += int(p_empty)

        for gp in g.get("penalties", []):
            pen_tot += 1
            for pp in p.get("penalties", []):
                if _similar(gp.get("text", ""), pp.get("text", "")) >= MATCH_THRESHOLD:
                    pen_ok += int(gp.get("type") == pp.get("type"))
                    break

    fields = {f: _prf(**agg[f]) for f in ENTITY_FIELDS}
    micro = _prf(sum(agg[f]["tp"] for f in ENTITY_FIELDS),
                 sum(agg[f]["fp"] for f in ENTITY_FIELDS),
                 sum(agg[f]["fn"] for f in ENTITY_FIELDS))
    macro_f1 = round(sum(fields[f]["f1"] for f in ENTITY_FIELDS) / len(ENTITY_FIELDS), 4)
    total_pred = micro["tp"] + micro["fp"]

    return {
        "n_gold": len(gold), "missing_from_pred": missing,
        "fields": fields, "micro": micro, "macro_f1": macro_f1,
        "hallucination_rate": round(micro["fp"] / total_pred, 4) if total_pred else 0.0,
        "empty_correct_rate": round(empty_ok / empty_tot, 4) if empty_tot else None,
        "empty_total": empty_tot,
        "penalty_type_accuracy": round(pen_ok / pen_tot, 4) if pen_tot else None,
        "penalty_total": pen_tot,
    }


def main() -> None:
    parser = benchmark_parser()
    ext = benchmark_extractor()

    print("\n" + "═" * 62)
    print("  PARSER (tất định, đối chiếu tự động — không cần gold)")
    print("═" * 62)
    for did, r in parser["documents"].items():
        print(f"  {did:9s} {r['nodes']:>5,} node | article_recall {r['article_recall']:>4.0%} "
              f"| {r['invariant_errors']} lỗi bất biến")
    t = parser["totals"]
    print(f"  {'─' * 58}")
    print(f"  TỔNG      {t['nodes']:>5,} node | article_recall {t['article_recall']:>4.0%} "
          f"| {t['invariant_errors']} lỗi")

    print("\n" + "═" * 62)
    print(f"  EXTRACTOR (voting hybrid 20b∩gemma + 20b penalties, {ext['n_gold']} node gold gán tay)")
    print("═" * 62)
    print(f"  {'trường':13s} {'P':>5s} {'R':>5s} {'F1':>5s}   tp/fp/fn")
    for f, m in ext["fields"].items():
        print(f"  {f:13s} {m['precision']:>4.0%} {m['recall']:>4.0%} {m['f1']:>4.0%}   "
              f"{m['tp']}/{m['fp']}/{m['fn']}")
    print(f"  {'─' * 40}")
    mi = ext["micro"]
    print(f"  {'MICRO':13s} {mi['precision']:>4.0%} {mi['recall']:>4.0%} {mi['f1']:>4.0%}")
    print(f"  MACRO F1           : {ext['macro_f1']:.0%}")
    print(f"  Hallucination rate : {ext['hallucination_rate']:.0%}")
    if ext["empty_correct_rate"] is not None:
        print(f"  Empty-correct rate : {ext['empty_correct_rate']:.0%} ({ext['empty_total']} node)")
    if ext["penalty_type_accuracy"] is not None:
        print(f"  Penalty type acc   : {ext['penalty_type_accuracy']:.0%} ({ext['penalty_total']} penalty)")

    (ROOT / "eval/results/benchmark_result.json").write_text(
        json.dumps({"parser": parser, "extractor": ext}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\n  -> eval/results/benchmark_result.json")


if __name__ == "__main__":
    main()
