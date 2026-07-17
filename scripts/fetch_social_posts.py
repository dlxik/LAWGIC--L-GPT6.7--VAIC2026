"""[P3] Crawl binh luan cong khai -> data/raw/social_posts/*.json

Nguon: comment bao dien tu (VnExpress, Tuoi Tre, Dan Tri), den 2026-07-17.
CHI lay noi dung cong khai. Hash author_id. KHONG luu ten/email that.
Output: list[Post] theo backend/models/schemas.py
"""


def fetch_comments(article_url: str) -> list[dict]:
    raise NotImplementedError


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
