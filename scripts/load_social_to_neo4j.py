"""Nạp OUTPUT pipeline dư luận (posts_labeled/) vào Neo4j để tab 'Cảnh báo hiểu nhầm'
có dữ liệu THẬT.

run_pipeline.py chỉ GHI file (claims_labeled/misconceptions/trends.json). API /trends,
/misconception, /stats đọc từ Neo4j (node Post/Claim/Misconception) -> cần bước nạp này.
KHÔNG wipe: thêm social vào cạnh graph luật đang có (CONTRADICTS/REFERS_TO nối vào node luật).

Chạy:  python scripts/load_social_to_neo4j.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import ROOT  # noqa: E402
from backend.graph import loader  # noqa: E402

RAW = ROOT / "data" / "raw" / "social_posts.json"
LAB = ROOT / "data" / "processed" / "posts_labeled"


def main() -> None:
    posts = json.loads(RAW.read_text(encoding="utf-8"))
    claims = json.loads((LAB / "claims_labeled.json").read_text(encoding="utf-8"))
    miscs = json.loads((LAB / "misconceptions.json").read_text(encoding="utf-8"))

    claims_by_post: dict[str, list[dict]] = {}
    for c in claims:
        claims_by_post.setdefault(c["post_id"], []).append(c)

    print(f"Nạp {len(posts)} post + {len(claims)} claim (904 post có claim)...")
    for i, p in enumerate(posts, 1):
        loader.load_post(p, claims_by_post.get(p["post_id"], []))
        if i % 400 == 0:
            print(f"  {i}/{len(posts)}")

    # load_misconceptions mong '_members'; file thật dùng 'member_claim_ids' -> map.
    for m in miscs:
        m["_members"] = m.get("member_claim_ids", [])
    loader.load_misconceptions(miscs)
    print(f"Nạp {len(miscs)} misconception. XONG.")


if __name__ == "__main__":
    main()
