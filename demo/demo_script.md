# Kịch bản demo (5 phút)

> Cả team diễn tập **2 lần** có bấm giờ ở giờ thứ 22. Người demo mở sẵn 3 tab.

## Chuẩn bị trước khi bấm chạy

Ba tab mở sẵn theo thứ tự:
1. Slide bìa (vấn đề + số liệu)
2. Neo4j Browser — `http://localhost:7474` — chạy sẵn query
   `MATCH (o:Point)-[r:SUPERSEDED_BY]->(n:Point) RETURN o, r, n LIMIT 25`
3. Dashboard — `http://localhost:8000/` (tab Trends được active mặc định)
4. Slide eval (số accuracy từ `eval/run_eval.py`)

Kiểm tra `curl :8000/health` → `graph_source` phải là **`neo4j`** (nếu vẫn
`mock` nghĩa là P2 chưa nạp — cắm cờ demo mock cũng chạy nhưng phải nói rõ).

## Kịch bản

| Phút | Màn hình | Lời thoại |
|---|---|---|
| 0:00 | Slide | "Nghị định 168/2025 có hiệu lực 01/07/2026. Trong 2 tuần đầu, 47 lần tin đồn 'uống 1 lon bia bị tước bằng vĩnh viễn' đã lan trên mạng — không cơ quan nào chỉnh chính thức. Chúng tôi phát hiện được vì nối hai luồng dữ liệu vào một graph." |
| 0:30 | Neo4j Browser | "Đây là graph THẬT, không phải vector store. Điều — Khoản — Điểm là node, `SUPERSEDED_BY` ở mức Điểm là cạnh — cho phép trả lời 'luật nói gì tại ngày 1/7' và 'điều này đổi thế nào'." Chỉ vào 1 cạnh cụ thể. |
| 1:30 | Dashboard tab **Cảnh báo hiệu nhầm** | "Đây là 3 hiểu nhầm đang lan. Cái đầu 47 lần lặp, 12k tương tác, cấp HIGH. Click vào." |
| 2:00 | Card mở ra | Đọc câu định chính từ hệ thống. "Không phải bịa — người dân đang nhớ khung phạt cũ. Cả 2 văn bản đều có 30–40 triệu, nhưng chỉ văn bản cũ *có thể diễn giải* thành vĩnh viễn." |
| 2:45 | Tab **Văn bản cũ vs mới** | Side-by-side `nd100-d5-k10-a` ↔ `nd168-d5-k9-a`. "SUPERSEDED_BY ở mức Điểm, có `change_type`, có ngày hiệu lực. Vector RAG không làm được." |
| 3:30 | Tab **Hỏi — Đáp** | Nhập: "Uống 1 lon bia thì bị phạt bao nhiêu từ 1/7/2026?" — chọn ngày 2026-07-01. |
| 3:50 | Kết quả | "Trả lời kèm citation Điều — Khoản — Điểm. Mỗi `node_id` được API validate lại với graph — LLM bịa là bị lọc luôn." |
| 4:15 | Câu hỏi lạc đề | Nhập "Tôi nên đầu tư cổ phiếu nào?" — hệ thống trả `refused` **"không đủ căn cứ"**. "Không đoán bừa. Đây là nguyên tắc cứng." |
| 4:35 | Slide eval | "50 claim gắn nhãn tay, accuracy X%, precision Y%. Số cụ thể ở `eval/run_eval.py`, không nói suông." |

## Câu BGK sẽ hỏi — chuẩn bị trước

1. **"Sao không dùng RAG vector cho nhanh?"**
   → Vector không trả lời được "luật nói gì ngày 1/7" và "điều này đổi thế nào".
   `SUPERSEDED_BY` ở mức Điểm làm được. Mở Neo4j Browser cho xem.
2. **"Làm sao biết phân loại đúng/sai chính xác?"**
   → Mở `eval/`. Accuracy trên gold set 50 claim. (KHÔNG có số này = mất điểm nặng)
3. **"LLM bịa điều luật thì sao?"**
   → Mỗi câu trả lời trích `node_id` có thật trong graph — API validate ở
   `backend/api/qa_endpoint.py::_llm_answer`, citation không khớp bị lọc. Không
   tìm thấy → từ chối trả lời (`mode = refused`). Demo bằng câu hỏi lạc đề.
4. **"Dữ liệu comment lấy thế nào, có vi phạm gì không?"**
   → Chỉ nội dung công khai trên báo điện tử, hash tác giả (`author_hash`),
   không lưu danh tính. Xem `backend/models/schemas.py::Post`.
5. **"Nếu Anthropic API sập giữa demo?"**
   → API tự fallback sang `mode = template`: trả nguyên văn điều luật khớp
   keyword + citation vẫn thật. Dashboard không vỡ.

## Checklist trước demo

- [ ] `docker compose up` xanh cả `neo4j` và `api`
- [ ] `curl :8000/health` → `graph_source: neo4j`
- [ ] `curl :8000/trends | jq length` ≥ 3
- [ ] Ask thử 2 câu mẫu + 1 câu lạc đề, đều có kết quả đúng mode
- [ ] `python eval/run_eval.py` in số accuracy — chụp màn hình sẵn cho slide
- [ ] Neo4j Browser đã save query `SUPERSEDED_BY` — bấm 1 phát là ra hình
- [ ] Người demo ngủ ≥ 4 tiếng trước giờ trình bày
