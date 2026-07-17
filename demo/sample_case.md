# Case mẫu: ngưỡng thuế hộ kinh doanh

> Nguồn: 3 văn bản thuế trong `data/processed/legal_docs_structured/` +
> 3.321 bình luận thật trong `data/raw/social_posts.json` (VnExpress, 6/2025–4/2026).
> Số liệu trend dưới đây lấy từ `scripts/run_pipeline.py` chạy trên cụm luồng tranh luận;
> con số eval lấy từ `eval/run_eval.py` trên 48 claim gold gắn tay.

## Văn bản

**Luật hiện hành (hiệu lực 01/07/2026):**
Luật Thuế thu nhập cá nhân 109/2025/QH15.

- **`tncn2025-d7-k1`** — *"Cá nhân cư trú có hoạt động sản xuất, kinh doanh có mức
  doanh thu năm từ 500 triệu đồng trở xuống không phải nộp thuế thu nhập cá nhân."*
  → Ngưỡng miễn tính theo **DOANH THU**, và là **500 triệu/năm**.
- **`tncn2025-d7-k2`** — trên ngưỡng thì mặc định tính thuế trên **thu nhập**
  (doanh thu − chi phí) × thuế suất 15% (doanh thu đến 3 tỷ).
- **`tncn2025-d7-k3-a`** — hoặc chọn tính trên **phần doanh thu vượt** 500 triệu,
  thuế suất 0,5%–5% tùy ngành.

**Luật cũ (đã bị thay thế):**
Luật Quản lý thuế 38/2019/QH14, **`qlt2019-d51`** — *phương pháp khoán thuế* cho
hộ kinh doanh. Luật mới (108/2025/QH15) **đã bỏ hẳn phương pháp khoán** — cụm từ
"phương pháp khoán" chỉ còn xuất hiện trong văn bản 2019, 0 lần trong văn bản 2025.

## Tin đồn đang lan truyền

Cụm hiểu nhầm lớn nhất hệ thống gom được (dạng chuẩn hoá theo bình luận nhiều
tương tác nhất trong cụm):

> **"Hộ kinh doanh có thu nhập ~100–120 triệu đồng/năm là đã phải nộp thuế TNCN"**

| Chỉ số | Giá trị |
|---|---|
| Số lần lặp (cụm) | 6 |
| Tổng tương tác | 98 |
| Lần đầu xuất hiện | 09/06/2025 |
| Gần nhất | 19/11/2025 |
| Verdict | **INACCURATE** |

*(Số trên là từ mẫu 5 luồng chạy demo — 374 post, 91 claim, 23 cụm. Quét toàn bộ
3.321 post thì cụm này lớn hơn nhiều; ~70 post nhắc trực tiếp ngưỡng thấp.)*

Bản chất hiểu nhầm: người dân tưởng **ngưỡng chịu thuế thấp** (100–200 triệu) và
tính **trên doanh thu**, trong khi luật mới miễn tới **500 triệu doanh thu/năm**.

## Hệ thống đối chiếu

- Claim → `REFERS_TO` → **`tncn2025-d7-k1`** (ngưỡng miễn 500 triệu)
- Verdict: **INACCURATE**
- Định chính: *"Theo Điều 7 Khoản 1 Luật 109/2025/QH15, cá nhân kinh doanh có doanh
  thu năm từ 500 triệu đồng trở xuống KHÔNG phải nộp thuế TNCN. Thu nhập 100–120
  triệu tương ứng doanh thu thấp hơn nhiều ngưỡng này → được miễn hoàn toàn. Chỉ khi
  doanh thu vượt 500 triệu mới bắt đầu chịu thuế, và chỉ tính trên phần vượt (Điểm a
  Khoản 3) hoặc trên thu nhập sau khi trừ chi phí (Khoản 2)."*

## Tại sao graph ăn RAG vector ở case này

Tin đồn bám **cách hiểu của luật CŨ**: hộ nhỏ đóng thuế khoán theo doanh thu, ngưỡng
thấp. Điểm khớp text nhất với tin đồn là `qlt2019-d51` (thuế khoán — luật cũ), nhưng
căn cứ ĐÚNG để định chính là `tncn2025-d7-k1` (ngưỡng 500 triệu — luật mới).

Nhờ quan hệ giữa hai văn bản (`REPLACES` + `SUPERSEDED_BY` ở mức Điểm), hệ thống chỉ ra:

1. Người dân đang **nhớ quy định cũ**, không phải bịa hoàn toàn.
2. Điểm khác biệt cụ thể: bỏ thuế khoán, nâng ngưỡng lên 500 triệu, đổi cách tính.
3. Định chính tập trung vào **chỗ đã đổi**, không bắt đọc lại cả luật.

Vector store thuần trả về `qlt2019-d51` (giống text tin đồn nhất) và **không biết nó
đã hết hiệu lực** — sẽ định chính bằng chính quy định cũ mà dân đang nhớ nhầm.

## Con số đo được (trả lời "làm sao biết phân loại đúng?")

Chạy `python eval/run_eval.py` trên 48 claim gắn nhãn tay (`eval/gold_set.jsonl`):

| Chỉ số | Giá trị |
|---|---|
| Verdict accuracy (toàn bộ, 4 nhãn) | **58,3%** (±14%) |
| Trong phạm vi Điều 7 (ngưỡng + cách tính), 3 nhãn | **64,7%** |
| Trong phạm vi, gộp 2 nhãn (khớp luật / hiểu sai) | **82,4%** |
| Baseline (đoán bừa nhãn phổ biến nhất) | 29,2% |
| Độ phủ (thảo luận về ngưỡng/cách tính) | ~40% |

Con số vượt xa baseline. Phần khó nhất (`PARTIALLY_INACCURATE` — đúng cấu trúc, sai
con số/điều kiện) là ranh giới mờ mà cả người cũng cãi nhau. Mô hình dùng: FPT AI
`gpt-oss-120b`, truy hồi điều luật lai TF-IDF + embedding tiếng Việt.
