"""[P1] Hợp phiếu hybrid trên TOÀN BỘ graph -> entities_<doc>.json cuối.

Cấu hình thắng benchmark (F1 84%, hall 20%, penalty-type 71%):
  - 9 trường thực thể: GIAO 20b ∩ gemma (span cả hai đồng ý -> precision cao)
  - penalties: giữ nguyên 20b (gemma penalty-type = 0%)

Đầu vào: entities_20bfull_<doc>.json (A) + entities_gemma_<doc>.json (B)
Đầu ra:  entities_<doc>.json (đè - đây là graph cuối P2 nạp)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.benchmark_p1 import ENTITY_FIELDS, MATCH_THRESHOLD, _similar  # noqa: E402


def _vote(a_list, b_list):
    return [a for a in a_list if any(_similar(a, b) >= MATCH_THRESHOLD for b in b_list)]


def main() -> None:
    for did in ("tncn2025", "qlt2025", "qlt2019"):
        A = {e["node_id"]: e for e in json.loads(
            (ROOT / f"data/processed/entities_20bfull_{did}.json").read_text(encoding="utf-8"))}
        B = {e["node_id"]: e for e in json.loads(
            (ROOT / f"data/processed/entities_gemma_{did}.json").read_text(encoding="utf-8"))}

        out = []
        n_kept = n_dropped = 0
        for nid, a in A.items():
            b = B.get(nid, {})
            merged = dict(a)  # giữ node_id + penalties + mọi field khác của A
            for f in ENTITY_FIELDS:
                voted = _vote(a.get(f, []), b.get(f, []))
                n_kept += len(voted)
                n_dropped += len(a.get(f, [])) - len(voted)
                merged[f] = voted
            # penalties: giữ nguyên A (20b) - không giao
            out.append(merged)

        (ROOT / f"data/processed/entities_{did}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {did:9s} {len(out):>5,} node | giữ {n_kept} span, "
              f"bỏ {n_dropped} span 20b bịa/gemma không xác nhận")


if __name__ == "__main__":
    main()
