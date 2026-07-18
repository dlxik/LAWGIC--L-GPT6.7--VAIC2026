"""[P3] Retrieval ngữ nghĩa bằng FPT Vietnamese_Embedding.

Thay TF-IDF (từ vựng) cho bước 1 của linker. Lý do: claim nói con số này (200tr)
mà căn cứ đúng là ngưỡng khác (500tr) — cùng nghĩa, khác chữ. TF-IDF cho similarity
~0, embedding cho ~0.62. Đây là thứ nâng recall từ 63% lên.

Corpus 1.821 node được embed MỘT LẦN rồi cache xuống đĩa (data/processed/
law_embeddings.npz). Chạy lại không gọi lại API. Đổi model/đổi luật -> xoá cache.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from backend.core import config

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.show_law import load_nodes  # noqa: E402

EMBED_MODEL = "Vietnamese_Embedding"
CACHE_FILE = config.get_settings().structured_legal_dir.parent / "law_embeddings.npz"
EMBED_BATCH = 50  # số node embed mỗi request


def _embed(texts: list[str]) -> np.ndarray:
    """Gọi FPT embeddings, trả ma trận (n, dim) đã chuẩn hoá L2.

    Đi qua llm.embed (có retry 429/5xx/mạng). KHÔNG gọi _client().embeddings.create
    thẳng: _client đặt max_retries=0 nên gọi thẳng là mất hết retry -> build_cache
    1.821 node đứt giữa chừng khi FPT rate-limit.
    """
    from backend.core import llm

    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        chunk = texts[start:start + EMBED_BATCH]
        vectors.extend(llm.embed(chunk, model=EMBED_MODEL))
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-9, None)


def _context_text(nid: str, nodes: dict) -> str:
    """Text GIÀU NGỮ CẢNH để embed: tiêu đề Điều + text Khoản cha + text Điểm.

    Thay vì chỉ embed text của Điểm (thiếu ngữ cảnh -> câu 'thuế suất dưới 3 tỷ'
    không khớp được vì không biết nó thuộc Điều 7). Ghép ngữ cảnh cha vào giúp
    embedding hiểu Điểm nằm trong bối cảnh nào -> retrieval chính xác hơn.

    Suy cha từ node_id: tncn2025-d7-k2-a -> Điều tncn2025-d7, Khoản tncn2025-d7-k2.
    """
    parts = nid.split("-")
    ctx: list[str] = []
    article = nodes.get("-".join(parts[:2]))  # Điều
    if article and article.get("heading"):
        ctx.append(article["heading"])
    if len(parts) >= 4:  # là Điểm -> thêm text Khoản cha
        clause = nodes.get("-".join(parts[:3]))
        if clause and clause.get("text"):
            ctx.append(clause["text"])
    own = nodes[nid].get("text", "")
    ctx.append(own)

    # Bơm KHÁI NIỆM đồng nghĩa: luật viết "không phải nộp thuế" nhưng dân hỏi "miễn
    # thuế / ngưỡng miễn" -> embedding không nối được. Thêm cụm khái niệm để khớp.
    low = own.lower()
    if "không phải nộp" in low or "được miễn" in low or ("miễn" in low and "thuế" in low):
        ctx.append("ngưỡng miễn thuế; được miễn thuế; không phải nộp thuế")
    if "trở xuống" in low or "vượt trên" in low or "vượt quá" in low:
        ctx.append("ngưỡng doanh thu chịu thuế")

    # dedupe giữ thứ tự (node là Điều thì heading + text điều có thể trùng ý)
    return " — ".join(dict.fromkeys(t for t in ctx if t))


def build_cache(force: bool = False) -> None:
    """Embed toàn corpus luật -> cache. Idempotent trừ khi force.

    Embed text GIÀU NGỮ CẢNH (xem _context_text): đổi cách embed -> PHẢI force
    rebuild, không gian vector cũ không dùng lại được.
    """
    if CACHE_FILE.exists() and not force:
        return
    nodes = load_nodes()
    items = [(nid, n) for nid, n in nodes.items() if n["text"].strip()]
    node_ids = [nid for nid, _ in items]
    matrix = _embed([_context_text(nid, nodes) for nid in node_ids])
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE_FILE, node_ids=np.array(node_ids), matrix=matrix)
    print(f"  embed {len(node_ids)} node (giàu ngữ cảnh) -> {CACHE_FILE.name}")


def _load_cache() -> tuple[list[str], np.ndarray]:
    if not CACHE_FILE.exists():
        build_cache()
    data = np.load(CACHE_FILE, allow_pickle=True)
    return list(data["node_ids"]), data["matrix"]


def retrieve(claim_text: str, k: int) -> list[str]:
    """Top-k node_id gần nhất theo cosine embedding."""
    node_ids, matrix = _load_cache()
    query = _embed([claim_text])[0]
    scores = matrix @ query
    ranked = np.argsort(scores)[::-1][:k]
    return [node_ids[i] for i in ranked]
