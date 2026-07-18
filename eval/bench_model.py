"""[P1] Benchmark extractor cho MỘT model cụ thể, trên 30 node gold.

Chạy:  python eval/bench_model.py <model_name>
Lưu:   eval/bench_<model_name>.json

Dùng để so sánh nhiều model. Model truyền qua env LLM_MODEL (ghi đè .env).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL = sys.argv[1] if len(sys.argv) > 1 else None
if MODEL:
    os.environ["LLM_MODEL"] = MODEL  # ghi de truoc khi import config

from backend.ingestion.extractor import extract_nodes  # noqa: E402
from backend.core.config import get_settings  # noqa: E402
from eval.benchmark_p1 import _prf, _match_sets, _similar, ENTITY_FIELDS, MATCH_THRESHOLD  # noqa: E402


def main() -> None:
    model = get_settings().llm_model
    gold = {}
    for line in (ROOT / "eval/gold_entities.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(line)
        if "node_id" in o:
            gold[o["node_id"]] = o

    # text goc cho 30 node gold
    import glob
    txt = {}
    for f in glob.glob(str(ROOT / "data/processed/qlt*.json")) + glob.glob(str(ROOT / "data/processed/tncn*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for a in d["articles"]:
            txt[a["article_id"]] = a["text"]
            for k in a["clauses"]:
                txt[k["clause_id"]] = k["text"]
                for p in k["points"]:
                    txt[p["point_id"]] = p["text"]

    nodes = [(nid, txt[nid]) for nid in gold]
    print(f"  Model: {model} | trích {len(nodes)} node gold (gộp node, prompt EN)...")
    t0 = time.time()
    pred = extract_nodes(nodes, doc_id="gold")
    dt = time.time() - t0

    agg = {f: {"tp": 0, "fp": 0, "fn": 0} for f in ENTITY_FIELDS}
    empty_tot = empty_ok = pen_tot = pen_ok = 0
    for nid, g in gold.items():
        p = pred.get(nid, {})
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

    out = {
        "model": model, "n_gold": len(gold), "seconds": round(dt, 1),
        "fields": fields, "micro": micro, "macro_f1": macro_f1,
        "hallucination_rate": round(micro["fp"] / total_pred, 4) if total_pred else 0.0,
        "empty_correct_rate": round(empty_ok / empty_tot, 4) if empty_tot else None,
        "empty_total": empty_tot,
        "penalty_type_accuracy": round(pen_ok / pen_tot, 4) if pen_tot else None,
        "penalty_total": pen_tot,
    }
    safe = model.replace("/", "_")
    (ROOT / f"eval/results/bench_{safe}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  {dt:.0f}s | MicroF1={micro['f1']:.0%} P={micro['precision']:.0%} R={micro['recall']:.0%} "
          f"Macro={macro_f1:.0%} Hall={out['hallucination_rate']:.0%} "
          f"Empty={out['empty_correct_rate']:.0%} PenType={out['penalty_type_accuracy']:.0%}")
    print(f"  -> eval/results/bench_{safe}.json")


if __name__ == "__main__":
    main()
