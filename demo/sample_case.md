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
| Cụm tổng (toàn giai đoạn) | 6 lần, 98 tương tác |
| **Đợt bùng (cửa sổ 48h quanh 19/11/2025)** | **4 claim** — cảnh báo trend |
| Lần đầu → gần nhất | 09/06/2025 → 19/11/2025 |
| Verdict | **INACCURATE** |

Cảnh báo trend (chạy `--as-of 2025-11-20 --window 48 --min-occ 3`): hệ thống bắt được
**đợt lan 4 claim cùng một hiểu nhầm trong 48 giờ ngày 19/11/2025** (13:03, 15:53,
23:37×2) — không phải đếm cả cụm trải 5 tháng, mà đếm THẬT số claim trong cửa sổ.

*(Số trên từ mẫu 5 luồng demo — 374 post, 91 claim, 23 cụm. Quét toàn bộ 3.321 post
thì cụm này lớn hơn nhiều; ~70 post nhắc trực tiếp ngưỡng thấp.)*

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

Chạy `python eval/run_eval.py` trên 48 claim gắn nhãn tay (`eval/gold_set.jsonl`).
Số dưới là **trung bình 3 lần chạy** (model FPT dao động ±8đ giữa các lần):

| Chỉ số | Giá trị |
|---|---|
| **PHÁT HIỆN TIN SAI** — bắt đúng claim INACCURATE (nhị phân) | **86,8%** (P=0,75 R=0,86) |
| Citation accuracy (trỏ đúng điều luật) | **76,2%** |
| Verdict 4 nhãn (ACCURATE/PARTIAL/INACCURATE/UNVERIFIABLE) | ~60% (±14%) |
| Baseline (đoán bừa nhãn phổ biến nhất) | 29,2% |

**Metric chính là "phát hiện tin sai" 86,8%** — đúng câu hỏi của một hệ chống
misinformation: *hệ có gắn cờ đúng những claim sai không?* (recall 0,86). Verdict
4-nhãn chỉ ~60% vì bị chặn bởi **ranh giới ACCURATE↔PARTIALLY mơ hồ bản chất** — sai
số nhỏ tới mức nào thì tụt hạng, người gán nhãn cũng cãi nhau; đây là trần nhãn-người,
không phải bug. ~25% claim nằm trên ranh giới đó.

Cấu hình: FPT AI `gpt-oss-120b`; truy hồi điều luật LAI — TF-IDF từ vựng + neo cả Điều 7
làm ứng viên (candidate recall 100%), LLM chọn khoản đúng nhờ bản đồ Điều 7 trong prompt.
Graph `SUPERSEDED_BY` là điểm khác biệt cho nhóm claim **bám luật CŨ** (thuế khoán
`qlt2019-d51`): bắc cầu sang luật mới để định chính đúng chỗ đã đổi. Trên bộ gold này
graph ~ngang TF-IDF về accuracy tổng (34/35 đáp án nằm ở luật MỚI, không có tiền nhiệm
để bắc cầu) — giá trị graph là ĐỊNH TÍNH ("dân đang nhớ luật cũ") + cho nhóm claim luật cũ,
không phải cú nhảy accuracy. (Embedding tiếng Việt FPT đo yếu cho domain → dùng TF-IDF.)
