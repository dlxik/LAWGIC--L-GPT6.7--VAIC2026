"""[Tra cứu] Trả về NGUYÊN Điều luật gốc khi người dùng nhấn vào 1 kết quả.

Vì kết quả tra cứu chỉ là 1 Khoản/Điểm — đọc lẻ thường vô nghĩa ("Trường hợp quy
định tại điểm b khoản 2 Điều 109..."). Nhấn vào phải bung ra CẢ Điều: tiêu đề Điều
+ mọi Khoản + Điểm theo đúng thứ tự văn bản, và tô đậm mục vừa nhấn.

Suy Điều cha từ node_id (2 đoạn đầu): qlt2025-d26-k1-a -> Điều qlt2025-d26.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@lru_cache(maxsize=1)
def _all_nodes() -> dict[str, dict]:
    # load_nodes đọc file mỗi lần -> cache 1 lần cho mọi request tra cứu.
    from scripts.show_law import load_nodes  # noqa: WPS433

    return load_nodes()


def _article_prefix(node_id: str) -> str:
    parts = node_id.split("-")
    return "-".join(parts[:2])  # <doc>-d<N>


def _depth(label: str) -> int:
    return {"Article": 0, "Clause": 1, "Point": 2}.get(label, 1)


def _local_num(node_id: str, art_prefix: str) -> str:
    """Số/chữ cục bộ để hiển thị: 'k1'->'1', điểm 'a'->'a', Điều->''"""
    rem = node_id[len(art_prefix):].lstrip("-")
    if not rem:
        return ""
    last = rem.split("-")[-1]
    return last[1:] if last.startswith("k") and last[1:].isdigit() else last


@router.get("/law/article")
def law_article(node_id: str = Query(min_length=3, max_length=100)) -> dict:
    """Full Điều luật chứa node_id: tiêu đề + toàn bộ Khoản/Điểm theo thứ tự."""
    nodes = _all_nodes()
    art_prefix = _article_prefix(node_id)
    article = nodes.get(art_prefix)
    if not article:
        raise HTTPException(status_code=404, detail=f"khong tim thay Dieu cua {node_id!r}")

    # load_nodes giữ thứ tự văn bản -> lọc theo tiền tố, GIỮ nguyên thứ tự (không sort lại).
    # Dấu '-' sau tiền tố chặn nhầm d3 với d30 (d3- != d30).
    items = []
    for nid, n in nodes.items():
        if nid == art_prefix or nid.startswith(art_prefix + "-"):
            items.append({
                "node_id": nid,
                "label": n.get("label", ""),
                "depth": _depth(n.get("label", "")),
                "num": _local_num(nid, art_prefix),
                "heading": n.get("heading", ""),
                "text": n.get("text", ""),
                "effective_from": n.get("effective_from"),
                "effective_to": _clean(n.get("effective_to")),
                "is_target": nid == node_id,
            })

    return {
        "article": {
            "node_id": art_prefix,
            "display": article.get("display", ""),
            "heading": article.get("heading", ""),
            "doc_number": article.get("doc_number", ""),
            "doc_id": article.get("doc_id", ""),
            "effective_from": article.get("effective_from"),
            "effective_to": _clean(article.get("effective_to")),
        },
        "target": node_id,
        "items": items,
    }


def _clean(v):
    # load_nodes để 'None' dạng chuỗi cho effective_to rỗng -> chuẩn hoá về null.
    return None if v in (None, "None", "") else v
