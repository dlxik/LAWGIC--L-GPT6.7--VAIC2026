# Kịch bản Demo LAWGIC — 4 phút (Vòng 3 · Demo Day)

> Mọi câu hỏi/ngày trong script đã **test thật** trên hệ thống. Làm đúng là ra đúng.

---

## 0. CHUẨN BỊ TRƯỚC KHI QUAY (KHÔNG quay phần này)

1. **Bật server** (đảm bảo chạy):
   ```bash
   # health phải trả graph_source: neo4j
   curl http://localhost:8000/health
   ```
2. **Mở sẵn 2 tab trình duyệt:**
   - Tab 1 — **Web app:** `http://localhost:8000` → đang ở tab **"Cảnh báo hiểu nhầm"**, bấm **Ctrl+Shift+R** (xoá cache, nạp bản mới nhất).
   - Tab 2 — **Neo4j Browser:** `http://localhost:7474`
     - Ô **Connect URL:** `bolt://localhost:7687`
     - **Username:** `neo4j`
     - **Password:** `lawgic-dev-password`
     - Bấm **Connect**. Dán sẵn (CHƯA Enter) câu Cypher ở mục 1 dưới.
3. **Phóng to chữ** trình duyệt (Ctrl +) cho dễ nhìn khi quay.
4. Đóng hết tab/thông báo thừa. Chế độ **Khách** là đủ (KHÔNG cần đăng nhập).

---

## 1. THÔNG TIN TRUY CẬP (copy sẵn ra giấy nhớ)

| Thứ | Giá trị |
|---|---|
| Web app | `http://localhost:8000` |
| Neo4j Browser | `http://localhost:7474` · bolt: `bolt://localhost:7687` |
| Neo4j user / pass | `neo4j` / `lawgic-dev-password` |

**Câu hỏi Hỏi–Đáp (gõ TAY hoặc dùng chip):**
- Time-travel A: `Hội đồng tư vấn thuế xã phường còn hoạt động từ 1/7/2026 không?`
- Time-travel B: `Hội đồng tư vấn thuế xã phường còn hoạt động từ 1/6/2026 không?`
- Chống ảo giác: chip **"câu hỏi không liên quan"** (tiền ảo)
- Câu thường: chip **"ngưỡng miễn"**

**Cypher dán vào Neo4j Browser (hiện graph cũ→mới):**
```cypher
MATCH path = (old:Clause)-[:SUPERSEDED_BY]->(new:Clause)
WHERE old.clause_id STARTS WITH 'qlt2019-d10'
RETURN path
```

---

## 2. KỊCH BẢN TỪNG GIÂY (~3:55)

| Thời gian | THAO TÁC (làm gì) | LỜI NÓI (đọc) |
|---|---|---|
| **0:00–0:18** | Màn hình đang ở tab **Cảnh báo hiểu nhầm** (danh sách cảnh báo). | "Từ 1/7/2026, luật thuế hộ kinh doanh thay đổi lớn. Trong giai đoạn giao thời, người dân hiểu sai và tin đồn lan nhanh trên mạng xã hội. LAWGIC nối **luật** với **dư luận** trên một đồ thị tri thức để phát hiện và định chính." |
| **0:18–0:55** | **Nhấn** cảnh báo mức **HIGH** đầu tiên *("Thu nhập 120 triệu/năm không phải nộp thuế")*. Chỉ vào khối đỏ↔xanh. | "Hệ thống tự phát hiện hiểu nhầm này — 23 lần lặp, hơn 2.000 tương tác. Bên trái là điều dân đang tin **SAI**; bên phải là **ĐÚNG theo luật**, kèm trích dẫn Điều 7." |
| **0:55–1:15** | Cuộn xuống mục **"Điều luật bị vi phạm"** rồi **"Bằng chứng lan truyền"**. | "Không phải nói suông: đây là các điều luật bị vi phạm — có trích dẫn đầy đủ — và các bài đăng thật làm bằng chứng. Mỗi cảnh báo đều **truy được về luật gốc**." |
| **1:15–1:25** | Chuyển sang tab **Hỏi – Đáp**. | "Đây là phần lõi và là **khác biệt lớn nhất** của chúng tôi." |
| **1:25–1:55** | Gõ (hoặc dán) câu **A**: *"Hội đồng tư vấn thuế xã phường còn hoạt động từ 1/7/2026 không?"* → **Hỏi**. Đợi ra kết quả. | "Hỏi: hội đồng tư vấn thuế xã phường còn hoạt động từ 1/7/2026 không? Trả lời: **KHÔNG — không còn kể từ 1/7/2026**, và trích chính Điều 28 Luật cũ 2019, dán nhãn **đã hết hiệu lực**." |
| **1:55–2:25** | Sửa trong câu hỏi **1/7/2026 → 1/6/2026** (câu **B**) → **Hỏi** lại. | "Giờ tôi đổi đúng **một con số** — hỏi tính đến **1/6/2026**. Cùng câu hỏi, hệ thống trả lời **CÓ — vẫn còn hoạt động**, vì lúc đó luật cũ chưa hết hiệu lực. **RAG vector không làm được điều này** — nó chỉ so độ giống chữ, không hiểu hiệu lực theo thời gian." |
| **2:25–2:45** | **Nhấn một node** trong đồ thị quan hệ điều luật bên phải → hiện nội dung; nhấn **"Mở rộng"**. | "Mỗi trích dẫn nằm trong **đồ thị Điều–Khoản–Điểm**. Nhấn vào là đọc luật gốc, mở rộng để xem quan hệ — đây là graph thật, không phải kho vector." |
| **2:45–3:05** | Nhấn chip **"câu hỏi không liên quan"** (đầu tư tiền ảo) → **Hỏi**. | "Và khi ngoài phạm vi — ví dụ đầu tư tiền ảo — hệ thống **TỪ CHỐI**: 'không đủ căn cứ'. Trong pháp lý, **thà từ chối còn hơn bịa**. Mọi trích dẫn đều được đối chiếu với node có thật, ID bịa bị loại." |
| **3:05–3:30** | Sang **tab 2 (Neo4j Browser)** đã dán sẵn Cypher → **Enter**. Graph nhỏ cũ→mới hiện ra. | "Đây là cơ chế đứng sau: cạnh **SUPERSEDED_BY** nối điều luật **cũ 2019 → mới 2025**. Chính cạnh này cho phép 'du hành thời gian' vừa rồi. Đây là lý do bài toán **cần cơ sở dữ liệu đồ thị**." |
| **3:30–3:55** | Quay lại tab web → tab **Tra cứu** → gõ *"hóa đơn điện tử"* → **Tìm** → nhấn 1 kết quả (bung nguyên Điều) → tick **"Chỉ luật đang hiệu lực"**. | "Cuối cùng, cho dân chuyên môn: tra cứu và **đọc nguyên Điều luật gốc** theo đúng thời điểm hiệu lực, không qua AI. LAWGIC — trợ lý pháp lý **đúng thời điểm, có căn cứ, không bịa**. Xin cảm ơn." |

---

## 3. PHÒNG HỜ & Q&A (2 phút hỏi đáp sau pitch)

**Nếu bị hỏi "khác gì ChatGPT/RAG?"**
→ "RAG vector trả điều luật giống nhất về chữ — thường là luật đã hết hiệu lực. Chúng tôi có **hiệu lực ở mức node + cạnh SUPERSEDED_BY**, nên trả đúng luật theo **thời điểm**. Vừa rồi cô/chú thấy: cùng câu hỏi, đổi ngày → đổi đáp án."

**Nếu bị hỏi "độ chính xác / có bịa không?"**
→ "Mỗi câu trả lời kèm trích dẫn được **validate với node thật**; không đủ căn cứ thì **từ chối**. Chúng tôi đo bằng **gold gán tay** và có cả bảng exact-match lẫn semantic, tự nêu hạn chế."

**Nếu bị hỏi "kinh doanh thế nào?"**
→ "B2B cho **công ty dịch vụ kế toán / đại lý thuế** phục vụ hộ kinh doanh — giảm giờ tra cứu, giảm rủi ro trích nhầm luật cũ. Lộ trình pilot 3 giai đoạn: design-partner → trả phí → mở rộng." (xem `docs/PILOT_ROADMAP.md`)

**Nếu một câu hỏi lỡ trả sai/lag khi quay:** đừng sửa live — **quay lại beat đó**. Ưu tiên giữ **beat time-travel (1:25–2:25)** và **beat cảnh báo (0:18–1:15)** thật mượt; đó là toàn bộ khác biệt.

**Nếu hết giờ:** cắt beat Tra cứu (3:30) trước, rồi beat Neo4j Browser. **Không bao giờ cắt** time-travel.
