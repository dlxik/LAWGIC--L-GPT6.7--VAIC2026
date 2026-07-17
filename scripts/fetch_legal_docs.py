"""[P1] Doc van ban tu data/raw/*.docx -> data/processed/<doc_id>.json

KHONG CRAWL. Da xac minh bang thuc nghiem (17/07/2026):
  - thuvienphapluat.vn : HTTP 403 tren trang van ban (chan bot). Homepage 200 la bay.
  - vanban.chinhphu.vn : PDF scan, 195 ky tu / 21 trang -> khong co text layer.
    File .signed.pdf co Producer = "Kodak Alaris Inc." => in ra giay roi quet lai.
  - luatvietnam.vn     : paywall toan van.

=> Ba van ban demo tai TAY tu thuvienphapluat duoi dang .docx (trinh duyet nguoi
   that vao binh thuong, chi curl bi 403) roi commit vao data/raw/.
   Chinh xac 100%, tai lap duoc, khong OCR. OCR doc nham SO ("500 trieu" ->
   "5OO trieu") -> citation bia -> nguy hiem hon ca tu choi tra loi.

.docx = zip chua word/document.xml. Doc bang zipfile + re (thu vien chuan),
KHONG can python-docx, KHONG can beautifulsoup4.

Chay:  python scripts/fetch_legal_docs.py
"""

from __future__ import annotations

import html
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ingestion.parser import parse_document, validate  # noqa: E402
from backend.models.schemas import LegalDocument  # noqa: E402

# Duong dan tuyet doi tu goc repo — chay pytest tu thu muc nao cung dung.
# Truoc day la Path("data/raw") tuong doi theo cwd -> chay pytest tu tests/ la gay.
_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = _ROOT / "data" / "raw" / "legal_docs"
OUT_DIR = _ROOT / "data" / "processed" / "legal_docs_structured"

# ---------------------------------------------------------------------------
# Ba van ban demo. doc_id slug TAY - khong tu sinh (tu sinh ra "nd1082025qh15").
# expiry_date cua qlt2019 = NGAY qlt2025 CO HIEU LUC (nua khoang [from, to),
# xem quy uoc trong backend/models/schemas.py::Temporal).
# ---------------------------------------------------------------------------

DOCS: dict[str, dict] = {
    "qlt2019": {
        "doc_id": "qlt2019",
        "doc_number": "38/2019/QH14",
        "title": "Luật Quản lý thuế",
        "issuer": "Quốc hội",
        "issued_date": "2019-06-13",
        "effective_date": "2020-07-01",
        "expiry_date": "2026-07-01",  # = ngay qlt2025 co hieu luc
        "status": "SUPERSEDED",
        "source_url": "https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-quan-ly-thue-2019-387595.aspx",
    },
    "qlt2025": {
        "doc_id": "qlt2025",
        "doc_number": "108/2025/QH15",
        "title": "Luật Quản lý thuế",
        "issuer": "Quốc hội",
        "issued_date": "2025-12-10",
        "effective_date": "2026-07-01",
        "expiry_date": None,
        "status": "ACTIVE",
        "source_url": "https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-Quan-ly-thue-2025-so-108-2025-QH15-675268.aspx",
        # loader.py:237 doc field nay de tao quan he (:LegalDocument)-[:REPLACES]->
        "replaces": "qlt2019",
    },
    "tncn2025": {
        "doc_id": "tncn2025",
        "doc_number": "109/2025/QH15",
        "title": "Luật Thuế thu nhập cá nhân",
        "issuer": "Quốc hội",
        "issued_date": "2025-12-10",
        "effective_date": "2026-07-01",
        "expiry_date": None,
        "status": "ACTIVE",
        "source_url": "https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-Thue-thu-nhap-ca-nhan-2025-so-109-2025-QH15-665870.aspx",
    },
}

# Dieu co hieu luc KHAC phan con lai cua chinh van ban do.
# Luat QLT 2025 hieu luc 01/7/2026, TRU Dieu 13 va Dieu 26 hieu luc 01/01/2026.
# Day la thu RAG vector khong lam duoc: cung mot luat, cac Dieu song o moc khac nhau.
# -> Q2_LAW_AS_OF ngay 2026-03-01 phai tra ve Dieu 13, 26 nhung KHONG tra ve Dieu 1.
#
# LUU Y (chua xu ly): nguon ghi Dieu 26 chi hieu luc som O PHAN hoa don dien tu cua
# ho/ca nhan kinh doanh, chu khong chac ca Dieu. Hien ap dung cho CA Dieu 26.
# Neu can chinh xac hon thi ha xuong muc Khoan - can doc ky Dieu 26 truoc.
EFFECTIVE_OVERRIDES: dict[str, dict[int, str]] = {
    "qlt2025": {13: "2026-01-01", 26: "2026-01-01"},
}


def read_docx(path: Path) -> str:
    """.docx -> text tho, moi doan mot dong.

    <w:p> = mot doan Word -> xuong dong. Nho vay "Dieu 5." luon dung dau dong,
    va neo "^" trong regex cua parser moi co nghia.
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    txt = re.sub(r"</w:p>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", txt))


def fetch(doc_id: str) -> str:
    """Tra text tho cua 1 van ban. Doc file local, KHONG tai mang."""
    path = RAW_DIR / f"{doc_id}.docx"
    if not path.exists():
        raise FileNotFoundError(
            f"Thieu {path}. Tai .docx tu {DOCS[doc_id]['source_url']} "
            f"(mo trinh duyet, KHONG dung curl - bi 403)."
        )
    return read_docx(path)


def build(doc_id: str) -> dict:
    """1 van ban -> dict LegalDocument da validate. Loi thi NEM, khong nuot."""
    raw = fetch(doc_id)
    doc = parse_document(raw, DOCS[doc_id], EFFECTIVE_OVERRIDES.get(doc_id))

    if errors := validate(doc, raw):
        raise ValueError(f"{doc_id}: parser ban - " + "; ".join(errors[:5]))

    # Ep qua contract chung. Bat sai schema NGAY, khong de P2 phat hien o gio 8.
    LegalDocument.model_validate(doc)
    return doc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for doc_id in DOCS:
        doc = build(doc_id)
        n = (
            len(doc["articles"])
            + sum(len(a["clauses"]) for a in doc["articles"])
            + sum(len(k["points"]) for a in doc["articles"] for k in a["clauses"])
        )
        total += n
        out = OUT_DIR / f"{doc_id}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {doc_id:9s} {n:>5,d} node  ->  {out}")
    print(f"  {'TONG':9s} {total:>5,d} node")


if __name__ == "__main__":
    main()
