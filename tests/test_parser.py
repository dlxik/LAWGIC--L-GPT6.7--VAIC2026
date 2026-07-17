"""[P1] Test parser + kiem tra bat bien tren van ban that.

Chay:  pytest tests/test_parser.py -v

Hai tang:
  - Unit  : text tong hop, chay <1ms, khoa tung hanh vi rieng le
  - Tich hop: 3 van ban that trong data/raw/, 2.055 node, khoa toan he thong
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ingestion.parser import (  # noqa: E402
    VN_LETTERS,
    parse_articles,
    parse_document,
    validate,
)
from backend.models.schemas import LegalDocument  # noqa: E402
from scripts.fetch_legal_docs import DOCS, EFFECTIVE_OVERRIDES, build, fetch  # noqa: E402

META = {
    "doc_id": "test",
    "doc_number": "00/2026/QH15",
    "title": "Luật thử",
    "issuer": "Quốc hội",
    "issued_date": "2026-01-01",
    "effective_date": "2026-07-01",
    "expiry_date": None,
    "status": "ACTIVE",
    "source_url": "https://example.invalid",
}

# Trich nguyen van cau truc that cua qlt2025 (tieu de Chuong o DONG SAU)
SAMPLE = """\
QUỐC HỘI
Luật số: 108/2025/QH15
Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Quốc hội ban hành Luật Quản lý thuế.
Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Luật này quy định việc quản lý các loại thuế.
Điều 2. Đối tượng áp dụng
1. Người nộp thuế bao gồm:
a) Tổ chức, hộ gia đình, hộ kinh doanh, cá nhân nộp thuế theo quy định của pháp luật về thuế;
b) Tổ chức nước ngoài, cá nhân nước ngoài có hoạt động kinh doanh tại Việt Nam;
c) Tổ chức, hộ gia đình, cá nhân nộp các khoản thu khác thuộc ngân sách nhà nước;
d) Tổ chức, cá nhân khấu trừ thuế theo quy định của pháp luật về thuế;
đ) Tổ chức, cá nhân thực hiện khấu trừ, nộp thay số thuế đã khấu trừ.
2. Cơ quan quản lý thuế bao gồm cơ quan thuế và cơ quan hải quan các cấp theo quy định.
Chương II
CÁC CHỨC NĂNG QUẢN LÝ THUẾ
Mục 1. ĐĂNG KÝ THUẾ
Điều 3. Nội dung quản lý thuế
Nội dung quản lý thuế bao gồm đăng ký thuế, khai thuế, tính thuế, nộp thuế, hoàn thuế, miễn thuế, giảm thuế và quản lý nợ thuế theo quy định tại Mục 2 của Luật này. Cơ quan quản lý thuế thực hiện các nội dung này theo nguyên tắc quản lý rủi ro và trên cơ sở dữ liệu số.
Mục 2. KHAI THUẾ
Điều 4. Khai thuế
Người nộp thuế phải khai thuế chính xác, trung thực, đầy đủ và nộp hồ sơ thuế đúng thời hạn; chịu trách nhiệm trước pháp luật về tính chính xác, trung thực, đầy đủ của hồ sơ thuế đã nộp cho cơ quan quản lý thuế.
Luật này được Quốc hội nước Cộng hòa xã hội chủ nghĩa Việt Nam khóa XV, Kỳ họp thứ 10 thông qua ngày 10 tháng 12 năm 2025.
CHỦ TỊCH QUỐC HỘITrần Thanh Mẫn
"""


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


def test_extracts_correct_article_numbers():
    articles = parse_articles(SAMPLE)
    assert [article["number"] for article in articles] == [1, 2, 3, 4]
    assert articles[0]["heading"] == "Phạm vi điều chỉnh"


def test_section_heading_not_leaked_into_text():
    """'Muc 1. DANG KY THUE' - tieu de CUNG dong, khac Chuong (tieu de dong sau).

    Muc 2,3,4... nam GIUA chuong, ngay sau mot Khoan -> current_article khong None ->
    khong nhan dien thi roi vao BODY. Tren van ban that: 13 node bi nuot.
    """
    articles = parse_articles(SAMPLE)
    all_text = " ".join(
        article["text"]
        + "".join(
            clause["text"] + "".join(point["text"] for point in clause["points"])
            for clause in article["clauses"]
        )
        for article in articles
    )
    assert "ĐĂNG KÝ THUẾ" not in all_text  # tieu de Muc 1
    assert "KHAI THUẾ" not in all_text  # tieu de Muc 2


def test_inline_section_reference_is_preserved():
    """'quy dinh tai Muc 2 cua Luat nay' la THAM CHIEU, khong phai tieu de.

    Check #6 chi bat dang tieu de (theo sau la chu HOA) -> khong duoc bao
    dong gia o day, neu khong parser bi ep xoa noi dung that.
    """
    articles = parse_articles(SAMPLE)
    assert "Mục 2 của Luật này" in articles[2]["text"]
    doc = parse_document(SAMPLE, META)
    assert validate(doc, SAMPLE) == []


def test_validate_detects_leaked_structural_heading():
    """Check #6 bat CA LOP bug: them cap moi (Phan, Tieu muc) ma quen nhan
    dien -> test do ngay, thay vi nuot im lang."""
    doc = parse_document(SAMPLE, META)
    doc["articles"][0]["text"] += " Mục 9. QUY ĐỊNH KHÁC"
    assert any("lot moc cau truc" in error for error in validate(doc, SAMPLE))


def test_preamble_produces_no_orphan_clause():
    """'Luật số: 108/2025/QH15' va 'Can cu Hien phap...' dung TRUOC moi Dieu.

    Khong duoc hieu nham thanh Khoan. Bat bien nay do CAU TRUC code cuong che
    (current_article is None -> continue), khong phai do regex phuc tap.
    """
    articles = parse_articles(SAMPLE)
    assert sum(len(article["clauses"]) for article in articles) == 2  # chi Dieu 2 co Khoan


def test_chapter_heading_not_leaked_into_text():
    """schemas.py khong co model Chapter -> Chuong bi vut.

    Nhung phai NHAN DIEN: neu khong, 'Chuong II' + 'CAC CHUC NANG QUAN LY THUE'
    bi noi vao text cua Dieu 2 (Dieu cuoi chuong I). Bug im lang - JSON van dep.
    """
    articles = parse_articles(SAMPLE)
    all_text = " ".join(
        article["heading"]
        + article["text"]
        + "".join(
            clause["text"] + "".join(point["text"] for point in clause["points"])
            for clause in article["clauses"]
        )
        for article in articles
    )
    assert "Chương" not in all_text
    assert "CÁC CHỨC NĂNG" not in all_text


def test_vietnamese_point_letters():
    """Bang chu cai tieng Viet co 'd' va KHONG co f/j/w/z.

    Dung string.ascii_lowercase la sai ngay o Diem thu 5.
    """
    articles = parse_articles(SAMPLE)
    letters = [point["letter"] for point in articles[1]["clauses"][0]["points"]]
    assert letters == ["a", "b", "c", "d", "đ"]  # "đ" dung SAU "d", khong phai sau "z"
    assert "đ" in VN_LETTERS and "f" not in VN_LETTERS


def test_body_attaches_to_stack_top():
    articles = parse_articles(SAMPLE)
    assert articles[0]["text"] == "Luật này quy định việc quản lý các loại thuế."


def test_closing_formula_not_leaked_into_last_article():
    """'Luat nay duoc Quoc hoi... thong qua ngay...' + chu ky khong thuoc cay
    Dieu-Khoan-Diem. Khong dung han thi chung bi noi vao Khoan cuoi cua Dieu cuoi.

    Ca 3 van ban that deu dinh loi nay truoc khi vá. Bien the: "duoc" khong co
    "da", "Cong hoa"/"Cong hoa", "ky hop"/"Ky hop".
    """
    articles = parse_articles(SAMPLE)
    tail = articles[-1]["text"]
    assert "thông qua ngày" not in tail
    assert "CHỦ TỊCH QUỐC HỘI" not in tail
    assert tail.endswith("cho cơ quan quản lý thuế.")


def test_nfc_normalization_required():
    """Tieng Viet co 2 cach ma hoa cung mot chu, nhin mat thuong GIONG HET.

    NFD: 'D' = D + dau ngang (2 ky tu). Regex '^Dieu' chi khop NFC.
    Thieu normalize -> parser ra 0 Dieu va ban debug regex 2 tieng vo ich.
    """
    import unicodedata

    nfd = unicodedata.normalize("NFD", SAMPLE)
    assert nfd != SAMPLE  # thuc su khac o muc byte
    assert len(parse_articles(nfd)) == 4  # nhung parser van ra dung


def test_node_id_matches_contract_and_is_stable():
    """'nd168-d5-k2-a'. Sinh tu VI TRI, khong tu bo dem chay.

    Bo dem chay -> them 1 Dieu o giua -> moi ID sau do dich -> MERGE cua P2 de node ma.
    """
    doc = parse_document(SAMPLE, META)
    clause = doc["articles"][1]["clauses"][0]
    assert doc["articles"][1]["article_id"] == "test-d2"
    assert clause["clause_id"] == "test-d2-k1"
    assert clause["points"][0]["point_id"] == "test-d2-k1-a"
    assert parse_document(SAMPLE, META) == doc  # chay lai ra y het


def test_temporal_defaults_from_document():
    doc = parse_document(SAMPLE, META)
    article = doc["articles"][0]
    assert article["effective_from"] == "2026-07-01"
    assert article["effective_to"] is None
    point = doc["articles"][1]["clauses"][0]["points"][0]
    assert point["effective_from"] == "2026-07-01"  # chay xuong tan Diem


def test_temporal_override_per_article():
    """Luat QLT 2025 hieu luc 01/7/2026 TRU Dieu 13 & 26 hieu luc 01/01/2026.

    Day la thu vector store khong lam duoc: cung mot luat, cac Dieu song o moc khac nhau.
    """
    doc = parse_document(SAMPLE, META, effective_overrides={2: "2026-01-01"})
    eff = {article["number"]: article["effective_from"] for article in doc["articles"]}
    assert eff == {1: "2026-07-01", 2: "2026-01-01", 3: "2026-07-01", 4: "2026-07-01"}
    # override chay xuong Khoan va Diem cua Dieu do
    assert doc["articles"][1]["clauses"][0]["points"][0]["effective_from"] == "2026-01-01"


def test_validate_detects_non_sequential_clauses():
    doc = parse_document(SAMPLE, META)
    doc["articles"][1]["clauses"][0]["number"] = 7  # gia lap bat nham "50.000.000"
    assert any("Khoan khong lien tuc" in error for error in validate(doc, SAMPLE))


def test_validate_detects_dropped_content():
    """Bat bien QUAN TRONG NHAT: parser chay khong loi, JSON dep, nhung mat 1/3 van ban."""
    doc = parse_document(SAMPLE, META)
    doc["articles"] = doc["articles"][:1]
    assert any("Do phu" in error for error in validate(doc, SAMPLE))


# ---------------------------------------------------------------------------
# Tich hop - van ban that
# ---------------------------------------------------------------------------

DOC_IDS = list(DOCS)
EXPECTED_NODES = {"qlt2019": 1194, "qlt2025": 662, "tncn2025": 199}


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_real_document_parses_clean(doc_id):
    """6 bat bien tren 100% node. Kiem tra tay chi phu ~20 node (1%)."""
    raw = fetch(doc_id)
    doc = parse_document(raw, DOCS[doc_id], EFFECTIVE_OVERRIDES.get(doc_id))
    assert validate(doc, raw) == []


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_real_document_matches_contract(doc_id):
    """Sai schema phai bat o day, khong de P2 phat hien o moc gio 8."""
    LegalDocument.model_validate(build(doc_id))


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_node_count_does_not_regress(doc_id):
    """Khoa so node. Sua regex lam mat 200 Diem -> test do, khong phai P2 do."""
    doc = build(doc_id)
    n = (
        len(doc["articles"])
        + sum(len(article["clauses"]) for article in doc["articles"])
        + sum(
            len(clause["points"])
            for article in doc["articles"]
            for clause in article["clauses"]
        )
    )
    assert n == EXPECTED_NODES[doc_id]


def test_qlt2025_articles_13_and_26_take_effect_early():
    """Kiem chung tren VAN BAN THAT, khong phai mock.

    Nguon: Luat QLT 2025 hieu luc 01/7/2026, tru Dieu 13 va Dieu 26 -> 01/01/2026.
    Day la du lieu nuoi cau demo "luat noi gi tai ngay X".
    """
    eff = {article["number"]: article["effective_from"] for article in build("qlt2025")["articles"]}
    assert eff[13] == "2026-01-01"
    assert eff[26] == "2026-01-01"
    assert eff[1] == "2026-07-01"


def test_qlt2019_expires_when_qlt2025_takes_effect():
    """Nua khoang [from, to): effective_to = NGAY DAU TIEN HET hieu luc.

    Ghi 2026-06-30 -> ngay 30/6 luat bien mat. Ngay 15/6 va 15/7 van pass ke ca
    khi quy uoc sai, nen chung CHE bug. Chi ngay bien lo ra.
    """
    old, new = build("qlt2019"), build("qlt2025")
    assert old["articles"][0]["effective_to"] == new["effective_date"] == "2026-07-01"


def test_old_new_document_pair_exists():
    """Khong co cap nay thi diffing.py cua P2 khong co gi de chay.

    replaces phai SONG SOT qua Pydantic - neu schemas.py thieu field, no bi nuot
    im lang -> loader.py:237 khong tao REPLACES -> SUPERSEDED_BY khong bao gio sinh.
    """
    doc = LegalDocument.model_validate(build("qlt2025"))
    assert doc.replaces == "qlt2019"
