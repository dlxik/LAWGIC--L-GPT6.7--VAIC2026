"""[P1] Trích TOÀN BỘ node của 3 văn bản bằng MỘT model, lưu có hậu tố.

Dùng để chạy model thứ 2 (gemma) phục vụ voting mà KHÔNG đè output model 1.

Chạy:  python scripts/run_full_model.py <model> <suffix>
Lưu:   data/processed/entities_<suffix>_<doc>.json
"""

import json
import os
import sys
import time

MODEL, SUFFIX = sys.argv[1], sys.argv[2]
os.environ["LLM_MODEL"] = MODEL
sys.path.insert(0, ".")

from backend.ingestion.extractor import extract_all  # noqa: E402

t0 = time.time()
for did in ("tncn2025", "qlt2025", "qlt2019"):
    doc = json.load(open(f"data/processed/{did}.json"))
    t1 = time.time()
    ents = extract_all(doc)
    json.dump(ents, open(f"data/processed/entities_{SUFFIX}_{did}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    nz = sum(1 for e in ents if any(e[f] for f in (
        "subjects", "obligations", "rights", "prohibitions", "penalties",
        "deadlines", "references", "tax_rates", "tax_base", "exemptions")))
    print(f"  {did:9s} {len(ents):>5,} node | {time.time() - t1:>5.0f}s | {nz} có dữ liệu", flush=True)
print(f"  TỔNG {time.time() - t0:.0f}s", flush=True)
