"""[P3/P4] Tiền xử lý query người dùng -> gần ngôn ngữ VĂN BẢN LUẬT trước khi retrieve.

TỔNG QUÁT (không dành riêng 1 câu): người Việt hay (a) viết tắt tên riêng dài,
(b) dùng từ đời thường mà embedding không nối được với chữ trong luật. Cùng câu hỏi
diễn đạt kiểu văn bản thì retrieval trúng ngay — nên chuẩn hoá query trước khi tìm.

Nguyên tắc: MỞ RỘNG, không thay thế — giữ cả cách nói gốc + thêm dạng văn bản, để
không làm hỏng câu vốn đã đúng. Query-side: KHÔNG cần rebuild embedding cache.

Mở rộng từ điển: chỉ cần thêm cặp vào ABBREV / EXPAND bên dưới.
Dùng bởi: backend/discourse/linker.py::_candidate_set (nên phủ cả Q&A lẫn discourse).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1) VIẾT TẮT -> ĐẦY ĐỦ  (tên riêng/cụm dài người Việt hay rút gọn)
#    Bung tại chỗ, khớp nguyên token (word boundary). Giữ cả viết tắt lẫn bản đầy đủ.
#    CHỈ đưa viết tắt RÕ NGHĨA trong ngữ cảnh thuế (bỏ cái mơ hồ như hđ, tk, cn).
# ---------------------------------------------------------------------------
ABBREV = {
    # sắc thuế
    "tncn": "thu nhập cá nhân",
    "tndn": "thu nhập doanh nghiệp",
    "gtgt": "giá trị gia tăng",
    "vat": "giá trị gia tăng",
    "ttđb": "tiêu thụ đặc biệt",
    "xnk": "xuất nhập khẩu",
    "bvmt": "bảo vệ môi trường",
    "sdđ": "sử dụng đất",
    # chủ thể / cơ quan
    "hkd": "hộ kinh doanh",
    "cnkd": "cá nhân kinh doanh",
    "nnt": "người nộp thuế",
    "dn": "doanh nghiệp",
    "htx": "hợp tác xã",
    "cqt": "cơ quan thuế",
    "cqqlt": "cơ quan quản lý thuế",
    "ubnd": "ủy ban nhân dân",
    "ubtvqh": "ủy ban thường vụ quốc hội",
    "btc": "bộ tài chính",
    # thủ tục / chứng từ
    "mst": "mã số thuế",
    "qlt": "quản lý thuế",
    "hđđt": "hóa đơn điện tử",
    "gtgc": "giảm trừ gia cảnh",
    "qttc": "quyết toán thuế",
    "kkt": "kê khai thuế",
    # tài sản / khác
    "bđs": "bất động sản",
    "ck": "chứng khoán",
    "bhxh": "bảo hiểm xã hội",
    "bhyt": "bảo hiểm y tế",
    "nsnn": "ngân sách nhà nước",
    "tmđt": "thương mại điện tử",
}

# ---------------------------------------------------------------------------
# 2) ĐỜI THƯỜNG -> KHÁI NIỆM VĂN BẢN  (bơm thêm, không xoá cách nói gốc)
#    Đây là chỗ embedding hay hụt: dân nói kiểu này, luật viết kiểu kia.
# ---------------------------------------------------------------------------
EXPAND = {
    # miễn / nộp thuế
    "miễn thuế": "không phải nộp thuế",
    "được miễn": "không phải nộp thuế",
    "khỏi đóng thuế": "không phải nộp thuế",
    "không phải đóng": "không phải nộp thuế",
    "khỏi nộp": "không phải nộp thuế",
    "đóng thuế": "nộp thuế",
    "phải đóng": "phải nộp",
    "nộp bao nhiêu": "mức thuế phải nộp",
    "chịu thuế bao nhiêu": "mức thuế phải nộp",
    "ngưỡng miễn": "mức doanh thu không phải nộp thuế",
    "ngưỡng chịu thuế": "mức doanh thu phải nộp thuế",
    # thu nhập / doanh thu / lãi
    "tiền lời": "thu nhập lợi nhuận",
    "tiền lãi": "thu nhập",
    "làm ra": "doanh thu thu nhập",
    "doanh số": "doanh thu",
    "lương": "tiền lương tiền công",
    "đi làm công": "thu nhập từ tiền lương tiền công",
    "làm thuê": "thu nhập từ tiền lương tiền công",
    # kinh doanh
    "làm ăn": "hoạt động sản xuất kinh doanh",
    "buôn bán": "kinh doanh thương mại phân phối hàng hóa",
    "bán hàng online": "kinh doanh trên nền tảng thương mại điện tử",
    "bán online": "kinh doanh trên nền tảng thương mại điện tử",
    "sàn thương mại điện tử": "nền tảng thương mại điện tử",
    "thuế khoán": "phương pháp khoán ấn định thuế",
    "bỏ khoán": "không áp dụng phương pháp khoán",
    # loại thu nhập khác
    "bán nhà": "chuyển nhượng bất động sản",
    "bán đất": "chuyển nhượng bất động sản",
    "nhà đất": "bất động sản",
    "cho thuê nhà": "cho thuê bất động sản",
    "cho thuê trọ": "cho thuê bất động sản",
    "bán cổ phiếu": "chuyển nhượng chứng khoán",
    "cổ tức": "thu nhập từ đầu tư vốn",
    "lãi ngân hàng": "thu nhập từ đầu tư vốn lãi tiền gửi",
    "trúng số": "trúng thưởng",
    "được thừa kế": "nhận thừa kế",
    "được cho tặng": "quà tặng",
    "được tặng": "quà tặng",
    # gia cảnh / phụ thuộc
    "nuôi con": "người phụ thuộc giảm trừ gia cảnh",
    "con cái": "người phụ thuộc",
    "giảm trừ": "giảm trừ gia cảnh",
    # thủ tục / vi phạm
    "khai thuế": "kê khai thuế",
    "quyết toán": "quyết toán thuế",
    "chậm nộp": "tiền chậm nộp",
    "trốn thuế": "hành vi trốn thuế vi phạm pháp luật về thuế",
    "phạt thuế": "xử phạt vi phạm hành chính về thuế",
    "đăng ký": "đăng ký thuế",
}

# 3) CHUẨN HOÁ SỐ:  400tr -> 400 triệu ;  3ty/3tỷ -> 3 tỷ ;  50k -> 50 nghìn
_NUM_TR = re.compile(r"(\d+)\s*tr(?:đ|iệu)?\b", re.IGNORECASE)
_NUM_TY = re.compile(r"(\d+)\s*t[yỷ]\b", re.IGNORECASE)
_NUM_K = re.compile(r"(\d+)\s*k\b")
_WORD = re.compile(r"[0-9a-zA-ZÀ-ỹ]+")


def _expand_abbrev(q: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0)
        full = ABBREV.get(w.lower())
        return f"{w} {full}" if full else w  # giữ cả viết tắt + bản đầy đủ
    return _WORD.sub(repl, q)


def normalize_query(q: str) -> str:
    """Query gốc -> query mở rộng gần văn bản luật (dùng cho RETRIEVAL, không hiện user)."""
    out = q
    out = _NUM_TR.sub(r"\1 triệu", out)
    out = _NUM_TY.sub(r"\1 tỷ", out)
    out = _NUM_K.sub(r"\1 nghìn", out)
    out = _expand_abbrev(out)

    low = out.lower()
    extra = [concept for phrase, concept in EXPAND.items() if phrase in low]
    if extra:
        out = f"{out} — {'; '.join(dict.fromkeys(extra))}"
    return out
