"""[P1] Kết hợp 2 model nhiều kiểu -> đo P/R/F1, xem cách nào giữ recall.

Vấn đề: giao thẳng A∩B cắt hallucination nhưng TỤT RECALL (span chỉ 1 model
thấy bị bỏ). Script đo 5 cấu hình để tìm cách chất-hơn-mà-giữ-recall:

  A đơn / B đơn          — mốc
  A∩B  (giao / voting)   — precision cao nhất, recall thấp nhất
  A∪B  (hợp)             — recall cao nhất, precision thấp
  A∪B + lọc verbatim  ⭐ — hợp rồi BỎ span không có trong text gốc.
                           Chỉ cắt bịa "chữ không có thật", KHÔNG đụng span đúng
                           -> precision tăng, RECALL GIỮ NGUYÊN. Miễn phí (0 gọi LLM).

Lọc verbatim KHÔNG bắt được bịa kiểu "sai vai" (span có thật nhưng gán nhầm
chủ thể/nghĩa vụ) -> đó là việc của voting. Hai cách bù nhau.

Chạy:  python eval/vote_combine.py <modelA> <modelB>
       (cần chạy eval/bench_raw.py cho từng model trước)
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.benchmark_p1 import (  # noqa: E402
    ENTITY_FIELDS, MATCH_THRESHOLD, _match_sets, _norm, _prf, _similar,
)

A_NAME, B_NAME = sys.argv[1], sys.argv[2]


def _load(name: str) -> dict:
    safe = name.replace("/", "_")
    return json.loads((ROOT / f"eval/results/rawpred_{safe}.json").read_text(encoding="utf-8"))


def _node_texts() -> dict:
    txt = {}
    for f in glob.glob(str(ROOT / "data/processed/qlt*.json")) + glob.glob(str(ROOT / "data/processed/tncn*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for a in d["articles"]:
            txt[a["article_id"]] = a["text"]
            for k in a["clauses"]:
                txt[k["clause_id"]] = k["text"]
                for p in k["points"]:
                    txt[p["point_id"]] = p["text"]
    return txt


def _grounded(span: str, text: str) -> bool:
    """Span có 'thật sự nằm trong text gốc' không? (kiểm verbatim, không LLM).

    Đúng khi span chuẩn hoá là chuỗi con của text, HOẶC >=70% từ của span có
    trong text. Bắt bịa kiểu 'chữ không có thật'; span verbatim/cắt nhẹ vẫn qua.
    """
    ns, nt = _norm(span), _norm(text)
    if not ns:
        return False
    if ns in nt:
        return True
    words = ns.split()
    if not words:
        return False
    hit = sum(1 for w in words if w in nt)
    return hit / len(words) >= 0.70


def _union(a_list: list[str], b_list: list[str]) -> list[str]:
    """Gộp, bỏ trùng (span của B trùng span A thì không thêm lại)."""
    out = list(a_list)
    for b in b_list:
        if not any(_similar(b, a) >= MATCH_THRESHOLD for a in out):
            out.append(b)
    return out


def _vote(a_list: list[str], b_list: list[str]) -> list[str]:
    """Giữ span của A mà B đồng ý (có span khớp)."""
    return [a for a in a_list if any(_similar(a, b) >= MATCH_THRESHOLD for b in b_list)]


def _vote_penalties(a_pen: list[dict], b_pen: list[dict]) -> list[dict]:
    out = []
    for a in a_pen:
        for b in b_pen:
            if _similar(a.get("text", ""), b.get("text", "")) >= MATCH_THRESHOLD:
                out.append(a)
                break
    return out


def _score(gold: dict, getpred) -> dict:
    agg = {f: {"tp": 0, "fp": 0, "fn": 0} for f in ENTITY_FIELDS}
    pen_tot = pen_ok = 0
    for nid, g in gold.items():
        p = getpred(nid)
        for field in ENTITY_FIELDS:
            tp, fp, fn = _match_sets(g.get(field, []), p.get(field, []))
            agg[field]["tp"] += tp
            agg[field]["fp"] += fp
            agg[field]["fn"] += fn
        for gp in g.get("penalties", []):
            pen_tot += 1
            for pp in p.get("penalties", []):
                if _similar(gp.get("text", ""), pp.get("text", "")) >= MATCH_THRESHOLD:
                    pen_ok += int(gp.get("type") == pp.get("type"))
                    break
    fields = {f: _prf(**agg[f]) for f in ENTITY_FIELDS}
    micro = _prf(sum(agg[f]["tp"] for f in ENTITY_FIELDS),
                 sum(agg[f]["fp"] for f in ENTITY_FIELDS),
                 sum(agg[f]["fn"] for f in ENTITY_FIELDS))
    tot = micro["tp"] + micro["fp"]
    return {
        "fields": fields, "micro": micro,
        "hall": round(micro["fp"] / tot, 4) if tot else 0.0,
        "pen_acc": round(pen_ok / pen_tot, 4) if pen_tot else None,
    }


def main() -> None:
    gold = {}
    for line in (ROOT / "eval/gold_entities.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(line)
        if "node_id" in o:
            gold[o["node_id"]] = o

    A, B = _load(A_NAME), _load(B_NAME)
    txt = _node_texts()

    def intersect(nid):
        a, b = A.get(nid, {}), B.get(nid, {})
        out = {f: _vote(a.get(f, []), b.get(f, [])) for f in ENTITY_FIELDS}
        out["penalties"] = _vote_penalties(a.get("penalties", []), b.get("penalties", []))
        return out

    def union(nid):
        a, b = A.get(nid, {}), B.get(nid, {})
        out = {f: _union(a.get(f, []), b.get(f, [])) for f in ENTITY_FIELDS}
        out["penalties"] = a.get("penalties", []) + [
            bp for bp in b.get("penalties", [])
            if not any(_similar(bp.get("text", ""), ap.get("text", "")) >= MATCH_THRESHOLD
                       for ap in a.get("penalties", []))]
        return out

    def union_grounded(nid):
        t = txt.get(nid, "")
        u = union(nid)
        out = {f: [s for s in u[f] if _grounded(s, t)] for f in ENTITY_FIELDS}
        out["penalties"] = [p for p in u["penalties"] if _grounded(p.get("text", ""), t)]
        return out

    def hybrid(nid):
        """Giao 9 trường thực thể (precision cao) NHƯNG giữ penalty của A.
        Vì giao giết penalty-type (B=0%) mà A mạnh penalty-type."""
        out = intersect(nid)
        out["penalties"] = A.get(nid, {}).get("penalties", [])
        return out

    configs = [
        (f"A: {A_NAME}", lambda nid: A.get(nid, {})),
        (f"B: {B_NAME}", lambda nid: B.get(nid, {})),
        ("A∩B  (giao/voting)", intersect),
        ("A∪B  (hợp)", union),
        ("A∪B + lọc verbatim", union_grounded),
        ("A∩B ent + A pen ⭐", hybrid),
    ]
    results = [(name, _score(gold, fn)) for name, fn in configs]

    def row(name, r):
        m = r["micro"]
        pen = f"{r['pen_acc']:.0%}" if r["pen_acc"] is not None else "  -"
        print(f"  {name:24s} {m['f1']:>4.0%} {m['precision']:>4.0%} {m['recall']:>4.0%} "
              f"{r['hall']:>5.0%}   {pen}")

    print(f"\n  {'cấu hình':24s} {'F1':>4s} {'P':>4s} {'R':>4s} {'Hall':>5s}  PenT")
    print(f"  {'-' * 52}")
    for name, r in results:
        row(name, r)

    rA = results[0][1]
    print("\n  So với A đơn (mục tiêu: chất hơn mà GIỮ recall):")
    for name, r in results[2:]:
        print(f"    {name:24s} F1 {(r['micro']['f1']-rA['micro']['f1'])*100:+.0f}  "
              f"P {(r['micro']['precision']-rA['micro']['precision'])*100:+.0f}  "
              f"Hall {(r['hall']-rA['hall'])*100:+.0f}  "
              f"R {(r['micro']['recall']-rA['micro']['recall'])*100:+.0f}")

    print("\n  Theo trường (F1):")
    hdr = "  {:14s}".format("trường") + "".join(f"{n.split(':')[0][:8]:>9s}" for n, _ in results)
    print(hdr)
    for f in ENTITY_FIELDS:
        print("  {:14s}".format(f) + "".join(f"{r['fields'][f]['f1']:>8.0%} " for _, r in results))

    (ROOT / "eval/results/vote_result.json").write_text(
        json.dumps({"A": A_NAME, "B": B_NAME,
                    "configs": {name: r for name, r in results}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n  -> eval/results/vote_result.json")


if __name__ == "__main__":
    main()
