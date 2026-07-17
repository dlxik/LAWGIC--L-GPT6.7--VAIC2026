"""[P3] Crawl thao luan cong khai -> data/raw/social_posts.json

Nguon: comment VnExpress (API JSON cong khai). Da xac minh 17/07/2026:
  - Facebook          : khong con API cong khai lay comment -> BO
  - VnExpress         : usi-saas.vnexpress.net tra JSON, HTTP 200, phan trang OK
  - thuvienphapluat   : khong co comment

CHI lay noi dung cong khai. Hash author. KHONG luu ten/email that.
Output: list[Post] theo backend/models/schemas.py

THIET KE: IT BAI, DU LUONG.
  Thao luan la CA LUONG, khong phai cau noi le. Hieu nham va dinh chinh nam
  canh nhau trong cung mot luong:
      goc:   "Doanh thu 200 trieu la phai dong thue roi"
      reply: "Ban nham, tu 2026 la 500 trieu"
  Lay 53 bai x chi comment goc -> 2.892 cau noi le, mat het ngu canh.
  Lay MAX_ARTICLES bai x (goc + TOAN BO reply) -> luong day du, co ngu canh.

RIENG TU - doc truoc khi sua file nay:
  API tra ve `full_name` = TEN THAT ("Duong Dinh Duy"). schemas.py::Post ghi ro
  `author_hash  # KHONG luu danh tinh that`. Ta hash `userid` (khong dao nguoc
  duoc) va KHONG BAO GIO ghi full_name ra file. Hash tu full_name cung sai: ten
  that van suy ra duoc bang bang tra.

CANH BAO DU LIEU (do that, 17/07/2026):
  Comment tap trung 2025-06 -> 2026-02 (luc luat DUOC THONG QUA), khong phai
  2026-07 (luc luat CO HIEU LUC). Bao chi da chuyen chu de.
  -> Q3_TRENDING_MISCONCEPTIONS loc `created_at > datetime() - 48h` tra RONG.
  -> Phai noi rong TREND_WINDOW_HOURS, hoac neo Q3 vao moc thoi gian truyen vao
     (giong law_as_of(date)) thay vi datetime(). Xem README muc "Du lieu demo".

Chay:  python scripts/fetch_social_posts.py
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT_FILE = Path("data/raw/social_posts.json")

TOPIC_URL = "https://vnexpress.net/topic/thue-ho-kinh-doanh-28377"
TOPIC_PAGES = 3

COMMENT_API = "https://usi-saas.vnexpress.net/index/get"
# Reply endpoint. Mau chot: objectid la BAI, con comment goc truyen qua `id`.
# Truyen objectid=comment_id -> "Invalid id". Thieu offset -> "Invalid offset".
REPLY_API = "https://usi-saas.vnexpress.net/index/getreplay"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://vnexpress.net/",
}

# Lay bai co nhieu thao luan nhat. It bai + du luong > nhieu bai + cut ngon.
MAX_ARTICLES = 12
PAGE_SIZE = 100  # API chap nhan toi 100/lan
REQUEST_DELAY = 0.25  # giay - lich su voi may chu

# Phai bat CA URL day du, khong chi article_id: VnExpress KHONG resolve URL thieu
# slug (https://vnexpress.net/4991878.html -> 404). Post.url la nguon de kiem
# chung - link hong thi demo "bam vao doc nguon" mat het uy tin.
RE_ARTICLE_URL = re.compile(r"https://vnexpress\.net/[a-z0-9-]+-(\d{7})\.html")

# RIENG TU: content cua REPLY chua HTML tho co danh tinh THAT cua nguoi duoc tra loi:
#   <span class="reply_name myuser" data-userid="1073324795">@trungtuyen938</span>:&nbsp;
# -> userid THO (chua hash) + ten tai khoan that. Chi xuat hien o reply, comment
# goc khong bao gio dinh. Phai cat CA KHOI, khong chi tag: `parent_id` da cho
# biet dang tra loi ai roi, tien to @mention la thua ma lai cho danh tinh.
RE_MENTION = re.compile(r'<span class="reply_name[^"]*"[^>]*>.*?</span>\s*:?\s*(?:&nbsp;)?', re.S)
RE_HTML_TAG = re.compile(r"<[^>]+>")


def _clean_content(raw: str) -> str:
    """Bo @mention (co danh tinh that) + HTML tho -> text sach cho LLM."""
    text = RE_MENTION.sub("", raw)
    text = RE_HTML_TAG.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _hash_author(user_id: int | str) -> str:
    """userid -> hash khong dao nguoc duoc.

    Dung userid chu KHONG dung full_name: ten that suy nguoc duoc bang bang tra.
    Cat 16 ky tu du phan biet ~2 trieu tac gia.
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:16]


def _get(client: httpx.Client, url: str, params: dict) -> dict:
    """GET + parse JSON. Loi mang/JSON -> tra data rong, khong nem."""
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json().get("data") or {}
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  ! {url} {params.get('objectid')}: {exc}")
        return {}


def fetch_articles(pages: int = TOPIC_PAGES) -> dict[str, str]:
    """Quet trang chu de -> {article_id: url_day_du_co_slug}."""
    articles: dict[str, str] = {}
    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            url = TOPIC_URL if page == 1 else f"{TOPIC_URL}-p{page}"
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"  ! bo qua {url}: {exc}")
                continue
            for match in RE_ARTICLE_URL.finditer(response.text):
                articles.setdefault(match.group(1), match.group(0))
            time.sleep(REQUEST_DELAY)
    return articles


def count_comments(client: httpx.Client, article_id: str) -> int:
    """So comment goc cua 1 bai. limit=1 -> 1 request re, chi doc `total`."""
    data = _get(
        client,
        COMMENT_API,
        {
            "offset": 0,
            "limit": 1,
            "frommobile": 0,
            "sort": "like",
            "is_onload": 1,
            "objectid": article_id,
            "objecttype": 1,
            "siteid": 1000000,
        },
    )
    return int(data.get("total") or 0)


def fetch_root_comments(client: httpx.Client, article_id: str) -> list[dict]:
    """TOAN BO comment goc cua 1 bai (co phan trang)."""
    items: list[dict] = []
    offset = 0
    while True:
        data = _get(
            client,
            COMMENT_API,
            {
                "offset": offset,
                "limit": PAGE_SIZE,
                "frommobile": 0,
                "sort": "like",
                "is_onload": 1,
                "objectid": article_id,
                "objecttype": 1,
                "siteid": 1000000,
            },
        )
        batch = data.get("items") or []
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(data.get("total") or 0):
            break
        time.sleep(REQUEST_DELAY)
    return items


def fetch_replies(client: httpx.Client, article_id: str, comment_id: int) -> list[dict]:
    """TOAN BO reply cua 1 comment goc.

    `replys.items` trong tra ve cua COMMENT_API luon RONG du `replys.total` > 0
    -> phai goi rieng endpoint nay.
    """
    items: list[dict] = []
    offset = 0
    while True:
        data = _get(
            client,
            REPLY_API,
            {
                "siteid": 1000000,
                "objectid": article_id,  # BAI, khong phai comment
                "objecttype": 1,
                "id": comment_id,  # comment goc
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        batch = data.get("items") or []
        items.extend(batch)
        offset += len(batch)
        if not batch or len(batch) < PAGE_SIZE:
            break
        time.sleep(REQUEST_DELAY)
    return items


def to_post(comment: dict, article_url: str, parent_id: str | None = None) -> dict:
    """Comment VnExpress -> dict theo schemas.py::Post.

    `userlike` moi la so luot thich. `rating` la dict RONG - dung no thi
    engagement luon = 0 va Q3 (xep hang theo reach) mat y nghia.
    """
    created = datetime.fromtimestamp(comment["creation_time"], tz=timezone.utc)
    return {
        "post_id": f"vne-{comment['comment_id']}",
        "platform": "vnexpress_comment",
        "url": article_url,
        "author_hash": _hash_author(comment["userid"]),
        "content": _clean_content(comment["content"]),
        "created_at": created.isoformat(),
        "engagement": int(comment.get("userlike") or 0),
        "parent_id": parent_id,
    }


def fetch_thread(client: httpx.Client, article_id: str, article_url: str) -> list[dict]:
    """1 bai -> toan bo luong thao luan: comment goc + reply cua tung goc."""
    posts: list[dict] = []
    roots = fetch_root_comments(client, article_id)
    n_replies = 0

    for root in roots:
        posts.append(to_post(root, article_url))
        if not (root.get("replys") or {}).get("total"):
            continue
        root_post_id = f"vne-{root['comment_id']}"
        for reply in fetch_replies(client, article_id, root["comment_id"]):
            posts.append(to_post(reply, article_url, parent_id=root_post_id))
            n_replies += 1
        time.sleep(REQUEST_DELAY)

    print(f"  {article_id}: {len(roots):>3d} gốc + {n_replies:>3d} reply")
    return posts


def _thread_order(posts: list[dict]):
    """Key sap xep sao cho MOI LUONG nam lien nhau: goc roi den reply cua no.

    Giu mang PHANG (schemas.py::Post phang, loader.load_post() nhan tung post) -
    long JSON vao la pha contract. Nhung sap theo created_at TOAN CUC thi reply
    nam cach goc trung binh 176 phan tu (xa nhat 1.542) -> khong ai doc noi.

    Thu tu: cac luong theo thoi gian goc; trong moi luong, goc truoc, reply sau
    (theo thoi gian).
    """
    root_time = {p["post_id"]: p["created_at"] for p in posts if p["parent_id"] is None}

    def key(post: dict) -> tuple[str, int, str]:
        if post["parent_id"] is None:
            return (post["created_at"], 0, "")
        return (root_time.get(post["parent_id"], post["created_at"]), 1, post["created_at"])

    return key


def main() -> None:
    articles = fetch_articles()
    print(f"  {len(articles)} bài từ trang chủ đề\n")

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        # Chon bai nhieu thao luan nhat. Probe limit=1 -> re, chi doc `total`.
        counts = {}
        for article_id in articles:
            counts[article_id] = count_comments(client, article_id)
            time.sleep(REQUEST_DELAY)
        top = sorted(counts, key=counts.get, reverse=True)[:MAX_ARTICLES]
        print(f"  Lấy {len(top)}/{len(articles)} bài nhiều thảo luận nhất:\n")

        posts: list[dict] = []
        seen: set[str] = set()
        for article_id in top:
            for post in fetch_thread(client, article_id, articles[article_id]):
                if post["post_id"] in seen:
                    continue
                seen.add(post["post_id"])
                posts.append(post)

    posts.sort(key=_thread_order(posts))
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    if posts:
        roots = sum(1 for p in posts if p["parent_id"] is None)
        print(f"\n  {len(posts):,} post ({roots:,} gốc + {len(posts) - roots:,} reply)")
        print(f"  -> {OUT_FILE}")
        print(f"  thời gian: {posts[0]['created_at'][:10]} → {posts[-1]['created_at'][:10]}")


if __name__ == "__main__":
    main()
