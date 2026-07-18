# LAWGIC — Legal Analytics With Graph-Integrated Cognition

Legal Knowledge Graph nối hai luồng — **văn bản pháp luật** và **thảo luận công khai** —
để phát hiện sớm hiểu nhầm chính sách trong dư luận.

> Chia việc cho team: xem [DIVISION.md](DIVISION.md)

## Khác biệt

- **Graph database thật**, không phải RAG vector thuần. Quan hệ `SUPERSEDED_BY` ở
  **mức Điểm** cho phép truy vấn "luật nói gì tại ngày X" và "điều này đã đổi thế nào" —
  vector store không làm được.
- **Version tracking theo thời gian**: tự phát hiện văn bản mới sửa đổi văn bản cũ (semantic diffing).
- **Mọi câu trả lời trích dẫn Điều–Khoản–Điểm.** Không tìm được căn cứ thì từ chối trả lời,
  không đoán.
- **Có đo lường**: `eval/` chấm độ chính xác phân loại trên gold set gắn nhãn tay.

## Chạy

```bash
# 1. Config: điền LLM_API_KEY (FPT AI Marketplace) + Neo4j password
cp .env.example .env

# 2. Up cả stack — Neo4j + API
docker compose up

# 3. Nạp graph một lần (chạy trong container api)
docker compose exec api python -m backend.graph.loader --wipe

# 4. Mở dashboard (đã mount /frontend/static tại root API)
open http://localhost:8000/
```

- **Dashboard**: http://localhost:8000/ (sidebar 4 tab: Cảnh báo hiểu nhầm, Hỏi–Đáp có citation, So sánh văn bản, Tra cứu văn bản)
- **API docs (Swagger)**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (paste `demo/graph_legend.md` để tô màu graph)

Dữ liệu (`data/processed/legal_docs_structured/`, `data/processed/entities_*.json`,
`data/raw/social_posts.json`) đã commit — không cần chạy lại parser/extractor. Nếu muốn build lại từ đầu, xem `scripts/`.

**Sign-in dashboard**: bất kỳ email/password nào cũng được (client-side fake auth cho hackathon).
Email chứa `admin` → vai trò Quản trị; email khác → Người dùng; không đăng nhập → Khách (5 câu Q&A/session).
Backend còn có rate limit thật: 10 câu Q&A + 30 tra cứu/phút/IP (xem `backend/api/ratelimit.py`).

## Pipeline

```
Văn bản luật ──> parser ──> extractor ──┐
 (P1)            Điều/Khoản/Điểm        │
                                        ├──> Neo4j ──> API ──> Dashboard
Bình luận ────> classifier ──> linker ──┘     (P2)      (P4)      (P4)
 (P3)           chủ đề        claim↔Điểm
                              │
                              └──> misinformation ──> cảnh báo trend
```

## Cấu trúc

| Thư mục | Nội dung | Phụ trách |
|---|---|---|
| `backend/models/schemas.py` | **Contract chung** — mọi module trao đổi qua đây | cả team |
| `backend/graph/schema.py` | **Contract graph** — node/relationship Neo4j | cả team |
| `backend/core/` | config + LLM client dùng chung | P4 |
| `backend/ingestion/` | parser Điều–Khoản–Điểm, trích entity | P1 |
| `backend/graph/` | loader, semantic diffing, truy vấn theo thời gian | P2 |
| `backend/discourse/` | phân loại chủ đề, liên kết claim↔điều luật, phát hiện trend | P3 |
| `backend/api/` | Q&A API (có citation) + API dashboard | P4 |
| `frontend/static/` | dashboard sidebar + 4 tab (roles: Khách / Người dùng / Quản trị) | P4 |
| `eval/` | đo độ chính xác trên gold set 48 claim | P3 |
| `prompts/` | prompt LLM dùng trong pipeline | P1, P3 |
| `demo/` | kịch bản demo tax + query Neo4j đã dán màu | P4 |

## Dữ liệu demo

Ba văn bản thuế: Luật Quản lý thuế **38/2019/QH14** (cũ, một phần bị thay thế),
Luật Quản lý thuế sửa đổi **108/2025/QH15**, Luật Thuế thu nhập cá nhân sửa đổi
**109/2025/QH15**. Cả hai luật mới hiệu lực **01/07/2026**. Case demo chính: ngưỡng
miễn TNCN **500 triệu** cho hộ kinh doanh — dư luận nhớ nhầm ngưỡng ~100–200 triệu
theo quy định khoán cũ.

Comment lấy công khai trên VnExpress (3.321 post, 04/06/2025 – 10/04/2026);
tác giả được hash, không lưu danh tính.
