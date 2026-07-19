"""[P3] Gộp FULL PIPELINE dư luận: post thô -> nhãn -> misconception -> trend.

Chạy trọn luồng của P3, nối tất cả các mảnh lại:
    post (data/raw/social_posts.json)
      -> classify_posts      (chủ đề + tách claim)          [classifier.py]
      -> link_claim          (claim -> Điều/Khoản/Điểm)     [linker.py]
      -> verdict_for_claim   (đúng/sai/không đủ căn cứ)      [misinformation.py]
      -> cluster_misconceptions (gom hiểu nhầm giống nhau)   [misinformation.py]
      -> detect_trends       (cảnh báo tin đồn đang lan)     [misinformation.py]

Ghi ra data/processed/posts_labeled/ + in bảng trend.

Chạy:
    python scripts/run_pipeline.py --threads 20      # 20 luồng tranh luận (demo nhanh)
    python scripts/run_pipeline.py --all             # toàn bộ (đắt, ~1446 luồng)
    python scripts/run_pipeline.py --as-of 2025-12-15  # mốc thời gian tính trend

Tốn API (classify + link + verdict mỗi claim). Mặc định chạy MẪU NHỎ để xem luồng
chạy đúng; --all mới quét hết.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import get_settings  # noqa: E402
from backend.discourse import classifier, linker, misinformation  # noqa: E402
from backend.discourse.threads import build_threads, debated_first, load_posts  # noqa: E402

OUT_DIR = get_settings().labeled_posts_dir


def _select_posts(n_threads: int | None) -> list[dict]:
    """Lấy post để chạy. n_threads=None -> tất cả; ngược lại N luồng tranh luận nhất."""
    posts = load_posts()
    if n_threads is None:
        return posts
    threads = build_threads(posts)
    chosen = debated_first(threads)[:n_threads]
    return [p for _, thread in chosen for p in thread]


def run(n_threads: int | None, as_of: str | None, window_hours: int | None = None,
        min_occurrences: int | None = None) -> dict:
    posts = _select_posts(n_threads)
    print(f"  [1/5] Phân loại {len(posts)} post ({'toàn bộ' if n_threads is None else f'{n_threads} luồng'})...")
    classified = classifier.classify_posts(posts)

    # Gom claim từ các post đã phân loại, gắn kèm engagement + thời gian của post.
    post_meta = {p["post_id"]: p for p in posts}
    claims = []
    for post_id, data in classified.items():
        if not data.get("is_legal_claim"):
            continue
        meta = post_meta.get(post_id, {})
        for c in data.get("claims", []):
            claims.append({
                "claim_id": c["claim_id"],
                "post_id": post_id,
                "text": c["text"],
                "topic": data.get("topic", ""),
                "engagement": meta.get("engagement", 0),
                "created_at": meta.get("created_at"),
            })
    print(f"  [2/5] {len(claims)} claim pháp lý. Liên kết điều luật...")

    for i, claim in enumerate(claims):
        # 1 claim lỗi (model hỏng/từ chối) KHÔNG được làm sập cả pipeline.
        try:
            claim["citations"] = linker.link_claim(claim["text"], claim["topic"])
        except Exception as exc:  # noqa: BLE001
            print(f"\n        ! link lỗi {claim['claim_id']}: {exc}")
            claim["citations"] = []
        print(f"        link {i+1}/{len(claims)}", end="\r")
    print()

    print("  [3/5] Phán verdict...")
    for i, claim in enumerate(claims):
        try:
            claim.update(misinformation.verdict_for_claim(claim["text"], claim["citations"]))
        except Exception as exc:  # noqa: BLE001
            print(f"\n        ! verdict lỗi {claim['claim_id']}: {exc}")
            claim.update({"verdict": "UNVERIFIABLE", "confidence": 0.0,
                          "explanation": f"lỗi model: {exc}", "correct_statement": ""})
        print(f"        verdict {i+1}/{len(claims)}", end="\r")
    print()

    print("  [4/5] Gom cụm hiểu nhầm...")
    misconceptions = misinformation.cluster_misconceptions(claims)

    print(f"  [5/5] Phát hiện trend (as_of={as_of or 'tự động'}, window={window_hours or 'mặc định'}h, "
          f"min_occ={min_occurrences or 'mặc định'})...")
    trends = misinformation.detect_trends(
        misconceptions, as_of=as_of, window_hours=window_hours,
        min_occurrences=min_occurrences,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "claims_labeled.json").write_text(
        json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "misconceptions.json").write_text(
        json.dumps(misconceptions, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "trends.json").write_text(
        json.dumps(trends, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"claims": claims, "misconceptions": misconceptions, "trends": trends}


def _print_summary(result: dict) -> None:
    from collections import Counter

    claims = result["claims"]
    dist = Counter(c.get("verdict") for c in claims)
    print("\n  === KẾT QUẢ ===")
    print(f"  Claim: {len(claims)}")
    for v, n in dist.most_common():
        print(f"    {v:<24} {n}")
    print(f"  Misconception (cụm hiểu sai): {len(result['misconceptions'])}")

    print("\n  TREND — tin đồn đang lan (cảnh báo chính của hệ thống):")
    if not result["trends"]:
        print("    (không có trend vượt ngưỡng trong cửa sổ — thử --as-of khác)")
    for t in result["trends"][:5]:
        m = t["misconception"]
        occ = t.get("occurrences_in_window", m["count"])
        print(f"    [{t['severity']}] {occ} claim trong cửa sổ (cụm {m['count']} tổng), "
              f"{m['total_engagement']} tương tác")
        print(f"          \"{m['canonical_text'][:80]}\"")
        if m.get("contradicts"):
            print(f"          trái với: {', '.join(m['contradicts'][:3])}")
    print(f"\n  -> {OUT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gộp full pipeline dư luận P3")
    parser.add_argument("--threads", type=int, default=15, help="số luồng tranh luận (mặc định 15)")
    parser.add_argument("--all", action="store_true", help="chạy toàn bộ post (đắt)")
    parser.add_argument("--as-of", default=None, help="mốc thời gian tính trend, vd 2025-12-15")
    parser.add_argument("--window", type=int, default=None,
                        help="cửa sổ trend (giờ). Mặc định 48h thường TRỐNG vì post cũ (2025) "
                             "so với ngày demo — dùng ~720 (30 ngày) neo vào giai đoạn sôi động")
    parser.add_argument("--min-occ", type=int, default=None,
                        help="số lần lặp tối thiểu để coi là trend. Mặc định 5 (config). "
                             "Dữ liệu demo: đợt bùng lớn nhất là 4 claim/ngày (19/11/2025) nên "
                             "dùng 3. Demo bật trend: --as-of 2025-11-20 --window 48 --min-occ 3")
    args = parser.parse_args()

    n = None if args.all else args.threads
    _print_summary(run(n, args.as_of, args.window, args.min_occ))


if __name__ == "__main__":
    main()
