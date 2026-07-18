"""[P3] Gom post thành luồng. ĐỊNH NGHĨA DUY NHẤT — đừng gom ở chỗ khác.

thread_id là `custom_id` của Batches API (crawl_docs.md §7.2). Hai chỗ gom khác
nhau -> thread_id lệch -> retry sai đơn vị -> mất cả luồng 90 post mà không báo.

Dùng bởi: backend/discourse/classifier.py, scripts/show_thread.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS_FILE = ROOT / "data" / "raw" / "social_posts.json"


def load_posts(path: Path = POSTS_FILE) -> list[dict]:
    """Đọc post thô. Trả list[dict] theo schemas.py::Post."""
    if not path.exists():
        raise FileNotFoundError(f"Không thấy {path}. Chạy: python scripts/fetch_social_posts.py")
    return json.loads(path.read_text(encoding="utf-8"))


def build_threads(posts: list[dict]) -> dict[str, list[dict]]:
    """Gom post thành luồng. Trả {thread_id: [gốc, reply theo thời gian...]}.

    thread_id = post_id của comment gốc.

    Reply mồ côi (parent_id trỏ post không có trong file) tự thành luồng riêng —
    thà mất ngữ cảnh còn hơn mất post. Xảy ra khi crawl cắt giữa chừng.
    """
    by_id = {p["post_id"]: p for p in posts}
    threads: dict[str, list[dict]] = {}

    for post in posts:
        parent = post.get("parent_id")
        root_id = parent if parent and parent in by_id else post["post_id"]
        threads.setdefault(root_id, []).append(post)

    for thread in threads.values():
        thread.sort(key=lambda p: (p.get("parent_id") is not None, p["created_at"]))
    return threads


def debated_first(threads: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    """Luồng có tranh luận trước, dài nhất trước.

    78% "luồng" chỉ có 1 post. 314 luồng tranh luận (22%) chứa TOÀN BỘ 1.875 reply
    — đó là chỗ hiểu nhầm sinh ra và lan. Hết giờ/hết tiền thì cắt từ đuôi danh
    sách này, không cắt từ đầu.
    """
    return sorted(threads.items(), key=lambda kv: -len(kv[1]))
