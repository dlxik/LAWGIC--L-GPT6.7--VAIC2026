"""[P3] Lien ket claim <-> Dieu/Khoan/Diem. Hybrid, KHONG phai vector RAG thuan.

  1. BM25/vector lay top-K Diem ung vien
  2. Mo rong theo graph: Diem -> Khoan cha -> van ban lien quan -> SUPERSEDED_BY
  3. LLM chon Diem dung nhat + confidence

Buoc 2 la ly do dung graph database. Ghi ro vao slide.
Output: list[Citation]
"""


def link_claim(claim_text: str, topic: str) -> list[dict]:
    raise NotImplementedError
