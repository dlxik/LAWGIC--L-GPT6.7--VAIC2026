"""[P1] Trích 100 node gold bằng MỘT model, lưu SPAN THÔ (để hợp phiếu đa model).

Khác bench_model.py: file kia chỉ lưu số tổng (P/R/F1). Voting cần span thô của
từng model để tính giao (span cả hai model cùng trích).

Chạy:  python eval/bench_raw.py <model_name>
Lưu:   eval/results/rawpred_<model_name>.json   {node_id: {field: [span,...]}}
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL = sys.argv[1]
os.environ["LLM_MODEL"] = MODEL  # ghi đè trước khi import config

from backend.ingestion.extractor import extract_nodes  # noqa: E402
from backend.core.config import get_settings  # noqa: E402


def main() -> None:
    model = get_settings().llm_model
    gold = {}
    for line in (ROOT / "eval/gold_entities.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(line)
        if "node_id" in o:
            gold[o["node_id"]] = o

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
    print(f"  Model {model}: trích {len(nodes)} node gold...", flush=True)
    t0 = time.time()
    pred = extract_nodes(nodes, doc_id="gold")
    print(f"  xong {time.time() - t0:.0f}s", flush=True)

    safe = model.replace("/", "_")
    (ROOT / f"eval/results/rawpred_{safe}.json").write_text(
        json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> eval/results/rawpred_{safe}.json ({len(pred)} node)")


if __name__ == "__main__":
    main()
