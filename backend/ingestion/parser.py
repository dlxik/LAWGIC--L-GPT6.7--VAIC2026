"""[P1] Tach van ban -> cay Dieu / Khoan / Diem.

Regex lam chinh, LLM chi va cho regex fail (bang, phu luc).
Output: LegalDocument (backend/models/schemas.py)

Cau truc thuc te (da xac minh tren qlt2019 / qlt2025 / tncn2025):

    Chuong I                       <- so La Ma, KHONG co tieu de cung dong
    QUY DINH CHUNG                 <- tieu de o DONG SAU, viet HOA
    Muc 1. DANG KY THUE            <- tieu de CUNG dong (khac Chuong)
    Dieu 1. Pham vi dieu chinh     <- Dieu + tieu de CUNG dong
    Luat nay quy dinh viec...      <- BODY
    Dieu 2. Doi tuong ap dung
    1. Nguoi nop thue bao gom:     <- Khoan
    a) To chuc, ho gia dinh...     <- Diem
    d) To chuc, ca nhan khau tru   <- co diem "d" (d gach ngang)

schemas.py KHONG co model Chapter/Section -> Chuong va Muc duoc NHAN DIEN nhung
KHONG LUU. Van phai nhan dien: neu khong, tieu de cua chung bi nuot vao text cua
node truoc do (do tren van ban that: 13 node dinh loi Muc).
"""

from __future__ import annotations

import re
import unicodedata

# Chuong: chi co so La Ma tren dong, tieu de nam o DONG KE TIEP
RE_CHAPTER = re.compile(r"^Chương\s+([IVXLCDM]+)\s*$")
# Muc: tieu de nam CUNG DONG. Muc 2, 3, 4... nam GIUA chuong, ngay sau mot Khoan
# -> current_article khong None -> khong nhan dien thi roi vao BODY.
RE_SECTION = re.compile(r"^Mục\s+(\d+)\b")
RE_ARTICLE = re.compile(r"^Điều\s+(\d+)\s*[.．]\s*(.*)$")
RE_CLAUSE = re.compile(r"^(\d{1,2})\s*[.．]\s+(.+)$")
RE_POINT = re.compile(r"^([a-zđ])\)\s*(.+)$")
# Cau ket + chu ky, sau Dieu cuoi cung. Khong thuoc cay Dieu-Khoan-Diem -> gap la
# DUNG han. Bien the that: "Luat nay duoc" (khong co "da"), "Cong hoa"/"Cong hoa".
RE_CLOSING = re.compile(
    r"^(?:Luật|Bộ luật|Nghị định|Thông tư|Nghị quyết|Quyết định)\s+này\s+(?:đã\s+)?được\s+"
    r"(?:Quốc hội|Chính phủ|Ủy ban Thường vụ Quốc hội)"
)
# Moc cau truc lot vao text = parser sot mot cap. Dung cho check #6 trong validate().
# Chi bat dang TIEU DE (theo sau la chu HOA), khong bat tham chieu trong cau:
#   "Muc 2. KHAI THUE"        -> tieu de bi nuot   -> BAT
#   "quy dinh tai Muc 2 cua"  -> tham chieu hop le -> BO QUA
RE_HEADING_LEAK = re.compile(
    r"\b(?:Mục\s+\d+\s*[.．]|Chương\s+[IVXLCDM]+)\s+[A-ZĐÁÀẢÃẠÂÊÔƠƯ]{2,}"
)

# Thu tu chu cai tieng Viet dung cho Diem: khong co f, j, w, z; "d" dung sau "d".
# Dung string.ascii_lowercase la sai ngay o Diem thu 5.
VN_LETTERS = "abcdđeghiklmnopqrstuvxy"

# Do phu tren nguong nay coi la sach. Khong dat 1.0 vi noi BODY bang dau cach
# lam parsed_chars nhinh hon expected_chars vai phan nghin.
MIN_COVERAGE = 0.98


def _normalize(raw_text: str) -> list[str]:
    """Chuan hoa roi tach dong, bo dong trong.

    NFC la BAT BUOC: neu nguon tra ve dang phan ra (D + dau ngang), chuoi "Dieu"
    trong regex se khong khop du nhin mat thuong giong het.
    """
    text = unicodedata.normalize("NFC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ")  # no-break space -> space thuong
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def parse_articles(text: str) -> list[dict]:
    """Text tho -> list[Article]. May trang thai, KHONG phai quet regex toan file.

    Ngan xep: Dieu -> Khoan -> Diem. Dong BODY duoc gan vao node o dinh ngan xep.

    Hai bat bien duoc cuong che bang CAU TRUC CODE, khong phai bang assert:
      - Khoan chi hop le khi da co Dieu (current_article is not None)
      - Diem chi hop le khi da co Khoan (current_clause is not None)
    Nho vay phan mo dau "Can cu Hien phap..." khong bi hieu nham thanh Khoan.
    """
    articles: list[dict] = []
    current_article: dict | None = None
    current_clause: dict | None = None
    current_point: dict | None = None
    skip_next_line = False  # dong tieu de cua Chuong

    for line in _normalize(text):
        if skip_next_line:
            skip_next_line = False
            continue

        if RE_CLOSING.match(line):
            break  # het phan quy pham; phia sau chi con chu ky

        if RE_CHAPTER.match(line):
            skip_next_line = True  # tieu de Chuong o dong SAU -> nuot them 1 dong
            current_article = current_clause = current_point = None
            continue

        if RE_SECTION.match(line):
            # Tieu de Muc CUNG dong -> khong skip. Reset ngan xep vi Muc la ranh
            # gioi cau truc; dong ke tiep luon la mot Dieu moi.
            current_article = current_clause = current_point = None
            continue

        if match := RE_ARTICLE.match(line):
            current_article = {
                "number": int(match.group(1)),
                "heading": match.group(2).strip(),
                "text": "",
                "clauses": [],
            }
            articles.append(current_article)
            current_clause = current_point = None
            continue

        if current_article is None:
            continue  # phan mo dau -> bo qua

        if match := RE_CLAUSE.match(line):
            current_clause = {
                "number": int(match.group(1)),
                "text": match.group(2).strip(),
                "points": [],
            }
            current_article["clauses"].append(current_clause)
            current_point = None
            continue

        if current_clause is not None and (match := RE_POINT.match(line)):
            current_point = {"letter": match.group(1), "text": match.group(2).strip()}
            current_clause["points"].append(current_point)
            continue

        # BODY: gan vao node o dinh ngan xep (Diem > Khoan > Dieu)
        target = current_point or current_clause or current_article
        target["text"] = f"{target['text']} {line}".strip()

    return articles


def _expected_content_length(text: str) -> int:
    """So ky tu THUOC cay Dieu-Khoan-Diem, tinh y het parse_articles().

    Check #7 phai do "co nuot noi dung khong", KHONG duoc phat vi da vut
    boilerplate co chu dich (mo dau, tieu de Chuong/Muc, cau ket). Neu so voi
    tong ky tu tho thi van ban that ra 97% con mau test ti hon ra 72% - cung mot
    parser, khac nhau chi vi ti le boilerplate.
    """
    total = 0
    started = False
    skip_next_line = False

    for line in _normalize(text):
        if skip_next_line:
            skip_next_line = False
            continue
        if RE_CLOSING.match(line):
            break
        if RE_CHAPTER.match(line):
            skip_next_line = True
            continue
        if RE_SECTION.match(line):
            continue
        if match := RE_ARTICLE.match(line):
            started = True
            total += len(match.group(2).strip())  # chi phan heading duoc giu
            continue
        if not started:
            continue  # phan mo dau
        if match := RE_CLAUSE.match(line):
            total += len(match.group(2).strip())
        elif match := RE_POINT.match(line):
            total += len(match.group(2).strip())
        else:
            total += len(line)

    return total


def _parsed_content_length(articles: list[dict]) -> int:
    """So ky tu parser thuc su giu lai, tren moi node."""
    return sum(
        len(article["heading"])
        + len(article["text"])
        + sum(
            len(clause["text"]) + sum(len(point["text"]) for point in clause["points"])
            for clause in article["clauses"]
        )
        for article in articles
    )


def _assign_ids(doc_id: str, articles: list[dict]) -> None:
    """Sinh node_id tai cho. Contract voi P2: "nd168-d5-k2-a".

    ID sinh tu VI TRI trong van ban, khong tu bo dem chay -> ON DINH giua cac lan
    chay. Bo dem chay -> them 1 Dieu o giua -> moi ID sau do dich -> MERGE cua P2
    de node ma.
    """
    for article in articles:
        article["article_id"] = f"{doc_id}-d{article['number']}"
        for clause in article["clauses"]:
            clause["clause_id"] = f"{article['article_id']}-k{clause['number']}"
            for point in clause["points"]:
                point["point_id"] = f"{clause['clause_id']}-{point['letter']}"


def _assign_temporal(
    articles: list[dict],
    default_from: str,
    default_to: str | None,
    overrides: dict[int, str] | None = None,
) -> None:
    """Gan effective_from / effective_to cho MOI node (Temporal trong schemas.py).

    Mac dinh lay tu hieu luc cua van ban. `overrides` xu ly truong hop mot so Dieu
    co hieu luc khac phan con lai - VD Luat QLT 2025 hieu luc 2026-07-01 NHUNG
    Dieu 13 va Dieu 26 hieu luc 2026-01-01.

    Hieu luc cua Dieu chay xuong Khoan va Diem cua no. Theo docstring Temporal,
    node sau nhat giu su that - nhung parser khong biet gi hon van ban, nen gan
    cung gia tri ca 3 tang. P2 doc o tang sau nhat.
    """
    overrides = overrides or {}
    for article in articles:
        effective_from = overrides.get(article["number"], default_from)
        nodes = [
            article,
            *article["clauses"],
            *(point for clause in article["clauses"] for point in clause["points"]),
        ]
        for node in nodes:
            node["effective_from"] = effective_from
            node["effective_to"] = default_to


def parse_document(
    raw_text: str,
    doc_meta: dict,
    effective_overrides: dict[int, str] | None = None,
) -> dict:
    """Text tho -> dict theo schema LegalDocument. Ham chinh cua P1.

    doc_meta phai co: doc_id, doc_number, title, issuer, issued_date,
    effective_date, source_url (xem backend/models/schemas.py).

    effective_overrides: {article_number: iso_date} cho Dieu co hieu luc khac
    phan con lai cua chinh van ban do.
    """
    articles = parse_articles(raw_text)
    _assign_ids(doc_meta["doc_id"], articles)
    _assign_temporal(
        articles,
        default_from=doc_meta["effective_date"],
        default_to=doc_meta.get("expiry_date"),
        overrides=effective_overrides,
    )
    return {**doc_meta, "articles": articles}


# ---------------------------------------------------------------------------
# Kiem tra bat bien - chay tren 100% node, gan nhu mien phi
# ---------------------------------------------------------------------------


def _iter_nodes(article: dict):
    """Duyet moi node co text trong 1 Dieu: (node_id, text)."""
    yield article["article_id"], article["text"]
    for clause in article["clauses"]:
        yield clause["clause_id"], clause["text"]
        for point in clause["points"]:
            yield point["point_id"], point["text"]


def validate(doc: dict, raw_text: str) -> list[str]:
    """Tra list loi. Rong = sach.

    Bat loi HE THONG tren toan bo node. Kiem tra tay chi phu ~20 node (1%), con
    day phu 100%. Can ca hai: bat bien bat loi he thong, mat nguoi bat loi tinh vi.
    """
    errors: list[str] = []
    articles = doc["articles"]

    # 1. So Dieu duy nhat -> node_id khong dung nhau -> MERGE cua P2 khong de node ma
    numbers = [article["number"] for article in articles]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        errors.append(f"Dieu trung: {duplicates}")

    # 2. So Dieu tang dan lien tuc tu 1
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"Dieu khong lien tuc: dem {len(numbers)}, max {max(numbers)}")

    for article in articles:
        # 3. Khoan tang dan lien tuc -> loc duoc so tien / ngay thang bi bat nham
        clause_numbers = [clause["number"] for clause in article["clauses"]]
        if clause_numbers and clause_numbers != list(range(1, len(clause_numbers) + 1)):
            errors.append(
                f"Dieu {article['number']}: Khoan khong lien tuc {clause_numbers}"
            )

        for clause in article["clauses"]:
            # 4. Diem dung thu tu bang chu cai tieng Viet: a,b,c,d,d,e,g...
            letters = [point["letter"] for point in clause["points"]]
            if letters and letters != list(VN_LETTERS[: len(letters)]):
                errors.append(
                    f"Dieu {article['number']} Khoan {clause['number']}: "
                    f"Diem sai thu tu {letters}"
                )

            # 5. Moi node phai co text
            if not clause["text"]:
                errors.append(f"{clause['clause_id']}: text rong")
            for point in clause["points"]:
                if not point["text"]:
                    errors.append(f"{point['point_id']}: text rong")

        # 6. Moc cau truc khong duoc lot vao text cua node. Bat CA LOP bug nay:
        #    them cap moi (Phan, Tieu muc) ma quen nhan dien -> test do ngay, thay
        #    vi nuot im lang. KHONG bat "Dieu N" vi "quy dinh tai Dieu 85 cua Luat
        #    nay" la tham chieu HOP LE.
        for node_id, text in _iter_nodes(article):
            if match := RE_HEADING_LEAK.search(text):
                errors.append(f"{node_id}: lot moc cau truc vao text -> {match.group(0)!r}")

    # 7. Do phu ky tu. BAT LOI IM LANG NGUY HIEM NHAT: parser chay khong loi, ra
    #    JSON dep, nhung nuot mat ca doan ma khong ai biet.
    parsed_chars = _parsed_content_length(articles)
    expected_chars = _expected_content_length(raw_text)
    if expected_chars and parsed_chars / expected_chars < MIN_COVERAGE:
        errors.append(
            f"Do phu chi {parsed_chars / expected_chars:.1%} "
            f"({parsed_chars:,}/{expected_chars:,} ky tu) - dang nuot noi dung"
        )

    return errors
