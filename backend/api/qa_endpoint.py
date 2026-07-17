"""[P4] POST /qa  {question, as_of_date?} -> QAResponse

MOI cau tra loi PHAI kem citation Dieu-Khoan-Diem.
Khong tim duoc dieu luat -> tra loi "khong du can cu", KHONG doan.
"""


def answer(question: str, as_of_date: str | None = None) -> dict:
    raise NotImplementedError
