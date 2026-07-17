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
cp .env.example .env        # điền ANTHROPIC_API_KEY
docker compose up           # Neo4j + API
```

- API: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474
- Dashboard: mở `frontend/static/index.html`

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
| `frontend/static/` | dashboard 1 trang, 2 tab | P4 |
| `eval/` | đo độ chính xác trên gold set | P3 |
| `prompts/` | prompt LLM dùng trong pipeline | P1, P3 |
| `demo/` | kịch bản demo + case mẫu nồng độ cồn | P4 |

## Dữ liệu demo

Văn bản có hiệu lực từ 1/7/2026, thảo luận công khai đến 17/7/2026.
Comment chỉ lấy nội dung công khai, tác giả được hash, không lưu danh tính.
