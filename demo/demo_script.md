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
| 4:35 | Slide eval | "48 claim gắn nhãn tay. Metric chính — PHÁT HIỆN TIN SAI: **86,8%** (recall 0,86), trích đúng điều luật **76,2%**. Verdict 4-nhãn ~60% vì ranh giới đúng/sai-một-phần mơ hồ — ta nói thẳng. Số ở `eval/run_eval.py`, không nói suông." |

## Câu BGK sẽ hỏi — chuẩn bị trước

1. **"Sao không dùng RAG vector cho nhanh?"**
   → Vector không trả lời được "luật nói gì ngày 1/7" và "điều này đổi thế nào".
   `SUPERSEDED_BY` ở mức Điểm làm được. Mở Neo4j Browser cho xem.
2. **"Làm sao biết phân loại đúng/sai chính xác?"**
   → Mở `eval/`. **Phát hiện tin sai 86,8%** (recall 0,86), citation 76,2% trên gold
   48 claim. Verdict 4-nhãn ~60% — nói thẳng là bị chặn bởi ranh giới ACCURATE↔PARTIAL
   mơ hồ (người gán nhãn cũng cãi), không giấu. (KHÔNG có số này = mất điểm nặng)
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
- [ ] `curl :8000/trends | jq length` ≥ 1 (data thuế: 1 trend "120tr phải nộp thuế"
      với `--as-of 2025-11-20 --window 48 --min-occ 3`; regen bằng `run_pipeline.py`)
- [ ] Ask thử 2 câu mẫu + 1 câu lạc đề, đều có kết quả đúng mode
- [ ] `USE_EMBEDDINGS=0 python eval/run_eval.py` in số (TF-IDF ổn định, tránh timeout
      524 FPT) — chạy ≥2 lần vì dao động ±8đ, chụp màn hình số đại diện cho slide
- [ ] Neo4j Browser đã save query `SUPERSEDED_BY` — bấm 1 phát là ra hình
- [ ] Người demo ngủ ≥ 4 tiếng trước giờ trình bày
