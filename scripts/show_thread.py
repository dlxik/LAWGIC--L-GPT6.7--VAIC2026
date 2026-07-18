"""[P3] Đọc luồng thảo luận từ data/raw/social_posts.json.

Không có công cụ này thì gắn nhãn 50 claim = dò tay trong JSON 2 MB.
crawl_docs.md §7.4 đề xuất; P3_PLAN.md bước 3 cần nó trước khi làm gold set.

Chạy:
    python scripts/show_thread.py --list              # 314 luồng có tranh luận, nhiều reply nhất trước
    python scripts/show_thread.py vne-61662018        # in 1 luồng
    python scripts/show_thread.py --grep "500 triệu"  # tìm luồng theo nội dung
    python scripts/show_thread.py --stats             # số liệu tổng quan

Gom luồng dùng chung backend/discourse/threads.py — một định nghĩa duy nhất, vì
thread_id là custom_id của Batches API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.discourse.threads import build_threads, load_posts  # noqa: E402


def render_thread(thread: list[dict], *, width: int = 88) -> str:
    """Luồng -> text cho người đọc. KHÁC render cho LLM (xem classifier.py)."""
    lines = []
    for post in thread:
        is_reply = post.get("parent_id") is not None
        tag = "  [TRẢ LỜI]" if is_reply else "[GỐC]"
        indent = "    " if is_reply else ""
        lines.append(
            f"{tag} {post['post_id']}  ·  {post['created_at'][:16].replace('T', ' ')}"
            f"  ·  {post['engagement']} like"
        )
        content = post["content"]
        while content:
            lines.append(indent + "  " + content[:width])
            content = content[width:]
        lines.append("")
    return "\n".join(lines)


def cmd_stats(threads: dict[str, list[dict]], posts: list[dict]) -> None:
    debated = {k: v for k, v in threads.items() if len(v) > 1}
    replies = sum(1 for p in posts if p.get("parent_id"))
    longest = max(threads.values(), key=len)
    print(f"  post          : {len(posts):,}  ({len(posts) - replies:,} gốc + {replies:,} reply)")
    print(f"  luồng         : {len(threads):,}")
    print(f"  có tranh luận : {len(debated):,}  ({len(debated) / len(threads):.0%})")
    print(f"  luồng 1 post  : {len(threads) - len(debated):,}")
    print(f"  dài nhất      : {len(longest)} post  (thread {longest[0]['post_id']})")
    print(f"  thời gian     : {min(p['created_at'] for p in posts)[:10]}"
          f" → {max(p['created_at'] for p in posts)[:10]}")
    reply_in_debated = sum(len(v) - 1 for v in debated.values())
    print(f"\n  {len(debated):,} luồng tranh luận chứa {reply_in_debated:,}/{replies:,} reply"
          f" ({reply_in_debated / replies:.0%}) — gắn nhãn ưu tiên ở đây")


def cmd_list(threads: dict[str, list[dict]], limit: int) -> None:
    debated = sorted(
        (t for t in threads.values() if len(t) > 1), key=len, reverse=True
    )[:limit]
    print(f"  {len(debated)} luồng có tranh luận (nhiều reply nhất trước):\n")
    for thread in debated:
        root = thread[0]
        engagement = sum(p["engagement"] for p in thread)
        print(f"  {root['post_id']:>16}  {len(thread):>3d} post  {engagement:>5d} like"
              f"  {root['created_at'][:10]}  {root['content'][:60]}")


def cmd_grep(threads: dict[str, list[dict]], needle: str, limit: int) -> None:
    needle_low = needle.lower()
    hits = [
        (tid, thread, sum(needle_low in p["content"].lower() for p in thread))
        for tid, thread in threads.items()
    ]
    hits = sorted(((t, th, n) for t, th, n in hits if n), key=lambda x: -x[2])[:limit]
    print(f"  {len(hits)} luồng khớp {needle!r}:\n")
    for tid, thread, n in hits:
        print(f"  {tid:>16}  {len(thread):>3d} post  {n} lần khớp"
              f"  {thread[0]['content'][:60]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Đọc luồng thảo luận")
    parser.add_argument("thread_id", nargs="?", help="post_id của comment gốc")
    parser.add_argument("--list", action="store_true", help="liệt kê luồng có tranh luận")
    parser.add_argument("--grep", metavar="TEXT", help="tìm luồng theo nội dung")
    parser.add_argument("--stats", action="store_true", help="số liệu tổng quan")
    parser.add_argument("-n", type=int, default=25, help="số dòng tối đa (mặc định 25)")
    args = parser.parse_args()

    posts = load_posts()
    threads = build_threads(posts)

    if args.stats:
        cmd_stats(threads, posts)
    elif args.list:
        cmd_list(threads, args.n)
    elif args.grep:
        cmd_grep(threads, args.grep, args.n)
    elif args.thread_id:
        thread = threads.get(args.thread_id)
        if not thread:
            sys.exit(f"Không thấy luồng {args.thread_id}. Thử: --list hoặc --grep")
        print(render_thread(thread))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
