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
    """Gọi FPT embeddings, trả ma trận (n, dim) đã chuẩn hoá L2."""
    from backend.core.llm import _client

    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        chunk = texts[start:start + EMBED_BATCH]
        response = _client().embeddings.create(model=EMBED_MODEL, input=chunk)
        vectors.extend(d.embedding for d in response.data)
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-9, None)


def build_cache(force: bool = False) -> None:
    """Embed toàn corpus luật -> cache. Idempotent trừ khi force."""
    if CACHE_FILE.exists() and not force:
        return
    nodes = load_nodes()
    items = [(nid, n) for nid, n in nodes.items() if n["text"].strip()]
    node_ids = [nid for nid, _ in items]
    matrix = _embed([n["text"] for _, n in items])
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE_FILE, node_ids=np.array(node_ids), matrix=matrix)
    print(f"  embed {len(node_ids)} node -> {CACHE_FILE.name}")


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
