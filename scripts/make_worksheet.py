"""[P3] Dựng bàn làm việc để gắn nhãn gold set bằng tay.

Chạy:  python scripts/make_worksheet.py
Sinh:  eval/gold_set.jsonl   — 60 dòng, expected_verdict/expected_citation = "TODO"
       eval/WORKSHEET.md     — ngữ cảnh luồng + điều luật liên quan cho từng claim

Rồi: mở 2 file cạnh nhau, điền nhãn vào .jsonl, xong chạy `python eval/check_gold.py`.

VÌ SAO KHÔNG ĐỂ MÁY GẮN NHÃN
  Pipeline chấm điểm bằng LLM. Nhãn gold cũng do LLM sinh thì accuracy đo được
  chỉ là "LLM có đồng ý với chính nó không" — không phải "phân loại có đúng không".
  DIVISION.md ghi "gắn nhãn TAY" chính vì vậy. Script này chỉ dọn bàn, không gắn nhãn.

  Cụ thể: worksheet KHÔNG gợi ý sẵn node_id qua linker.py. Gợi ý rồi bấm đồng ý
  là đang chấm điểm chính cái sắp đo. Worksheet chỉ đưa điều luật ứng viên theo
  từ khoá của chủ đề, người gắn nhãn tự chọn.

CÁCH CHỌN ỨNG VIÊN (phải nói được với BGK, nên viết ra đây)
  Vũ trụ mẫu: 2.189 post trong 314 luồng có tranh luận — chỗ hiểu nhầm sinh ra
  và lan. Bỏ 1.132 luồng 1-post vì không có đối thoại để hiểu nhầm lộ ra.

  Ba rổ, tổng 60 ứng viên (dư 10 so với mục tiêu 50 để còn cân lại phân bổ):
    A · 35  Lấy mẫu ngẫu nhiên CÓ SEED trong post mang tín hiệu pháp lý
            (có số tiền, hoặc có từ khoá thuế). Đây là rổ chính, không thiên vị.
    B · 15  Luồng bàn về ngưỡng doanh thu (500/200 triệu) — bảo đảm case demo
            và cặp ACCURATE/PARTIALLY_INACCURATE tương phản có mặt.
    C · 10  Post có từ khoá pháp lý nhưng mơ hồ, không số liệu — hạt giống cho
            lớp UNVERIFIABLE. Thiếu lớp này thì LLM ép hết vào 3 lớp kia.

  Seed cố định -> chạy lại ra đúng danh sách cũ. Nhãn đã gắn không bị xáo.

  TRẦN ĐỘ DÀI 320 KÝ TỰ. Không phải để tiết kiệm token — để claim còn là CLAIM.
  Bình luận 1.194 ký tự là bài luận kinh tế trộn 5 ý kiến với 2 khẳng định; ép nó
  vào một `expected_citation` duy nhất là bịa ra một câu hỏi thi không có đáp án
  đúng. Claim tốt là câu dứt khoát: "Thuế ngành ăn uống 4,5% trên doanh thu".
  Đánh đổi phải biết: bỏ qua hiểu nhầm nằm trong bài dài. Chấp nhận được — eval
  đo verdict/citation, không đo khả năng bóc claim khỏi bài luận.

TRƯỜNG `text`
  Điền sẵn NGUYÊN VĂN bình luận, không phải bản viết lại của máy — để không ai
  cài quan điểm vào câu hỏi thi. Người gắn nhãn tự sửa thành câu claim đứng độc
  lập nếu bình luận quá dài hoặc chứa nhiều claim.
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.discourse.threads import build_threads, load_posts  # noqa: E402
from scripts.show_law import load_nodes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLD_FILE = ROOT / "eval" / "gold_set.jsonl"
WORKSHEET_FILE = ROOT / "eval" / "WORKSHEET.md"

SEED = 2026  # cố định -> chạy lại ra cùng danh sách
N_RANDOM, N_THRESHOLD, N_VAGUE = 35, 15, 10
MIN_LEN, MAX_LEN = 40, 320  # claim là một câu, không phải bài luận

MONEY = re.compile(r"\d[\d.,]*\s*(triệu|tỷ|tỉ|đồng|%)", re.I)
LEGAL_KW = re.compile(
    r"thuế|hoá đơn|hóa đơn|kê khai|khoán|doanh thu|thu nhập|chậm nộp|cưỡng chế|"
    r"quyết toán|miễn thuế|thuế suất|nghị định|luật|quy định",
    re.I,
)
THRESHOLD_KW = re.compile(r"(500|200|100)\s*(triệu|tr\b)|ngưỡng", re.I)

# Bản đồ điều luật cho ĐÚNG chủ đề của dư luận đã crawl (thuế hộ kinh doanh).
# In một lần ở đầu worksheet, đọc một lần dùng cho cả 60 claim — thay vì gợi ý
# từng dòng, vốn hoặc nhiễu (khớp lỏng) hoặc trống (khớp chặt).
#
# node_id nào sai thì make_worksheet.py chết ngay, không âm thầm in bản đồ hỏng.
LAW_MAP: list[tuple[str, list[str]]] = [
    ("Ngưỡng miễn thuế", ["tncn2025-d7-k1"]),
    ("Cách tính MẶC ĐỊNH — trên thu nhập (doanh thu − chi phí)",
     ["tncn2025-d7-k2", "tncn2025-d7-k2-a", "tncn2025-d7-k2-b",
      "tncn2025-d7-k2-c", "tncn2025-d7-k2-d"]),
    ("Cách tính TUỲ CHỌN — trên phần doanh thu vượt 500tr (chỉ khi ≤3 tỷ)",
     ["tncn2025-d7-k3", "tncn2025-d7-k3-a", "tncn2025-d7-k3-b",
      "tncn2025-d7-k3-c", "tncn2025-d7-k3-d", "tncn2025-d7-k3-e"]),
    ("Cho thuê bất động sản", ["tncn2025-d7-k4"]),
    ("Hộ kinh doanh kê khai (luật MỚI)", ["qlt2025-d13"]),
    ("Thuế khoán (chỉ có ở luật CŨ — luật mới đã bỏ)", ["qlt2019-d51"]),
    ("Hoá đơn điện tử", ["qlt2025-d26", "qlt2019-d89"]),
    ("Chậm nộp — là LÃI, không phải phạt", ["qlt2025-d16", "qlt2019-d59"]),
    ("Cưỡng chế", ["qlt2025-d48", "qlt2025-d49", "qlt2019-d132"]),
]

# Cụm từ -> tra điều luật ứng viên. Chỉ để THU HẸP vùng đọc cho người gắn nhãn,
# KHÔNG phải gợi ý đáp án.
#
# Khớp CẢ CỤM, không khớp từ đầu: "thuế suất" mà khớp theo "thuế" thì trúng gần
# như mọi điều trong 1.821 node -> gợi ý "chuyển nhượng vàng miếng" cho claim về
# hộ kinh doanh, tốn thời gian người đọc hơn là giúp.
#
# Không có cụm nào khớp -> không gợi ý gì, để người gắn nhãn tự `show_law.py --grep`.
# Thà không gợi ý còn hơn gợi ý sai hướng.
HINT_PHRASES = [
    "500 triệu",
    "không phải nộp thuế",
    "doanh thu tính thuế",
    "thu nhập tính thuế",
    "thuế suất",
    "hoá đơn điện tử",
    "kê khai",
    "khai thuế",
    "thuế khoán",
    "chậm nộp",
    "cưỡng chế",
    "miễn thuế",
]


def _is_candidate(post: dict) -> bool:
    text = post["content"]
    return MIN_LEN <= len(text) <= MAX_LEN and bool(LEGAL_KW.search(text))


def pick_candidates(posts: list[dict]) -> list[dict]:
    threads = build_threads(posts)
    debated = {tid: t for tid, t in threads.items() if len(t) > 1}
    pool = [p for t in debated.values() for p in t if _is_candidate(p)]

    rng = random.Random(SEED)
    chosen: dict[str, dict] = {}

    def take(subset: list[dict], n: int, bucket: str) -> None:
        rng.shuffle(subset)
        for post in subset:
            if len(chosen) >= N_RANDOM + N_THRESHOLD + N_VAGUE:
                return
            if post["post_id"] in chosen:
                continue
            chosen[post["post_id"]] = {**post, "_bucket": bucket}
            n -= 1
            if n <= 0:
                return

    threshold = [p for p in pool if THRESHOLD_KW.search(p["content"])]
    vague = [p for p in pool if not MONEY.search(p["content"])]
    general = [p for p in pool if MONEY.search(p["content"])]

    take(threshold, N_THRESHOLD, "B·ngưỡng")
    take(vague, N_VAGUE, "C·mơ hồ")
    take(general, N_RANDOM, "A·ngẫu nhiên")
    return list(chosen.values())


def law_hints(nodes: dict[str, dict], post_text: str) -> list[dict]:
    """Điều luật ứng viên theo cụm từ chung giữa bình luận và điều luật.

    KHÔNG dùng linker.py: gợi ý bằng chính thứ sắp được chấm điểm rồi bấm "đồng ý"
    là tự chấm bài mình. Ở đây chỉ khớp chuỗi thô, người gắn nhãn vẫn phải đọc.

    Xếp hạng: nhiều cụm khớp trước; hoà thì luật hiện hành (2025) trước luật cũ,
    vì tin đồn hay bám luật cũ nhưng căn cứ đúng nằm ở luật mới.
    """
    text_low = post_text.lower()
    matched = [p for p in HINT_PHRASES if p in text_low]
    if not matched:
        return []

    scored: list[tuple[int, int, dict]] = []
    for node in nodes.values():
        node_low = node["text"].lower()
        hits = sum(1 for phrase in matched if phrase in node_low)
        if hits:
            recent = 0 if node["doc_id"] in ("tncn2025", "qlt2025") else 1
            scored.append((-hits, recent, node))

    scored.sort(key=lambda x: (x[0], x[1], len(x[2]["text"])))
    return [node for _, _, node in scored[:6]]


def build_gold_rows(candidates: list[dict]) -> list[dict]:
    rows = []
    for i, post in enumerate(sorted(candidates, key=lambda p: p["post_id"]), start=1):
        rows.append({
            "claim_id": f"g{i:03d}",
            "text": post["content"],
            "expected_verdict": "TODO",
            "expected_citation": "TODO",
            "note": "",
            "source_post_id": post["post_id"],
        })
    return rows


def render_law_map(nodes: dict[str, dict]) -> str:
    """Bảng tra điều luật, dựng từ node THẬT. node_id sai -> chết ngay."""
    out = ["\n## Bản đồ điều luật (đọc một lần, dùng cho cả 60 claim)\n\n"
           "Đây là vùng luật mà dư luận đã crawl đang bàn tới. Tra node khác:\n"
           "`python scripts/show_law.py --grep \"...\"` · `python scripts/show_law.py tncn2025-d7`\n"]
    for group, node_ids in LAW_MAP:
        out.append(f"\n**{group}**\n\n")
        for node_id in node_ids:
            node = nodes.get(node_id)
            if node is None:
                raise SystemExit(
                    f"LAW_MAP trỏ node không tồn tại: {node_id!r}."
                    f" Sửa scripts/make_worksheet.py, đừng in bản đồ hỏng."
                )
            snippet = " ".join(node["text"].split())[:150]
            out.append(f"- `{node_id}` — {node['display']}<br>{snippet}…\n")
    return "".join(out)


def build_worksheet(candidates: list[dict], rows: list[dict], threads, nodes) -> str:
    by_post = {r["source_post_id"]: r for r in rows}
    thread_of = {p["post_id"]: tid for tid, t in threads.items() for p in t}

    out = [WORKSHEET_HEADER, render_law_map(nodes), "\n## Danh sách claim\n"]
    for post in sorted(candidates, key=lambda p: by_post[p["post_id"]]["claim_id"]):
        row = by_post[post["post_id"]]
        thread_id = thread_of[post["post_id"]]
        thread = threads[thread_id]
        root = thread[0]

        out.append(f"\n---\n\n## {row['claim_id']}  ·  `{post['post_id']}`"
                   f"  ·  {post['engagement']} like  ·  rổ {post['_bucket']}\n")

        if post["post_id"] != root["post_id"]:
            out.append(f"**Ngữ cảnh — bình luận gốc** (`{root['post_id']}`):\n")
            out.append(f"> {root['content'][:400]}\n")

        out.append("**Bình luận cần gắn nhãn:**\n")
        out.append(f"> {post['content']}\n")
        out.append(f"\n_Đọc cả luồng:_ `python scripts/show_thread.py {thread_id}`\n")

        hints = law_hints(nodes, post["content"])
        if hints:
            out.append("\n_Cụm từ trùng với_ "
                       + ", ".join(f"`{n['node_id']}`" for n in hints)
                       + " — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.\n")
    return "".join(out)


WORKSHEET_HEADER = """# Bàn gắn nhãn gold set — P3

> Sinh bởi `python scripts/make_worksheet.py` (seed cố định, chạy lại ra cùng danh sách).
> **Không sửa file này bằng tay** — nhãn điền vào `eval/gold_set.jsonl`.

## Cách làm

1. Mở `eval/gold_set.jsonl` cạnh file này. Mỗi dòng một claim, `claim_id` khớp mục bên dưới.
2. Với từng dòng, điền:
   - `expected_verdict`: `ACCURATE` | `PARTIALLY_INACCURATE` | `INACCURATE` | `UNVERIFIABLE`
   - `expected_citation`: node_id CÓ THẬT, vd `tncn2025-d7-k1`. Kiểm:
     `python scripts/show_law.py --check tncn2025-d7-k1`
   - `note`: vì sao — câu này chính là thứ trả lời BGK khi họ hỏi một ca cụ thể.
   - `text`: sửa lại thành câu claim đứng độc lập NẾU bình luận quá dài / nhiều claim.
     Đang điền sẵn nguyên văn để không ai cài quan điểm vào câu hỏi thi.
3. Xong chạy `python eval/check_gold.py` — soát node_id có thật, đủ nhãn, phân bổ có cân.

## Chỉ tiêu phân bổ (quan trọng hơn tổng số)

| Verdict | Cần | Vì sao |
|---|---|---|
| `INACCURATE` | ~15 | Nhãn chính, tin đồn thật |
| `PARTIALLY_INACCURATE` | ~15 | Lớp khó nhất — ca 505 triệu nằm đây |
| `ACCURATE` | ~10 | Chứng minh không phải cứ gắn "sai" là xong |
| `UNVERIFIABLE` | ~10 | Bỏ lớp này thì LLM ép hết vào 3 lớp kia |

Có 60 ứng viên cho mục tiêu 50 — **dư 10 để cân phân bổ**. Lớp nào đủ rồi thì
dòng thừa để `expected_verdict: "SKIP"`, `check_gold.py` sẽ bỏ qua.

Lấy ngẫu nhiên 50 cái sẽ ra ~40 `INACCURATE` — lúc đó một model đoán bừa
"INACCURATE" cho mọi thứ cũng đạt 80%, và cả bài eval vô nghĩa.

## Bẫy đã biết của đề tài thuế

- **`tncn2025-d7-k2` vs `k3` là hai cách tính KHÁC NHAU.** k2 (mặc định): thuế trên
  *thu nhập* (doanh thu − chi phí) × 15%. k3 (tuỳ chọn, ≤3 tỷ): thuế trên *phần
  doanh thu vượt* 500 triệu × 0,5–5%.
  → "doanh thu 505tr thì chỉ 5tr bị tính thuế" nói như quy tắc chung =
  `PARTIALLY_INACCURATE` (chỉ đúng nếu chọn k3).
  → "**nếu nộp theo doanh thu** thì chỉ nộp phần trên 500tr" = `ACCURATE` (đúng k3-a).
- **Tiền chậm nộp là LÃI, không phải PHẠT** (`LATE_PAYMENT_INTEREST`, 127 node —
  loại nhiều nhất). "Chậm nộp bị phạt" → `PARTIALLY_INACCURATE`, không phải `ACCURATE`.
- **Ngưỡng 500 triệu tính theo NĂM**, không phải tháng. "Bán 40tr/tháng chưa phải
  đóng thuế" = 480tr/năm → đúng, nhưng phải kiểm phép nhân.
- **Ý kiến ≠ claim.** "500 triệu quá thấp" là kiến nghị → không phải claim.
  Nếu bình luận không chứa claim nào, để `expected_verdict: "SKIP"`.
- **Nói về DỰ THẢO không phải luật hiện hành.** "200 triệu như dự định ban đầu"
  → `UNVERIFIABLE` (luật không nói về dự thảo), hoặc `SKIP`.


"""


def main() -> None:
    posts = load_posts()
    threads = build_threads(posts)
    nodes = load_nodes()

    candidates = pick_candidates(posts)
    rows = build_gold_rows(candidates)

    if GOLD_FILE.exists() and GOLD_FILE.stat().st_size > 0:
        existing = [json.loads(line) for line in GOLD_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        labelled = [r for r in existing if r.get("expected_verdict") not in ("TODO", None)]
        if labelled:
            sys.exit(
                f"  ! {GOLD_FILE} đã có {len(labelled)} dòng ĐÃ GẮN NHÃN.\n"
                f"    Chạy lại sẽ xoá công sức đó. Đổi tên file cũ trước nếu thật sự muốn dựng lại."
            )

    GOLD_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    WORKSHEET_FILE.write_text(
        build_worksheet(candidates, rows, threads, nodes), encoding="utf-8"
    )

    buckets: dict[str, int] = {}
    for post in candidates:
        buckets[post["_bucket"]] = buckets.get(post["_bucket"], 0) + 1

    print(f"  {len(rows)} ứng viên -> {GOLD_FILE.relative_to(ROOT)}")
    for bucket, n in sorted(buckets.items()):
        print(f"    {bucket:<14} {n:>3d}")
    print(f"  bàn làm việc -> {WORKSHEET_FILE.relative_to(ROOT)}")
    print(f"\n  Tiếp: mở 2 file cạnh nhau, điền nhãn, rồi `python eval/check_gold.py`")


if __name__ == "__main__":
    main()
