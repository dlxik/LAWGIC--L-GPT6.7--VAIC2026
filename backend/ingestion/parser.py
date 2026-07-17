"""[P1] Tach van ban -> cay Dieu / Khoan / Diem.

Regex lam chinh, LLM chi va cho regex fail (bang, phu luc).
Output: LegalDocument (backend/models/schemas.py)

Cau truc thuc te (da xac minh tren qlt2019 / qlt2025 / tncn2025):

    Chuong I                       <- so La Ma, KHONG co tieu de cung dong
    QUY DINH CHUNG                 <- tieu de o DONG SAU, viet HOA
    Dieu 1. Pham vi dieu chinh     <- Dieu + tieu de CUNG dong
    Luat nay quy dinh viec...      <- BODY
    Dieu 2. Doi tuong ap dung
    1. Nguoi nop thue bao gom:     <- Khoan
    a) To chuc, ho gia dinh...     <- Diem
    ...
    d) To chuc, ca nhan thuc hien  <- co diem "d" (d gach ngang)

schemas.py KHONG co model Chapter -> Chuong duoc NHAN DIEN nhung KHONG LUU.
Van phai nhan dien: neu khong, 2 dong "Chuong I" + "QUY DINH CHUNG" bi nuot
vao text cua Dieu cuoi chuong truoc.
"""

import re
import unicodedata

# Chuong: chi co so La Ma tren dong, tieu de nam o dong ke tiep
RE_CHAPTER = re.compile(r"^Chương\s+([IVXLCDM]+)\s*$")
RE_ARTICLE = re.compile(r"^Điều\s+(\d+)\s*[.．]\s*(.*)$")
RE_CLAUSE = re.compile(r"^(\d{1,2})\s*[.．]\s+(.+)$")
RE_POINT = re.compile(r"^([a-zđ])\)\s*(.+)$")

# Thu tu chu cai tieng Viet dung cho Diem: khong co f, j, w, z; "d" dung sau "d"
VN_LETTERS = "abcdđeghiklmnopqrstuvxy"


def _normalize(raw: str) -> list[str]:
    """Chuan hoa roi tach dong, bo dong trong.

    NFC la BAT BUOC: neu nguon tra ve dang phan ra (D + dau ngang), chuoi
    "Dieu" trong regex se khong khop du nhin mat thuong giong het.
    """
    txt = unicodedata.normalize("NFC", raw)
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = txt.replace(" ", " ")  # no-break space -> space thuong
    out = []
    for line in txt.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            out.append(line)
    return out


def parse_articles(text: str) -> list[dict]:
    """Text tho -> list[Article]. May trang thai, KHONG phai quet regex toan file.

    Ngan xep: Dieu -> Khoan -> Diem. Dong BODY duoc gan vao node o dinh ngan xep.

    Hai bat bien duoc cuong che bang CAU TRUC CODE, khong phai bang assert:
      - Khoan chi hop le khi da co Dieu (cur_a is not None)
      - Diem chi hop le khi da co Khoan (cur_k is not None)
    Nho vay phan mo dau "Can cu Hien phap..." khong bi hieu nham thanh Khoan.
    """
    articles: list[dict] = []
    cur_a: dict | None = None
    cur_k: dict | None = None
    cur_p: dict | None = None
    skip_next = False  # dong tieu de chuong

    for line in _normalize(text):
        if skip_next:
            skip_next = False
            continue

        if RE_CHAPTER.match(line):
            skip_next = True  # nuot dong tieu de chuong
            cur_a = cur_k = cur_p = None
            continue

        if m := RE_ARTICLE.match(line):
            cur_a = {
                "number": int(m.group(1)),
                "heading": m.group(2).strip(),
                "text": "",
                "clauses": [],
            }
            articles.append(cur_a)
            cur_k = cur_p = None
            continue

        if cur_a is None:
            continue  # phan mo dau -> bo qua

        if m := RE_CLAUSE.match(line):
            cur_k = {"number": int(m.group(1)), "text": m.group(2).strip(), "points": []}
            cur_a["clauses"].append(cur_k)
            cur_p = None
            continue

        if cur_k is not None and (m := RE_POINT.match(line)):
            cur_p = {"letter": m.group(1), "text": m.group(2).strip()}
            cur_k["points"].append(cur_p)
            continue

        # BODY: gan vao node o dinh ngan xep (Diem > Khoan > Dieu)
        target = cur_p or cur_k or cur_a
        target["text"] = f"{target['text']} {line}".strip()

    return articles


def _assign_ids(doc_id: str, articles: list[dict]) -> None:
    """Sinh node_id tai cho. Contract voi P2: "nd168-d5-k2-a".

    ID phai ON DINH giua cac lan chay: parse lai phai ra ID y het, neu khong
    MERGE cua P2 se de node trung.
    """
    for a in articles:
        a["article_id"] = f"{doc_id}-d{a['number']}"
        for k in a["clauses"]:
            k["clause_id"] = f"{a['article_id']}-k{k['number']}"
            for p in k["points"]:
                p["point_id"] = f"{k['clause_id']}-{p['letter']}"


def parse_document(raw_text: str, doc_meta: dict) -> dict:
    """Text tho -> dict theo schema LegalDocument. Ham chinh cua P1.

    doc_meta phai co: doc_id, doc_number, title, issuer, issued_date,
    effective_date, source_url (xem backend/models/schemas.py).
    """
    articles = parse_articles(raw_text)
    _assign_ids(doc_meta["doc_id"], articles)
    return {**doc_meta, "articles": articles}


# ---------- Kiem tra bat bien: chay tren 100% node, gan nhu mien phi ----------


def validate(doc: dict, raw_text: str) -> list[str]:
    """Tra list loi. Rong = sach.

    Bat loi HE THONG tren toan bo node. Kiem tra tay chi phu ~20 node (1%),
    con day phu 100%. Can ca hai.
    """
    errs: list[str] = []
    arts = doc["articles"]

    # 1. So Dieu duy nhat -> node_id khong dung nhau -> MERGE cua P2 khong de node ma
    nums = [a["number"] for a in arts]
    if len(nums) != len(set(nums)):
        errs.append(f"Dieu trung: {sorted({n for n in nums if nums.count(n) > 1})}")

    # 2. So Dieu tang dan lien tuc tu 1
    if nums and nums != list(range(1, len(nums) + 1)):
        errs.append(f"Dieu khong lien tuc: dem {len(nums)}, max {max(nums)}")

    for a in arts:
        # 3. Khoan tang dan lien tuc -> loc duoc so tien / ngay thang bi bat nham
        ks = [k["number"] for k in a["clauses"]]
        if ks and ks != list(range(1, len(ks) + 1)):
            errs.append(f"Dieu {a['number']}: Khoan khong lien tuc {ks}")

        for k in a["clauses"]:
            # 4. Diem dung thu tu a,b,c,d,d,e,g... (bang chu cai tieng Viet)
            ps = [p["letter"] for p in k["points"]]
            if ps and ps != list(VN_LETTERS[: len(ps)]):
                errs.append(f"Dieu {a['number']} Khoan {k['number']}: Diem sai thu tu {ps}")

            # 5. Moi node phai co text
            if not k["text"]:
                errs.append(f"{k['clause_id']}: text rong")
            for p in k["points"]:
                if not p["text"]:
                    errs.append(f"{p['point_id']}: text rong")

    # 6. Do phu ky tu. BAT LOI IM LANG NGUY HIEM NHAT: parser chay khong loi,
    #    ra JSON dep, nhung nuot mat ca doan ma khong ai biet.
    got = sum(
        len(a["heading"])
        + len(a["text"])
        + sum(len(k["text"]) + sum(len(p["text"]) for p in k["points"]) for k in a["clauses"])
        for a in arts
    )
    want = len("".join(_normalize(raw_text)))
    if want and got / want < 0.80:
        errs.append(f"Do phu chi {got / want:.0%} ({got:,}/{want:,} ky tu) - dang nuot noi dung")

    return errs
