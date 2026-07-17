# Chia việc 24h — 4 người

## Nguyên tắc sống còn

1. **Contract chốt ở giờ 1, sau đó đóng băng.** `backend/models/schemas.py` +
   `backend/graph/schema.py` là hợp đồng chung. Chốt xong không ai sửa một mình —
   muốn đổi field phải báo cả team. Đây là thứ duy nhất cho phép 4 người code song song.
2. **Mock trước, thật sau.** Ngay sau khi chốt contract, mỗi người tự tạo 3-5 bản ghi
   mock đúng schema và code trên đó. Không ai được ngồi chờ dữ liệu của người khác.
3. **Mỗi người 1 thư mục, không giẫm chân.** Branch `p1-ingestion`, `p2-graph`,
   `p3-discourse`, `p4-api`. Merge vào `main` ở 3 mốc tích hợp (giờ 8, 16, 21).
4. **Giờ 20 là deadline tính năng.** Sau đó chỉ sửa lỗi và dựng demo. Tính năng nào
   chưa xong ở giờ 20 thì bỏ, không cố.

---

## Ai làm gì

| | Người | Sở hữu | Giao nộp cuối |
|---|---|---|---|
| **P1** | Văn bản pháp luật | `scripts/fetch_legal_docs.py`, `backend/ingestion/` | JSON có cấu trúc của ≥3 văn bản (1 cũ + 1 mới sửa đổi nó + 1 văn bản khác) |
| **P2** | Graph | `backend/graph/` | Neo4j chạy được, nạp đủ dữ liệu, diffing + truy vấn theo thời gian hoạt động |
| **P3** | Dư luận + đo lường | `scripts/fetch_social_posts.py`, `backend/discourse/`, `eval/` | ≥500 post đã gắn nhãn + **số accuracy trên gold set** |
| **P4** | API + Dashboard + Demo | `backend/core/llm.py`, `backend/api/`, `frontend/`, `demo/` | Dashboard chạy, Q&A có citation, kịch bản demo đã diễn tập |

**P4 làm `core/llm.py` trước tiên** vì P1 và P3 đều gọi nó. Xong ở giờ 3, không được trễ.

---

## Timeline

### Giờ 0–1 — CẢ TEAM NGỒI CHUNG
Chốt `schemas.py` và `graph/schema.py`. Chọn đúng 3 văn bản demo (bắt buộc có
1 cặp cũ/mới để trình diễn semantic diffing — đây là điểm ăn tiền, không có thì
cả dự án chỉ còn là RAG). Chốt xong mới tản ra.

### Giờ 1–8 — Chạy song song trên mock

- **P1**: crawl 3 văn bản → regex parser Điều-Khoản-Điểm. Mốc giờ 8: 1 văn bản
  parse ra JSON đúng schema.
- **P2**: dựng Neo4j (`docker compose up neo4j`), viết constraint + `loader.py`.
  Mốc giờ 8: nạp được document mock, mở Neo4j Browser thấy cây Điều-Khoản-Điểm.
- **P3**: crawl comment (chạy nền, tốn thời gian nhất — **bắt đầu ngay giờ 1**),
  song song viết `classifier.py`. Mốc giờ 8: ≥500 post thô trong `data/raw/`.
- **P4**: `core/llm.py` xong **giờ 3** (P1/P3 đang chờ). Sau đó FastAPI khung +
  HTML dashboard tĩnh với dữ liệu giả.

> **Mốc tích hợp 1 (giờ 8):** merge hết vào `main`. P1 đưa JSON thật cho P2 nạp.
> Nếu schema có chỗ sai thì sửa **ngay lúc này** — sau giờ 8 thì đắt.

### Giờ 8–16 — Nối dây

- **P1**: `extractor.py` — trích entity bằng LLM. Xong 3 văn bản đầy đủ.
- **P2**: `diffing.py` — SUPERSEDED_BY ở mức Điểm + `law_as_of()`. **Đây là phần
  khó nhất và khác biệt nhất của cả dự án.** P2 không làm việc gì khác ở khung giờ này.
- **P3**: `linker.py` + `misinformation.py`. Chạy Batches API cho toàn bộ post
  (rẻ 50%, mất <1h — **bấm chạy rồi làm việc khác**, đừng ngồi nhìn).
- **P4**: nối API vào Neo4j thật. `/qa` và `/trends` trả dữ liệu thật.

> **Mốc tích hợp 2 (giờ 16):** dashboard hiển thị được trend thật từ graph thật.
> Đây là lúc biết dự án có sống hay không.

### Giờ 16–20 — Hoàn thiện

- **P1**: vá chỗ parser fail, kiểm tra thủ công 20 node bất kỳ.
- **P2**: tối ưu truy vấn, đảm bảo Neo4j Browser trình diễn được (demo sẽ mở nó).
- **P3**: **gắn nhãn tay 50 claim → chạy `eval/run_eval.py` → lấy con số.**
  Không có con số này là mất điểm nặng, ưu tiên hơn mọi thứ khác của P3.
- **P4**: dashboard cho ra hồn, viết `demo_script.md`.

> **Mốc tích hợp 3 (giờ 20–21): ĐÓNG BĂNG TÍNH NĂNG.** Từ đây chỉ sửa lỗi.

### Giờ 21–24 — Demo

- Cả team diễn tập demo **2 lần** có bấm giờ.
- Chuẩn bị 4 câu BGK sẽ hỏi (xem `demo/demo_script.md`).
- Ngủ. Người ngồi demo phải tỉnh táo.

---

## Rủi ro đã biết

| Rủi ro | Xử lý |
|---|---|
| Crawl comment chậm / bị chặn | P3 bắt đầu **giờ 1**, không phải giờ 8. Chặn thì chuyển sang xuất thủ công từ 1-2 bài báo — 500 post là đủ demo |
| Parser gãy vì văn bản định dạng loạn | Chọn 3 văn bản HTML sạch. Không tham PDF scan |
| Diffing không kịp | Đây là **khác biệt cốt lõi, không được bỏ**. Không kịp thì P1 sang hỗ trợ P2 ở giờ 16 |
| LLM bịa điều luật | Mọi citation phải khớp `node_id` có thật trong graph. P4 kiểm tra ở tầng API, không tin LLM |
| Hết tiền API | Batches API cho phân loại (rẻ 50%) + prompt caching cho corpus luật. Đừng chạy `effort=high` cho việc vặt |

## Câu hỏi cần trả lời trước khi bắt đầu

- 3 văn bản demo cụ thể là gì? (P1 chốt trong 30 phút đầu, cần đúng 1 cặp sửa đổi)
- Ai có API key Anthropic, hạn mức bao nhiêu?
- Crawl comment từ báo nào? Có bị chặn không? (P3 thử ngay giờ đầu)
