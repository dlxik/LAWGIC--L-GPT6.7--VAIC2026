"""[P2] Semantic diff giữa văn bản mới và văn bản cũ.

Ghép Điểm cũ <-> Điểm mới, phân loại thay đổi, tạo SUPERSEDED_BY.
change_type: UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED

BA BƯỚC
  1. Ghép cặp: khớp cấu trúc (Điều/Khoản/Điểm cùng vị trí) trước, rồi độ tương
     đồng text cho Điểm bị đánh số lại.
  2. Phân loại: so số (tiền phạt, số tháng, vĩnh viễn) -> TIGHTENED/LOOSENED.
     Deterministic, không cần LLM, chạy được ngay và test được.
  3. Ghi: đóng effective_to của Điểm cũ + tạo SUPERSEDED_BY.

VÌ SAO KHÔNG DÙNG LLM Ở BƯỚC 2
  So text thuần không biết "18-20 triệu" so với "6-8 triệu" là siết hay nới —
  nhưng regex rút số thì biết. Deterministic nghĩa là test được bằng fixture,
  không tốn tiền API, và không phụ thuộc core/llm.py (P4 chưa xong).
  refine_with_llm() để dành cho chỗ regex bó tay — gắn vào sau, không chặn.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from backend.graph import connection

# Ngưỡng ghép cặp theo text khi khớp cấu trúc thất bại (bắt Điểm bị đánh số lại).
#
# 0.75 lấy từ số đo trên qlt2019 -> qlt2025, không phải đoán.
#
# Với mỗi Điểm cũ chưa ghép, lấy bạn giống nhất trong 297 Điểm mới. Phân bố:
#     0.3-0.4:  77
#     0.4-0.5: 195   <- đỉnh = SÀN NHIỄU. Hai Điểm luật thuế bất kỳ đều giống
#                       nhau ~0.45 vì cùng khuôn mẫu hành chính.
#     0.5-0.6:  87   <- nhiều khả năng là max-của-nhiễu: lấy max trên 297 ứng
#                       viên thì nhiễu bị thổi lên. KHÔNG tin vùng này.
#     0.6-0.7:  27
#     0.7-0.8:  11   <- kiểm tay: đều là cặp thật
#     0.8-0.9:   5   <- kiểm tay: đều là cặp thật
#
# Vì sao cặp thật lại tụt xuống 0.75-0.85: luật mới đổi thuật ngữ hệ thống
# ("Người khai thuế" -> "Người nộp thuế"), kéo similarity xuống 0.05-0.15 trên
# toàn văn bản dù nội dung không đổi.
#
# Vùng xám 0.5-0.75 (khoảng 130 Điểm) là chỗ regex bó tay — để refine_with_llm()
# xử lý nếu có thời gian. Trước mắt báo REMOVED + ADDED, thật thà hơn ghép bừa.
SIMILARITY_PAIR_THRESHOLD = 0.75

# Ngưỡng ghép ĐIỀU theo heading. Cao vì heading ngắn, khớp là khớp rõ.
# Đo được: 29/152 Điều đạt >= 0.8, trong đó 18 cặp bằng 1.00 (heading y hệt).
ARTICLE_HEADING_THRESHOLD = 0.8
# Trên ngưỡng này coi như chỉ đổi chữ, không đổi nghĩa
SIMILARITY_UNCHANGED_THRESHOLD = 0.995

# Ngưỡng cho cặp khớp CẤU TRÚC (cùng Điều/Khoản/Điểm).
#
# LỖI ĐÃ XẢY RA — phiên bản đầu tin vị trí vô điều kiện: cùng (Điều, Khoản, Điểm)
# là ghép ngay, không kiểm text. Chạy trên fixture mock thì không sao vì hai văn
# bản cùng đánh số. Chạy trên dữ liệu thật thì 40/73 cặp là rác, cặp tệ nhất
# sim=0.01 ("giấy chứng nhận đăng ký kinh doanh" ghép với "chế độ ưu tiên người
# nộp thuế") — chỉ vì cùng nằm ở Điều 34 Khoản 1 Điểm c.
#
# Nguyên nhân: qlt2025 thay thế TOÀN BỘ qlt2019 và đánh số lại từ đầu (152 Điều
# -> 53 Điều). "Điều 5 Khoản 2 Điểm a" của hai bản là hai quy định khác hẳn nhau.
# Vị trí trùng là TRÙNG HỢP, không phải bằng chứng.
#
# Ngưỡng 0.5 lấy từ số đo thật, không phải đoán. Similarity của cặp khớp cấu trúc
# phân bố lưỡng cực rõ rệt, khoảng 0.4-0.8 hoàn toàn trống:
#     0.0-0.4  40 cặp  <- rác do trùng vị trí
#     0.4-0.8   0 cặp  <- khoảng trống
#     0.8-1.0  33 cặp  <- cặp thật
# 0.5 nằm giữa khoảng trống nên tách sạch mà vẫn rộng tay với Điểm bị viết lại
# nhiều nhưng vẫn cùng nội dung.
STRUCTURAL_MIN_SIMILARITY = 0.5


# ---------------------------------------------------------------------------
# Rút số từ text điều luật
# ---------------------------------------------------------------------------

_RE_MONEY = re.compile(r"([\d.,]+)\s*(?:đồng|VNĐ|VND)", re.I)
_RE_MONTHS = re.compile(r"(\d+)\s*tháng", re.I)
_RE_PERMANENT = re.compile(r"vĩnh\s*viễn|không\s*thời\s*hạn", re.I)


def _parse_money(text: str) -> list[int]:
    """"6.000.000 đồng đến 8.000.000 đồng" -> [6000000, 8000000]"""
    out = []
    for raw in _RE_MONEY.findall(text):
        digits = raw.replace(".", "").replace(",", "")
        if digits.isdigit():
            out.append(int(digits))
    return sorted(out)


def _parse_months(text: str) -> list[int]:
    return sorted(int(m) for m in _RE_MONTHS.findall(text))


def _severity(text: str) -> dict[str, Any]:
    """Rút mức độ nghiêm khắc của một Điểm để so cũ/mới."""
    return {
        "money": _parse_money(text),
        "months": _parse_months(text),
        "permanent": bool(_RE_PERMANENT.search(text)),
    }


# ---------------------------------------------------------------------------
# Bước 1 — ghép cặp
# ---------------------------------------------------------------------------

# Lấy NODE LÁ, không phải chỉ Point — cùng quy tắc "node sâu nhất giữ sự thật"
# như Q2. Bản đầu chỉ lấy Point nên diffing bỏ qua 775/988 Khoản không có Điểm
# (luật Việt Nam thật thì text của Khoản chính là quy định), làm con số REMOVED
# bị thổi phồng và mất hẳn phần diff của hơn nửa văn bản.
#
# CASE chọn tầng sâu nhất có mặt: có Điểm -> Điểm; không -> Khoản; không -> Điều.
_FETCH_LEAVES = """
MATCH (d:LegalDocument {doc_id: $doc_id})-[:HAS_ARTICLE]->(a:Article)
OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(k:Clause)
OPTIONAL MATCH (k)-[:HAS_POINT]->(p:Point)
WITH a, k, p,
     CASE WHEN p IS NOT NULL THEN p
          WHEN k IS NOT NULL THEN k
          ELSE a END AS n
WHERE NOT (n)-[:HAS_CLAUSE|HAS_POINT]->()
RETURN DISTINCT
       coalesce(n.point_id, n.clause_id, n.article_id) AS node_id,
       labels(n)[0] AS level,
       n.text AS text,
       a.number AS article,
       k.number AS clause,
       coalesce(p.letter, '') AS letter
ORDER BY article, clause, letter
"""

_FETCH_ARTICLES = """
MATCH (d:LegalDocument {doc_id: $doc_id})-[:HAS_ARTICLE]->(a:Article)
RETURN a.number AS number, a.heading AS heading
ORDER BY a.number
"""


def _fetch_leaves(doc_id: str) -> list[dict]:
    """Mọi node lá của văn bản: Điểm, hoặc Khoản-không-Điểm, hoặc Điều-không-Khoản."""
    return connection.run(_FETCH_LEAVES, doc_id=doc_id)


# Tên cũ, giữ cho code/test đang gọi. Giờ trả về node lá chứ không chỉ Point.
_fetch_points = _fetch_leaves


def _fetch_articles(doc_id: str) -> list[dict]:
    return connection.run(_FETCH_ARTICLES, doc_id=doc_id)


def pair_articles(old_doc_id: str, new_doc_id: str) -> dict[int, int]:
    """Ghép Điều cũ -> Điều mới theo HEADING. Trả {số Điều cũ: số Điều mới}.

    Vì sao heading chứ không phải nội dung: đo trên qlt2019 -> qlt2025,
        theo heading      29/152 Điều khớp >= 0.8  (18 cặp sim = 1.00)
        theo nội dung      7/152 Điều khớp >= 0.6  -> vô dụng
    Luật mới gom và viết lại nội dung, nhưng TÊN Điều thì giữ:
        "Ấn định thuế đối với hàng hóa xuất khẩu, nhập khẩu"  D52 -> D25
        "Hóa đơn điện tử"                                     D89 -> D26

    Đây là bước bắt buộc trước khi ghép Điểm. Ghép Điểm toàn cục là ghép 442 với
    332 giữa biển nhiễu; ghép trong phạm vi một cặp Điều đã khớp thì vị trí Điểm
    lại thành bằng chứng mạnh, vì đã đúng ngữ cảnh.
    """
    old = _fetch_articles(old_doc_id)
    new = _fetch_articles(new_doc_id)

    candidates = sorted(
        (
            (_similarity(o["heading"] or "", n["heading"] or ""), o, n)
            for o in old
            for n in new
            if o["heading"] and n["heading"]
        ),
        key=lambda t: t[0],
        reverse=True,
    )

    mapping: dict[int, int] = {}
    used_new: set[int] = set()
    for score, o, n in candidates:
        if score < ARTICLE_HEADING_THRESHOLD:
            break
        if o["number"] in mapping or n["number"] in used_new:
            continue
        mapping[o["number"]] = n["number"]
        used_new.add(n["number"])
    return mapping


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _pair_points(
    old_points: list[dict],
    new_points: list[dict],
    article_map: dict[int, int] | None = None,
) -> list[tuple[dict | None, dict | None]]:
    """Ghép Điểm cũ <-> Điểm mới. Ba vòng, vòng nào cũng ĐÒI TEXT XÁC NHẬN.

      1. Khớp vị trí TRONG cặp Điều đã ghép. `article_map` dịch số Điều cũ sang
         số Điều mới trước khi so vị trí, nên "Điều 52 Khoản 1 Điểm c" của bản cũ
         được so với "Điều 25 Khoản 1 Điểm c" của bản mới. Vẫn phải qua ngưỡng
         STRUCTURAL_MIN_SIMILARITY — vị trí là gợi ý, không phải bằng chứng.
      2. Ghép theo text cho phần còn lại, toàn cục — bắt Điểm chuyển sang Điều
         không ghép được bằng heading.
      3. Còn dư -> REMOVED / ADDED. Không đoán bừa.

    Không truyền article_map thì lùi về so vị trí thô (dùng cho văn bản sửa đổi
    một phần, nơi hai bản giữ nguyên cách đánh số).
    """
    article_map = article_map or {}
    pairs: list[tuple[dict | None, dict | None]] = []

    def old_key(p: dict) -> tuple:
        # Điều cũ này tương ứng Điều nào bên bản mới? Không ghép được thì giữ
        # nguyên số (văn bản sửa đổi một phần vẫn dùng chung cách đánh số).
        return (article_map.get(p["article"], p["article"]), p["clause"], p["letter"])

    def new_key(p: dict) -> tuple:
        return (p["article"], p["clause"], p["letter"])

    new_by_key = {new_key(p): p for p in new_points}
    used_new: set[str] = set()

    unmatched_old: list[dict] = []
    for old in old_points:
        match = new_by_key.get(old_key(old))
        # Trùng vị trí là chưa đủ — text phải xác nhận đây là cùng một quy định
        if (
            match
            and match["node_id"] not in used_new
            and _similarity(old["text"], match["text"]) >= STRUCTURAL_MIN_SIMILARITY
        ):
            pairs.append((old, match))
            used_new.add(match["node_id"])
        else:
            unmatched_old.append(old)

    leftover_new = [p for p in new_points if p["node_id"] not in used_new]

    # Ghép phần còn lại theo text — chọn cặp giống nhau nhất trước.
    # Chỉ ghép node CÙNG TẦNG: một Điểm không thể là bản mới của cả một Khoản.
    candidates = sorted(
        (
            (_similarity(o["text"], n["text"]), o, n)
            for o in unmatched_old
            for n in leftover_new
            if o.get("level") == n.get("level")
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    paired_old: set[str] = set()
    paired_new: set[str] = set()
    for score, o, n in candidates:
        if score < SIMILARITY_PAIR_THRESHOLD:
            break
        if o["node_id"] in paired_old or n["node_id"] in paired_new:
            continue
        pairs.append((o, n))
        paired_old.add(o["node_id"])
        paired_new.add(n["node_id"])

    # Còn dư: cũ -> REMOVED, mới -> ADDED
    pairs += [(o, None) for o in unmatched_old if o["node_id"] not in paired_old]
    pairs += [(None, n) for n in leftover_new if n["node_id"] not in paired_new]
    return pairs


# ---------------------------------------------------------------------------
# Bước 2 — phân loại
# ---------------------------------------------------------------------------


def _classify(old: dict | None, new: dict | None) -> tuple[str, float, str]:
    """Trả (change_type, similarity, summary)."""
    if old is None:
        return "ADDED", 0.0, "Điểm mới, không có bản cũ tương ứng"
    if new is None:
        return "REMOVED", 0.0, "Bản mới bỏ hẳn điểm này"

    sim = _similarity(old["text"], new["text"])
    if sim >= SIMILARITY_UNCHANGED_THRESHOLD:
        return "UNCHANGED", sim, "Giữ nguyên"

    so, sn = _severity(old["text"]), _severity(new["text"])
    reasons: list[str] = []
    direction = 0  # +1 siết, -1 nới

    if so["money"] and sn["money"]:
        if sn["money"][-1] > so["money"][-1]:
            direction += 1
            reasons.append(
                f"phạt tiền tăng {so['money'][0]:,}-{so['money'][-1]:,} "
                f"-> {sn['money'][0]:,}-{sn['money'][-1]:,}"
            )
        elif sn["money"][-1] < so["money"][-1]:
            direction -= 1
            reasons.append(
                f"phạt tiền giảm {so['money'][-1]:,} -> {sn['money'][-1]:,}"
            )

    if sn["permanent"] and not so["permanent"]:
        direction += 1
        reasons.append("chuyển sang vĩnh viễn")
    elif so["permanent"] and not sn["permanent"]:
        direction -= 1
        reasons.append("bỏ vĩnh viễn")
    elif so["months"] and sn["months"]:
        if sn["months"][-1] > so["months"][-1]:
            direction += 1
            reasons.append(f"thời hạn tăng {so['months'][-1]} -> {sn['months'][-1]} tháng")
        elif sn["months"][-1] < so["months"][-1]:
            direction -= 1
            reasons.append(f"thời hạn giảm {so['months'][-1]} -> {sn['months'][-1]} tháng")
        else:
            reasons.append(f"thời hạn giữ nguyên {sn['months'][-1]} tháng")

    if direction > 0:
        return "TIGHTENED", sim, "; ".join(reasons)
    if direction < 0:
        return "LOOSENED", sim, "; ".join(reasons)
    return "REWORDED", sim, "; ".join(reasons) or "Đổi câu chữ, mức xử phạt không đổi"


# ---------------------------------------------------------------------------
# Bước 3 — ghi vào graph
# ---------------------------------------------------------------------------

# Khớp cả 3 tầng: node lá có thể là Point, Clause (không Điểm) hoặc Article
# (không Khoản). Bản đầu chỉ MATCH (:Point) nên bỏ qua hơn nửa văn bản.
_MERGE_SUPERSEDED = """
MATCH (old) WHERE old.point_id = $old_id OR old.clause_id = $old_id
                  OR old.article_id = $old_id
MATCH (new) WHERE new.point_id = $new_id OR new.clause_id = $new_id
                  OR new.article_id = $new_id
MERGE (old)-[r:SUPERSEDED_BY]->(new)
SET r.change_type = $change_type,
    r.similarity = $similarity,
    r.effective_from = date($effective_from)
"""

_CLOSE_OLD_NODE = """
MATCH (n) WHERE n.point_id = $node_id OR n.clause_id = $node_id
              OR n.article_id = $node_id
SET n.effective_to = date($effective_to)
"""


def diff_documents(
    old_doc_id: str, new_doc_id: str, *, write: bool = True
) -> list[dict]:
    """So 2 văn bản, trả list[PointDiff]. write=False để xem trước, không ghi.

    Ghi vào graph gồm 2 việc, không được thiếu việc nào:
      - Tạo SUPERSEDED_BY (để trả lời "điều này đổi thế nào")
      - Đóng effective_to của Điểm cũ (để Q2 time-travel chạy đúng)
    """
    new_doc = connection.run(
        "MATCH (d:LegalDocument {doc_id: $id}) RETURN toString(d.effective_date) AS eff",
        id=new_doc_id,
    )
    if not new_doc:
        raise ValueError(f"không tìm thấy văn bản {new_doc_id}")
    cutover = new_doc[0]["eff"]

    # Ghép Điều trước, rồi mới ghép node lá trong phạm vi cặp Điều đã khớp.
    # Bỏ bước này là ghép hàng trăm node giữa biển nhiễu.
    article_map = pair_articles(old_doc_id, new_doc_id)
    pairs = _pair_points(
        _fetch_leaves(old_doc_id), _fetch_leaves(new_doc_id), article_map
    )

    diffs: list[dict] = []
    stmts: list[tuple[str, dict]] = []

    for old, new in pairs:
        change_type, sim, summary = _classify(old, new)
        diffs.append(
            {
                # Tên field giữ nguyên theo contract PointDiff (P4 đang đọc).
                # Giá trị giờ có thể là point_id, clause_id hoặc article_id —
                # tuỳ node lá nằm ở tầng nào.
                "old_point_id": old["node_id"] if old else None,
                "new_point_id": new["node_id"] if new else None,
                "level": (old or new).get("level"),
                "change_type": change_type,
                "similarity": round(sim, 4),
                "summary": summary,
            }
        )
        if not write:
            continue
        if old and new:
            stmts.append(
                (
                    _MERGE_SUPERSEDED,
                    {
                        "old_id": old["node_id"],
                        "new_id": new["node_id"],
                        "change_type": change_type,
                        "similarity": round(sim, 4),
                        "effective_from": cutover,
                    },
                )
            )
        if old:
            # Node cũ hết hiệu lực từ ngày văn bản mới có hiệu lực.
            # Thiếu bước này thì Q2 trả cả node cũ lẫn node mới -> sai.
            stmts.append(
                (_CLOSE_OLD_NODE, {"node_id": old["node_id"], "effective_to": cutover})
            )

    if stmts:
        connection.write_batch(stmts)

    diffs.sort(key=lambda d: (d["old_point_id"] or "zzz", d["new_point_id"] or "zzz"))
    return diffs


# ---------------------------------------------------------------------------
# Time-travel
# ---------------------------------------------------------------------------


def law_as_of(topic: str | None, date: str) -> list[dict]:
    """Luật có hiệu lực tại ngày `date`. Đây là thứ RAG vector không làm được."""
    from backend.graph.schema import Q2_LAW_AS_OF

    return connection.run(Q2_LAW_AS_OF, date=date, topic=topic)


def point_history(node_id: str) -> list[dict]:
    """Lần theo chuỗi SUPERSEDED_BY: một quy định đã đổi qua những bản nào.

    Nhận point_id, clause_id hoặc article_id — SUPERSEDED_BY giờ nối node lá ở
    bất kỳ tầng nào, không chỉ Điểm.
    """
    return connection.run(
        """
        MATCH (start) WHERE start.point_id = $node_id OR start.clause_id = $node_id
                          OR start.article_id = $node_id
        MATCH path = (start)-[:SUPERSEDED_BY*0..]->(n)
        RETURN coalesce(n.point_id, n.clause_id, n.article_id) AS point_id,
               labels(n)[0] AS level,
               n.text AS text,
               toString(n.effective_from) AS effective_from,
               toString(n.effective_to) AS effective_to,
               length(path) AS step
        ORDER BY step
        """,
        node_id=node_id,
    )


def refine_with_llm(diffs: list[dict]) -> list[dict]:
    """[Để sau] Nhờ LLM phân loại lại chỗ regex bó tay.

    Chỉ gọi cho REWORDED có similarity thấp — chỗ đổi nghĩa mà không đổi số.
    Cần core/llm.py của P4. Không chặn: regex đã đủ cho fixture và cho demo.
    """
    raise NotImplementedError


if __name__ == "__main__":
    for d in diff_documents("mock-old", "mock-new"):
        print(
            f"{d['change_type']:<10} {d['old_point_id'] or '-':<20} -> "
            f"{d['new_point_id'] or '-':<20} sim={d['similarity']:.2f}  {d['summary']}"
        )
