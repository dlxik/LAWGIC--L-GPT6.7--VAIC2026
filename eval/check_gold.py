"""[P3] Soát gold set trước khi tin vào con số của run_eval.py.

Chạy:  python eval/check_gold.py

Bắt 5 lỗi làm hỏng cả bài eval mà không báo gì:
  1. node_id bịa      -> citation_accuracy đo vào hư không
  2. verdict sai chính tả -> claim bị tính sai im lặng
  3. còn TODO         -> đang chấm trên gold chưa gắn xong
  4. phân bổ lệch     -> baseline bằng luôn kết quả, accuracy vô nghĩa
  5. trùng text       -> một claim tính 2 lần

In cả BASELINE (đoán bừa nhãn phổ biến nhất). Không có baseline thì "accuracy 80%"
không nói lên điều gì — BGK hỏi một câu là lộ.

Thoát mã 1 nếu gold set chưa dùng được.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.show_law import load_nodes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLD_FILE = ROOT / "eval" / "gold_set.jsonl"

VERDICTS = {"ACCURATE", "PARTIALLY_INACCURATE", "INACCURATE", "UNVERIFIABLE"}
SKIP = "SKIP"  # ứng viên hoá ra không phải claim -> không tính
TARGET_TOTAL = 50
TARGET_PER_CLASS = {
    "INACCURATE": 15,
    "PARTIALLY_INACCURATE": 15,
    "ACCURATE": 10,
    "UNVERIFIABLE": 10,
}
MIN_PER_CLASS = 8  # dưới mức này thì F1 của lớp đó không nói lên gì


def load_gold() -> list[dict]:
    if not GOLD_FILE.exists() or not GOLD_FILE.read_text(encoding="utf-8").strip():
        sys.exit("Gold set trống. Chạy: python scripts/make_worksheet.py")
    return [
        json.loads(line)
        for line in GOLD_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ci95(accuracy: float, n: int) -> float:
    """Nửa khoảng tin cậy 95% cho tỷ lệ. n=50, acc=0.8 -> ±11%.

    Con số này quyết định gold set bao nhiêu mẫu là đủ. Đưa vào đây để lúc trình
    bày còn nói được sai số, thay vì đọc mỗi "80%".
    """
    if n == 0:
        return 0.0
    return 1.96 * math.sqrt(max(accuracy * (1 - accuracy), 1e-9) / n)


def check(rows: list[dict], nodes: dict) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    todo = [r for r in rows if r.get("expected_verdict") == "TODO"]
    skipped = [r for r in rows if r.get("expected_verdict") == SKIP]
    labelled = [r for r in rows if r.get("expected_verdict") not in ("TODO", SKIP, None)]

    # 1 + 2 — từng dòng
    for row in labelled:
        cid = row.get("claim_id", "?")
        verdict = row.get("expected_verdict")
        if verdict not in VERDICTS:
            errors.append(f"{cid}: verdict {verdict!r} không hợp lệ."
                          f" Phải là một trong {sorted(VERDICTS)} hoặc {SKIP}")

        citation = row.get("expected_citation", "")
        if citation == "TODO":
            errors.append(f"{cid}: chưa có expected_citation")
        elif verdict == "UNVERIFIABLE":
            # Không có căn cứ trong luật -> citation rỗng là ĐÚNG, không phải thiếu.
            if citation and citation not in nodes:
                errors.append(f"{cid}: citation {citation!r} không có thật."
                              f" UNVERIFIABLE nên để chuỗi rỗng nếu không có căn cứ")
        elif not citation:
            errors.append(f"{cid}: chưa có expected_citation"
                          f" (verdict {verdict} cần một node_id làm căn cứ)")
        elif citation not in nodes:
            errors.append(f"{cid}: node_id {citation!r} KHÔNG TỒN TẠI trong 3 văn bản."
                          f" Kiểm: python scripts/show_law.py --check {citation}")

        if not row.get("note"):
            warnings.append(f"{cid}: chưa có note — đây là câu trả lời khi BGK hỏi ca này")

    # 5 — trùng
    for text, n in Counter(r.get("text", "") for r in labelled).items():
        if n > 1:
            errors.append(f"text trùng {n} lần: {text[:60]!r}")

    # ---------- Báo cáo ----------
    dist = Counter(r["expected_verdict"] for r in labelled)
    print(f"  Gold set: {len(rows)} dòng"
          f"  ·  {len(labelled)} đã gắn"
          f"  ·  {len(skipped)} SKIP"
          f"  ·  {len(todo)} còn TODO\n")

    print("  Phân bổ nhãn:")
    for verdict, target in TARGET_PER_CLASS.items():
        n = dist.get(verdict, 0)
        mark = "✓" if n >= MIN_PER_CLASS else "✗"
        print(f"    {mark} {verdict:<22} {n:>3d}  (mục tiêu ~{target})")
        if n < MIN_PER_CLASS and not todo:
            errors.append(f"lớp {verdict} chỉ có {n} mẫu (<{MIN_PER_CLASS})"
                          f" — F1 của lớp này không nói lên gì")

    # 4 — baseline
    if labelled:
        top_verdict, top_n = dist.most_common(1)[0]
        baseline = top_n / len(labelled)
        half = ci95(baseline, len(labelled))
        print(f"\n  BASELINE (đoán bừa {top_verdict!r} cho mọi claim): {baseline:.0%}")
        print(f"  Pipeline phải vượt rõ mức này thì con số mới có nghĩa.")
        lo, hi = max(0.0, 0.8 - half), min(1.0, 0.8 + half)
        print(f"  Với n={len(labelled)}, sai số 95% khoảng ±{half:.0%}"
              f" — accuracy 80% nghĩa là thật sự nằm trong {lo:.0%}–{hi:.0%}.")
        if baseline > 0.5:
            warnings.append(f"baseline {baseline:.0%} quá cao — phân bổ lệch,"
                            f" cân lại bằng cách SKIP bớt lớp {top_verdict}")

    # 3 — chưa xong
    if todo:
        warnings.append(f"còn {len(todo)} dòng TODO — chưa chấm được")
    if not todo and len(labelled) < TARGET_TOTAL:
        warnings.append(f"mới {len(labelled)}/{TARGET_TOTAL} claim."
                        f" Ít hơn thì sai số rộng, con số yếu trước BGK")

    if warnings:
        print(f"\n  ⚠ {len(warnings)} cảnh báo:")
        for w in warnings[:12]:
            print(f"    - {w}")
        if len(warnings) > 12:
            print(f"    ... và {len(warnings) - 12} cảnh báo nữa")

    if errors:
        print(f"\n  ✗ {len(errors)} LỖI — sửa xong mới chạy run_eval.py:")
        for e in errors[:15]:
            print(f"    - {e}")
        if len(errors) > 15:
            print(f"    ... và {len(errors) - 15} lỗi nữa")
        return 1

    if todo:
        print("\n  Chưa gắn xong, nhưng phần đã gắn không có lỗi.")
        return 1

    print(f"\n  ✓ Gold set dùng được: {len(labelled)} claim, không lỗi.")
    return 0


def main() -> None:
    sys.exit(check(load_gold(), load_nodes()))


if __name__ == "__main__":
    main()
