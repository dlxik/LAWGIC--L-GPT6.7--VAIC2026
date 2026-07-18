# Query demo cho Neo4j Browser (P2 — đã verify trên dữ liệu THẬT)

> Đề tài đã chốt: **luật thuế** (`qlt2019`, `qlt2025`, `tncn2025`). Mọi query
> dưới đây chạy trên đúng dữ liệu đang có trong graph.

Mở `http://localhost:7474`. Mỗi query dưới trả **8–40 node**, hình vừa mắt.
KHÔNG bấm "hiện tất cả" (3.979 node → treo Browser, thành một búi vô nghĩa).

---

## Query 1 — Một Điều là graph có tổ chức, không phải khối text (~10 node)

```cypher
MATCH (a:Article {article_id:'qlt2025-d25'})-[:HAS_CLAUSE]->(k)-[:HAS_POINT]->(p)
OPTIONAL MATCH (p)-[r]->(e)
RETURN a, k, p, e
```

**Lời thoại:** "Đây là Điều 25 Luật Quản lý thuế mới — quy định ấn định thuế.
Không phải một đoạn văn: nó là Điều chứa Khoản chứa Điểm, mỗi Điểm nối tới
nghĩa vụ / mức phạt / chủ thể. Máy **hiểu cấu trúc** điều luật, không chỉ lưu chữ."

---

## Query 2 — Semantic diff, ăn tiền nhất (~8 node)

```cypher
MATCH (o:Point)-[s:SUPERSEDED_BY]->(n:Point)
WHERE o.point_id STARTS WITH 'qlt2019-d52'
RETURN o, s, n
```

**Lời thoại:** "Bên trái là Điều **52** Luật Quản lý thuế 2019, bên phải Điều
**25** luật 2025 — số hiệu Điều khác hẳn nhau, hệ thống vẫn **tự nhận ra chúng
là một quy định** nhờ khớp nội dung, không khớp số thứ tự. Cạnh SUPERSEDED_BY
cho biết cái nào thay cái nào. Đây là version tracking mà vector store không có."

> Bối cảnh: cả điều này nói về căn cứ ấn định thuế ("Người khai thuế dựa vào các
> tài liệu không hợp pháp để khai thuế..."). Luật mới đổi thuật ngữ
> "Người khai thuế" → "Người nộp thuế" nhưng giữ nguyên bản chất → hệ thống
> vẫn ghép đúng (similarity ~0.82, trên ngưỡng 0.75).

---

## Query 3 — Hiệu lực so le trong CÙNG một luật (trump card, ~30 node)

```cypher
MATCH (d:LegalDocument {doc_id:'qlt2025'})-[:HAS_ARTICLE]->(a:Article)
WHERE a.article_id IN ['qlt2025-d13','qlt2025-d25']
OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(k)
RETURN a, k
```

**Lời thoại:** "Cùng một văn bản — Luật 2025 — nhưng Điều 13 (hộ, cá nhân kinh
doanh) hiệu lực từ **01/01/2026**, còn phần lớn luật hiệu lực **01/07/2026**.
Chỉ vào `effective_from` của hai node. Nếu gắn ngày hiệu lực ở cấp *văn bản*
như mọi hệ thống khác, **không thể** biểu diễn được điều này — đây là lý do
chúng tôi bắt buộc phải để hiệu lực ở cấp node."

---

## Câu time-travel (chạy ở console/API, không phải Browser)

Cùng một câu hỏi "luật thuế nói gì", hỏi hai ngày cách nhau **một hôm**:

```cypher
// Đổi $date giữa '2026-06-30' và '2026-07-01'
MATCH (n) WHERE (n:Article OR n:Clause OR n:Point)
  AND NOT (n)-[:HAS_POINT|HAS_CLAUSE]->()      // chỉ leaf: node sâu nhất giữ sự thật
  AND n.effective_from <= date($date)
  AND (n.effective_to IS NULL OR n.effective_to > date($date))
RETURN count(n) AS so_quy_dinh_hieu_luc
```

**Kết quả thật:** ngày 30/6 → **951** quy định; ngày 1/7 → **695**. Cùng câu
hỏi, lệch 1 ngày, **256 quy định khác nhau**. "Hỏi luật ở một thời điểm bất kỳ
trong quá khứ hay tương lai — graph trả đúng phiên bản có hiệu lực hôm đó."

---

## Con số nền (để nói khi bị hỏi "graph to cỡ nào")

- **3.979 node**, **5.401 cạnh** toàn graph
- **119 cạnh SUPERSEDED_BY** (49 cặp Điểm + 70 cặp Khoản/Điều) — tất cả qlt2019→qlt2025
- 3 văn bản: 38/2019/QH14, 108/2025/QH15, 109/2025/QH15

## Mạch bấm khi demo

Query 1 (cấu trúc) → Query 2 (thời gian/diff) → Query 3 (so le) → xen câu
time-travel ở console. Ba lần bấm nút Graph, mỗi lần một luận điểm.
