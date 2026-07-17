"""[P1] Tach van ban -> cay Chuong / Dieu / Khoan / Diem.

Regex lam chinh, LLM chi va cho regex fail (bang, phu luc).
Output: LegalDocument (backend/models/schemas.py)
"""

import re

RE_CHAPTER = re.compile(r"^Chuong\s+([IVXLC]+)\s*[.．]?\s*(.*)$", re.M)
RE_ARTICLE = re.compile(r"^Điều\s+(\d+)\s*[.．]\s*(.*)$", re.M)
RE_CLAUSE = re.compile(r"^(\d{1,2})\s*[.．]\s+(.+)$", re.M)
RE_POINT = re.compile(r"^([a-zđ])\)\s*(.+)$", re.M)


def parse_document(raw_html: str, doc_meta: dict) -> dict:
    """HTML tho -> dict theo schema LegalDocument. Ham chinh cua P1."""
    raise NotImplementedError


def parse_articles(text: str) -> list[dict]:
    raise NotImplementedError
