"""[P3] Tra văn bản luật từ data/processed/*.json.

Cần khi gắn nhãn gold set: điền `expected_citation` phải là node_id CÓ THẬT.
1.821 node trong 3 văn bản — không dò tay được.

Chạy:
    python scripts/show_law.py tncn2025-d7          # in cả cây Điều 7
    python scripts/show_law.py tncn2025-d7-k1       # in đúng 1 khoản
    python scripts/show_law.py --grep "500 triệu"   # tìm node theo nội dung
    python scripts/show_law.py --toc tncn2025       # mục lục các điều
    python scripts/show_law.py --check tncn2025-d7-k9   # node này có thật không?

`load_nodes()` được linker.py dùng lại làm nguồn ứng viên khi graph của Linh
chưa chạy — cùng một nguồn sự thật, không có bản sao thứ hai.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Đường dẫn theo config của P4 (P1 đổi chỗ lưu sang legal_docs_structured/ ở giờ 16).
# Đọc từ config để nếu P1 dời tiếp thì không phải sửa nhiều chỗ.
try:
    from backend.core.config import get_settings
    LAW_DIR = get_settings().structured_legal_dir
except Exception:
    LAW_DIR = ROOT / "data" / "processed" / "legal_docs_structured"
DOC_IDS = ("qlt2019", "qlt2025", "tncn2025")


def load_docs(doc_ids=DOC_IDS) -> dict[str, dict]:
    docs = {}
    for doc_id in doc_ids:
        path = LAW_DIR / f"{doc_id}.json"
        if path.exists():
            docs[doc_id] = json.loads(path.read_text(encoding="utf-8"))
    if not docs:
        sys.exit(f"Không thấy văn bản nào trong {LAW_DIR}")
    return docs


def load_nodes(doc_ids=DOC_IDS) -> dict[str, dict]:
    """Phẳng hoá 3 văn bản -> {node_id: {...}}.

    Mỗi node giữ `label` (Article|Clause|Point), `text`, `doc_id`, `display`
    (chuỗi trích dẫn cho người đọc) và `effective_from` — hiệu lực nằm ở MỨC
    NODE (schemas.py::Temporal), không phải mức văn bản.
    """
    nodes: dict[str, dict] = {}
    for doc_id, doc in load_docs(doc_ids).items():
        doc_number = doc.get("doc_number", doc_id)
        for article in doc.get("articles", []):
            _add(nodes, article, "Article", doc_id, doc_number,
                 f"Điều {article['number']} {doc_number}", article.get("heading", ""))
            for clause in article.get("clauses", []):
                _add(nodes, clause, "Clause", doc_id, doc_number,
                     f"Điều {article['number']} Khoản {clause['number']} {doc_number}")
                for point in clause.get("points", []):
                    _add(nodes, point, "Point", doc_id, doc_number,
                         f"Điều {article['number']} Khoản {clause['number']}"
                         f" Điểm {point['letter']} {doc_number}")
    return nodes


def _add(nodes, node, label, doc_id, doc_number, display, heading=""):
    node_id = node.get(f"{label.lower()}_id")
    if not node_id:
        return
    nodes[node_id] = {
        "node_id": node_id,
        "label": label,
        "doc_id": doc_id,
        "doc_number": doc_number,
        "display": display,
        "heading": heading,
        "text": node.get("text", ""),
        "effective_from": node.get("effective_from"),
        "effective_to": node.get("effective_to"),
    }


def _wrap(text: str, indent: str, width: int = 84) -> str:
    return textwrap.fill(text, width=width, initial_indent=indent,
                         subsequent_indent=indent) if text else ""


def cmd_show(nodes: dict[str, dict], node_id: str) -> None:
    """In node + toàn bộ node con của nó."""
    node = nodes.get(node_id)
    if not node:
        near = [n for n in nodes if n.startswith(node_id)][:5]
        hint = f"\nGần giống: {', '.join(near)}" if near else ""
        sys.exit(f"Không có node {node_id!r}{hint}")

    children = sorted(
        n for n in nodes
        if n.startswith(node_id + "-") and n.count("-") <= node_id.count("-") + 1
    )
    for nid in [node_id] + children:
        cur = nodes[nid]
        eff = cur["effective_from"] or "?"
        to = cur["effective_to"] or "nay"
        depth = cur["label"]
        indent = {"Article": "", "Clause": "  ", "Point": "     "}[depth]
        print(f"{indent}[{nid}]  {cur['display']}  ({eff} → {to})")
        if cur["heading"]:
            print(f"{indent}  « {cur['heading']} »")
        if cur["text"]:
            print(_wrap(cur["text"], indent + "  "))
        print()


def cmd_grep(nodes: dict[str, dict], needle: str, limit: int) -> None:
    needle_low = needle.lower()
    hits = [n for n in nodes.values() if needle_low in n["text"].lower()]
    print(f"  {len(hits)} node khớp {needle!r}:\n")
    for node in hits[:limit]:
        print(f"  [{node['node_id']}]  {node['display']}")
        print(_wrap(node["text"][:220], "      "))
        print()


def cmd_toc(nodes: dict[str, dict], doc_id: str) -> None:
    articles = [n for n in nodes.values() if n["label"] == "Article" and n["doc_id"] == doc_id]
    if not articles:
        sys.exit(f"Không có văn bản {doc_id!r}. Có: {', '.join(DOC_IDS)}")
    print(f"  {articles[0]['doc_number']} — {len(articles)} điều\n")
    for node in articles:
        print(f"  {node['node_id']:>16}  {node['heading'][:66]}")


def cmd_check(nodes: dict[str, dict], node_id: str) -> None:
    """node_id có thật không. Dùng khi soát expected_citation của gold set."""
    if node_id in nodes:
        print(f"  ✓ {node_id}  =  {nodes[node_id]['display']}")
    else:
        print(f"  ✗ {node_id}  KHÔNG TỒN TẠI")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tra văn bản luật")
    parser.add_argument("node_id", nargs="?", help="vd tncn2025-d7 hoặc tncn2025-d7-k1")
    parser.add_argument("--grep", metavar="TEXT", help="tìm node theo nội dung")
    parser.add_argument("--toc", metavar="DOC_ID", help="mục lục (qlt2019|qlt2025|tncn2025)")
    parser.add_argument("--check", metavar="NODE_ID", help="node_id có thật không")
    parser.add_argument("-n", type=int, default=15, help="số kết quả tối đa")
    args = parser.parse_args()

    nodes = load_nodes()

    if args.grep:
        cmd_grep(nodes, args.grep, args.n)
    elif args.toc:
        cmd_toc(nodes, args.toc)
    elif args.check:
        cmd_check(nodes, args.check)
    elif args.node_id:
        cmd_show(nodes, args.node_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
