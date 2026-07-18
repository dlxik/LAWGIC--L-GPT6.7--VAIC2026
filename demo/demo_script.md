# Kịch bản demo LAWGIC (5 phút)

> Case chính: **ngưỡng 500 triệu TNCN** — luật thuế TNCN 109/2025 miễn thuế
> cho hộ kinh doanh doanh thu ≤ 500 triệu/năm, nhưng dư luận vẫn nghĩ ngưỡng
> nằm ở mức 100–120 triệu (nhớ nhầm quy định cũ). Team diễn tập **2 lần**
> có bấm giờ ở giờ thứ 22.

---

## Chuẩn bị trước khi bấm chạy

Bốn tab mở sẵn theo thứ tự:
1. **Slide bìa** (vấn đề + số liệu)
2. **Neo4j Browser** — `http://localhost:7474` — style đã dán theo
   `demo/graph_legend.md`, query 1/2/3 (`demo/graph_demo_queries.md`) đã save
3. **Dashboard** — `http://localhost:8000/` — sidebar bên trái, tab Cảnh báo mở sẵn
4. **Slide eval** (số accuracy + hallucination rate)

Kiểm tra `curl :8000/health` → `graph_source: neo4j` (nếu vẫn `mock` thì P2 chưa
nạp — báo cả team). Kiểm tra `curl :8000/stats` phải ra **3 văn bản, 234 điều,
988 khoản, 833 điểm, 3.321 post**.

Người demo đăng nhập trước với `admin@lawgic.vn` (bất kỳ mật khẩu) — sidebar sẽ
hiển thị vai trò **Quản trị**, tab So sánh mở khóa, giới hạn Q&A biến mất.

---

## Kịch bản chi tiết

| Phút | Màn hình | Lời thoại |
|---|---|---|
| **0:00** | Slide 1 | "Nghị định thuế mới có hiệu lực từ 01/07/2026. Trong 10 tháng trước đó, chúng tôi đã thu **3.321 bình luận công khai** trên VnExpress bàn về thuế hộ kinh doanh. **~70 bình luận** khẳng định ngưỡng chịu thuế TNCN nằm ở 100–200 triệu — trong khi luật thực tế miễn tới 500 triệu. Không cơ quan nào chỉnh chính thức. Chúng tôi phát hiện được vì nối hai luồng dữ liệu vào một **graph**." |
| **0:30** | Neo4j Browser · Query 1 | "Đây là graph THẬT — không phải vector store. Điều → Khoản → Điểm là node, và mỗi node có nghĩa vụ, chủ thể, mức phạt, thuế suất, miễn giảm ở tầng dưới. **3.979 node · 5.401 cạnh · 3 văn bản** thuế: Luật Quản lý thuế 2019, sửa đổi 2025, và Luật TNCN 2025." Chỉ vào cạnh `HAS_EXEMPTION` màu xanh rêu. |
| **1:30** | Dashboard · **Cảnh báo hiểu nhầm** | "Đây là 3 hiểu nhầm hệ thống đang gắn cờ. Cái đầu — 'thu nhập 100-120 triệu đã phải nộp thuế TNCN' — 6 lần lặp, 98 tương tác, mức HIGH. Click." |
| **2:00** | Card mở ra inline | Đọc câu định chính. "Không phải bịa — người dân đang nhớ khung khoán thuế của Luật 2019. Cả 2 văn bản đều nói 'hộ kinh doanh', chỉ 1 văn bản còn hiệu lực." |
| **2:30** | Dashboard · **So sánh văn bản** | Chỉ side-by-side `qlt2019-d51` (khoán thuế) → `qlt2025-d25`: "Luật mới BỎ hẳn phương pháp khoán. Cụm từ 'phương pháp khoán' xuất hiện **0 lần** trong luật 2025, nhiều lần trong luật 2019. Đây là `SUPERSEDED_BY` — quan hệ RAG vector không làm được." |
| **3:15** | Neo4j Browser · Query 3 | "Cùng LUẬT 2025, nhưng Điều 13 (hộ kinh doanh) hiệu lực 01/01/2026, phần lớn luật hiệu lực 01/07/2026. Nếu gắn ngày hiệu lực ở cấp *văn bản*, không thể biểu diễn được điều này. Chúng tôi buộc phải để hiệu lực ở cấp node." |
| **3:45** | Dashboard · **Hỏi — Đáp** | Nhập: "Hộ kinh doanh doanh thu 400 triệu/năm có phải nộp thuế TNCN?" — chọn ngày 2026-07-01. |
| **4:00** | Kết quả | "Trả lời kèm citation Điều 7 Khoản 1 Luật TNCN 109/2025. Mỗi `node_id` được API validate lại với graph — LLM bịa là bị lọc thẳng." Chỉ vào citation nguyên văn. |
| **4:20** | Câu hỏi lạc đề | Nhập "Tôi nên đầu tư tiền ảo không?" — mode `REFUSED`, câu trả lời "không đủ căn cứ". "Không đoán bừa. Đây là nguyên tắc cứng." |
| **4:40** | Slide eval | "**60,4% verdict accuracy · 54,3% citation accuracy** trên gold set 48 claim gắn nhãn tay, cấu hình có graph. Baseline đoán bừa 29%. Extractor entity F1 **80% (gemma-4-31B)** hoặc **84% (voting hybrid)** trên 100-node gold. Số cụ thể, không nói suông." |

---

## Con số ăn tiền — quotable trong lúc trả lời BGK

**Corpus**
- **3 văn bản thuế**: Luật QLT 38/2019/QH14, sửa đổi 108/2025/QH15, TNCN 109/2025/QH15
- **3.979 node, 5.401 cạnh**, trong đó **119 cạnh `SUPERSEDED_BY`** (49 Điểm + 67 Khoản + 3 Điều) từ 2019 → 2025
- **1.842 node** có ≥1 entity trích xuất, bao gồm 46 `TaxRate`, 46 `TaxBase`, 43 `Exemption`

**Discourse (dữ liệu thảo luận)**
- **3.321 bình luận công khai** trên VnExpress (goal DIVISION.md ≥ 500, vượt gấp 6 lần)
- **1.446 root + 1.875 reply** (tỉ lệ reply 56%), **1.893 tác giả** hash
- Thời gian trải: **04/06/2025 → 10/04/2026** (10 tháng)

**Eval P1 (extractor)**
- **100-node gold**, đơn annotator, 4 vòng review chéo
- gemma-4-31B: **80% F1** (P 70, R 93), gpt-oss-20b **77%**, SaoLa 67%, Llama-3.3-70B 64%
- **Voting hybrid** (gpt-oss ∩ gemma + gpt-oss penalties): **84% F1** (P 80, R 89), hallucination **20%** (so với 32% single-model)

**Eval P3 (verdict + citation)**
- **48 claim gold** gắn nhãn tay (LLM-drafted, human-reviewed)
- **Verdict accuracy 60,4%** (4 nhãn) — baseline 29,2%
- **Citation accuracy 54,3%** (trỏ đúng node_id) — baseline gần 0
- Cấu hình: FPT AI `gpt-oss-120b`, retriever hybrid TF-IDF + embedding + graph expansion (`SUPERSEDED_BY` cả 2 chiều + doc-level bridge)
- Bật graph: citation 43% → **54%**, verdict → **60%**. Đây là bằng chứng graph đóng góp giá trị đo được.

**Tests**
- P2: **26/26 test xanh** trên real tax-law data (Linh xác nhận trong `linh.md`)
- P1: parser 100% recall trên 2.055 node, 0 invariant errors

---

## Câu BGK sẽ hỏi — chuẩn bị trước

1. **"Sao không dùng RAG vector cho nhanh?"**
   → Vector không trả lời được "luật nói gì ngày 01/07/2026" và "điều này đã đổi thế nào".
   `SUPERSEDED_BY` ở mức Điểm làm được. Mở Neo4j Browser + Query 2 cho xem.
   Số cụ thể: chuyển từ ngày 30/6 sang 1/7 → **256 quy định khác nhau** (951 → 695).

2. **"Làm sao biết phân loại đúng/sai chính xác?"**
   → Mở `eval/gold_set.jsonl` (48 claim). Chạy `python eval/run_eval.py` →
   **60,4% verdict, 54,3% citation**. Bật/tắt graph để so: graph-off 43% citation,
   graph-on 54% — chênh 11 điểm là đóng góp cụ thể của `SUPERSEDED_BY`.
   (**KHÔNG** có con số này = mất điểm nặng.)

3. **"LLM bịa điều luật thì sao?"**
   → Mỗi câu trả lời trích `node_id` có thật trong graph — API validate ở
   `backend/api/qa_endpoint.py::_llm_answer`, citation không khớp bị lọc.
   Không tìm thấy → tự động về `mode = refused`. **Demo bằng câu hỏi tiền ảo**.

4. **"Dữ liệu comment lấy thế nào, có vi phạm gì không?"**
   → Chỉ nội dung công khai trên báo điện tử (VnExpress), hash tác giả
   (`author_hash`), không lưu danh tính. Xem `backend/models/schemas.py::Post`.

5. **"Nếu Anthropic/FPT API sập giữa demo?"**
   → API tự fallback sang `mode = template`: trả nguyên văn điều luật khớp
   full-text retrieval + citation vẫn thật. Dashboard không vỡ. Còn có
   **rate limit** riêng (`backend/api/ratelimit.py`) 10 câu/phút/IP để chống burst.

6. **"Tại sao gold set chỉ 48 claim, và 60% có tin cậy không?"**
   → 48 claim với CI ~10 điểm; tin cậy cho **hướng đi** chứ không tuyệt đối.
   Con số baseline 29% (đoán nhãn phổ biến nhất) là mốc để so — chúng tôi hơn
   **30 điểm**. Caveat: gold LLM-drafted, human-reviewed một lượt; không có
   inter-annotator Kappa. Với thời lượng hackathon, sample size này là hợp lý;
   scale lên 200-500 là bước kế tiếp.

---

## Checklist trước demo

- [ ] `docker compose up` xanh cả `neo4j` và `api`
- [ ] `curl :8000/health` → `graph_source: neo4j`
- [ ] `curl :8000/stats` → mode `neo4j`, đủ 3 văn bản, ≥3 misconceptions
- [ ] `curl :8000/documents/qlt2025/file` → 200, ~50KB
- [ ] Hỏi Q&A câu chuẩn + câu lạc đề, đúng mode template/llm và refused
- [ ] Dán Neo4j `.grass` style, save 3 query
- [ ] `python eval/run_eval.py` → chụp màn hình sẵn cho slide
- [ ] Đăng nhập trước dashboard bằng `admin@lawgic.vn`
- [ ] Người demo ngủ ≥ 4 tiếng trước giờ trình bày
