# Chạy hệ thống LAWGIC từ đầu

---

## ⚡ MÁY MỚI (teammate) — chỉ cần xem GRAPH

Không cần API key, không cần crawl lại — dữ liệu luật đã nằm sẵn trong repo.
Cần: **Git**, **Docker Desktop**, **Python 3.11**.

```powershell
# 1. Lấy code (đã có sẵn thì bỏ qua, chỉ cần: git pull)
git clone https://github.com/dlxik/VAIC2026--L-GPT6.7.git
cd VAIC2026--L-GPT6.7

# 2. Cài thư viện Python
pip install -r backend/requirements.txt

# 3. Bật Neo4j (mở Docker Desktop trước, chờ nó xanh)
docker compose up -d neo4j
#    chờ ~15s cho Neo4j sẵn sàng

# 4. Nạp dữ liệu luật thật vào graph (~2-3 phút)
python -m backend.graph.loader --wipe
```

Xong. Mở **http://localhost:7474** (Neo4j Browser) → bấm **Connect** với:
- Connect URL: `bolt://localhost:7687`
- Username: `neo4j`
- Password: `lawgic-dev-password`

Rồi dán query trong [demo/graph_demo_queries.md](demo/graph_demo_queries.md) là ra hình graph.

> Graph sẽ **giống hệt máy mọi người** vì ID node là tất định + dùng chung dữ liệu
> trong repo. Nếu `docker compose` báo cổng 7474/7687 bận, tắt Neo4j bản khác đang
> chạy. Tiếng Việt lỗi font terminal thì chạy `$env:PYTHONIOENCODING="utf-8"` trước.

Muốn xem cả **dashboard + hỏi-đáp** thì đọc tiếp phần dưới (cần thêm bước bật API,
và chế độ B cần key FPT).

---

Hai chế độ:
- **Chế độ A — Graph + Dashboard** (KHÔNG cần API key): xem được graph luật,
  time-travel, semantic diff, dashboard đọc từ graph. Đây là phần chắc chắn chạy.
- **Chế độ B — Full có dư luận + Hỏi-Đáp** (CẦN key FPT): thêm bước chạy pipeline
  P3 để đổ bình luận → phát hiện hiểu nhầm, và Q&A trả lời bằng LLM.

---

## 0. Yêu cầu (chỉ làm 1 lần)

- **Docker Desktop** (đã cài trên máy này) — chứa Neo4j.
- **Python 3.11** (đã có).

Cài thư viện Python (từ thư mục gốc repo):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

> Nếu không muốn venv thì bỏ 2 dòng đầu, `pip install` thẳng. Trên máy này
> thư viện đã cài sẵn — có thể bỏ qua bước này.

---

## Chế độ A — Graph + Dashboard (không cần key)

### A1. Bật Neo4j (Docker)

```powershell
docker compose up -d neo4j
```

Chờ ~15s cho Neo4j nhận kết nối. Kiểm:

```powershell
docker compose ps          # cột STATUS của neo4j phải "healthy"
```

### A2. Nạp dữ liệu luật thật vào graph

```powershell
python -m backend.graph.loader --wipe
```

Sẽ in: nạp 3 văn bản thuế (qlt2019, qlt2025, tncn2025) + entity, rồi diffing.
**Mất ~2-3 phút.** Xong là graph có ~3.600 node.

### A3. Bật API + Dashboard

```powershell
uvicorn backend.api.main:app --reload --port 8000
```

Mở trình duyệt:
- **Dashboard**: http://localhost:8000/
- **Neo4j Browser** (xem graph): http://localhost:7474
  - user `neo4j`, password `lawgic-dev-password`
  - dán query trong [demo/graph_demo_queries.md](demo/graph_demo_queries.md) để xem hình

Kiểm API sống: mở http://localhost:8000/health → `graph_source` phải là `neo4j`.

> Ở chế độ A, tab Hỏi-Đáp và các cảnh báo "hiểu nhầm đang lan" sẽ trống hoặc
> trả mock, vì chưa chạy pipeline dư luận (chế độ B).

---

## Chế độ B — thêm dư luận + Hỏi-Đáp (cần key FPT)

Làm hết chế độ A trước, rồi:

### B1. Thêm key FPT vào `.env`

Mở file `.env` ở gốc repo, thêm dòng (lấy key ở marketplace.fptcloud.com):

```
LLM_API_KEY=sk-...
LLM_BASE_URL=https://mkp-api.fptcloud.com
```

> `.env` hiện đã có NEO4J + LLM_MODEL nhưng **thiếu `LLM_API_KEY`** — chưa thêm
> thì mọi bước gọi LLM (pipeline P3, Q&A) sẽ báo "Missing credentials".

### B2. Chạy pipeline dư luận của P3

```powershell
python scripts/run_pipeline.py --threads 20      # mẫu nhỏ, xem luồng chạy đúng
# hoặc toàn bộ (đắt, ~1446 luồng):
# python scripts/run_pipeline.py --all
```

Bước này: bình luận thật → phân loại → nối vào Điều-Khoản-Điểm → gom "hiểu nhầm
đang lan". Kết quả đổ vào graph, dashboard sẽ hiện cảnh báo thật.

### B3. Xem lại dashboard

Refresh http://localhost:8000/ — giờ tab cảnh báo có dữ liệu thật, tab Hỏi-Đáp
trả lời kèm trích dẫn Điều-Khoản-Điểm.

---

## Dừng / dọn

```powershell
# Dừng API: Ctrl+C ở cửa sổ uvicorn
docker compose down            # dừng Neo4j (giữ dữ liệu)
docker compose down -v         # dừng + XOÁ dữ liệu graph (nạp lại từ đầu)
```

---

## Cách khác: chạy tất cả bằng 1 lệnh Docker

```powershell
docker compose up              # dựng cả neo4j + api trong container
```

Nhưng graph khởi tạo **rỗng** — vẫn phải nạp dữ liệu:

```powershell
docker compose exec api python -m backend.graph.loader --wipe
```

Cách hybrid ở Chế độ A (Neo4j docker + API chạy Python local) dễ debug hơn,
khuyến nghị dùng khi phát triển.

---

## Trục trặc thường gặp

| Triệu chứng | Nguyên nhân | Cách xử |
|---|---|---|
| `Couldn't connect to localhost:7687` | Neo4j chưa chạy | `docker compose up -d neo4j`, chờ ~15s |
| `Missing credentials ... OPENAI_API_KEY` | thiếu `LLM_API_KEY` trong `.env` | thêm key FPT (B1); hoặc chỉ chạy chế độ A |
| `/health` trả `graph_source: mock` | graph rỗng | chạy lại bước A2 |
| `UnicodeEncodeError` (tiếng Việt) | terminal cp1252 | `$env:PYTHONIOENCODING="utf-8"` trước khi chạy |
| Dashboard trống trơn | API chưa bật | bước A3 (uvicorn) |
