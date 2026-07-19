# Deploy public — Render (API) + Neo4j Aura Free (DB)

Hướng dẫn đưa LAWGIC lên mạng public, miễn phí, đủ cho demo ~10 người.
Kiến trúc: **Neo4j chạy trên Aura Free (managed)** + **API FastAPI chạy trên Render Free**.
LLM vẫn gọi FPT AI Marketplace qua env var.

File đã chuẩn bị sẵn: `Dockerfile` (build cả repo), `.dockerignore`, `render.yaml` (blueprint).

---

## Bước 1 — Tạo Neo4j Aura Free (~5 phút)

1. Vào https://console.neo4j.io → đăng ký (Google được).
2. **Create instance** → chọn **AuraDB Free**.
3. Aura sinh ra credentials — **lưu lại ngay** (chỉ hiện 1 lần), gồm:
   - `NEO4J_URI` dạng `neo4j+s://xxxxxxxx.databases.neo4j.io`
   - `NEO4J_USERNAME` = `neo4j`
   - `NEO4J_PASSWORD` = chuỗi Aura tự sinh
4. Đợi instance chuyển trạng thái **Running** (~1 phút).

> Giới hạn Aura Free: 200k node / 400k quan hệ (graph LAWGIC ~2.055 node — dư sức).
> Instance tự **pause sau 3 ngày** không dùng; vào console bấm **Resume** là chạy lại.

---

## Bước 2 — Nạp graph lên Aura từ máy bạn (~3 phút)

Chạy loader **một lần**, trỏ vào Aura (dùng `.venv` sẵn có của project):

```bash
# Trỏ tạm biến môi trường sang Aura (ghi đè .env cho lần chạy này)
export NEO4J_URI="neo4j+s://xxxxxxxx.databases.neo4j.io"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<mật-khẩu-Aura>"

# Nạp toàn bộ graph (xoá sạch rồi nạp lại)
python -m backend.graph.loader --wipe
```

Kiểm tra: vào **Aura console → Query** chạy `MATCH (d:LegalDocument) RETURN count(d)` — phải ra **3**.

---

## Bước 3 — Deploy API lên Render (~5 phút + 3–5 phút build)

1. Đảm bảo repo đã push lên GitHub (đã có remote).
2. Vào https://render.com → đăng ký → **New +** → **Blueprint**.
3. Chọn repo `LAWGIC--L-GPT6.7--VAIC2026`. Render tự đọc `render.yaml`.
4. Điền các biến **secret** (đánh dấu `sync:false`) khi Render hỏi:
   - `NEO4J_URI` = `neo4j+s://xxxxxxxx.databases.neo4j.io`
   - `NEO4J_PASSWORD` = mật khẩu Aura
   - `LLM_API_KEY` = key FPT AI Marketplace của bạn
   *(các biến còn lại `render.yaml` đã điền sẵn.)*
5. **Apply / Deploy**. Render build image từ `Dockerfile` và chạy.
6. Xong sẽ có URL công khai dạng: `https://lawgic-api.onrender.com`

Kiểm tra:
- Mở `https://<app>.onrender.com/health` → phải thấy `"graph_source": "neo4j"`.
- Mở `https://<app>.onrender.com/` → dashboard hoạt động, thử tab Hỏi — Đáp.

---

## Lưu ý vận hành

| Vấn đề | Xử lý |
|---|---|
| **Render Free ngủ sau ~15 phút** không truy cập | Lần bấm đầu chờ ~50s để "thức". Cần luôn sẵn thì nâng gói **Starter ~$7/tháng** |
| **Aura pause sau 3 ngày** | Vào console bấm **Resume** trước buổi demo |
| Trước demo | Bấm thử 1 request để "hâm nóng" cả Render lẫn Aura khoảng 1–2 phút trước khi trình bày |
| Bảo mật | Không commit `.env`; không mở cổng Neo4j 7474/7687 ra ngoài (Aura đã lo phần này) |
| CORS | Đang mở `*` cho demo — siết lại domain thật nếu lên production |

## Cập nhật về sau
Mỗi lần push lên nhánh đã kết nối, Render **tự build lại** (`autoDeploy: true`).
Đổi dữ liệu graph thì chạy lại Bước 2 (loader trỏ Aura), không cần deploy lại API.
