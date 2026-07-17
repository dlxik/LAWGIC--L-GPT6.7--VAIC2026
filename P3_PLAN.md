# P3 — Dư luận + Đo lường · Kế hoạch hành động

> Sở hữu: `backend/discourse/`, `eval/`, `prompts/classify_topic.txt`, `prompts/detect_misunderstanding.txt`
> Branch: `hien` · Merge vào `main` ở mốc 8 / 16 / 21.
>
> **Đề tài là THUẾ, không phải giao thông.** Bản plan trước bám `README.md`/`DIVISION.md`
> (Nghị định 168, nồng độ cồn) — sai. Dữ liệu thật là luật thuế. Bản này bám dữ liệu.
>
> `scripts/fetch_social_posts.py` **không còn là việc của P3** — Quân đã làm xong, bàn giao
> ở [`crawl_docs.md`](crawl_docs.md). Đọc file đó trước khi đọc file này.

## Giao nộp cuối

1. **3.321 post đã gắn nhãn** → `data/processed/posts_labeled/`. Post thô đã có sẵn.
2. **Con số accuracy trên gold set** — `python eval/run_eval.py` in ra được, ≥50 claim gắn nhãn tay, accuracy ≥80%.

Thứ 2 quan trọng hơn. BGK chắc chắn hỏi *"làm sao biết phân loại đúng?"*, không có số thì không trả lời được.
Phải chọn giữa "nhãn hết 3.321 post" và "50 claim gold + accuracy" → **chọn accuracy**.

---

## Hiện trạng: cái gì đã có, cái gì chưa

### Quân đã làm hộ (rủi ro #1 của P3 đã biến mất)

| | Số liệu thật |
|---|---|
| Post | **3.321** — mục tiêu `DIVISION.md` là ≥500 → **gấp 6,6×** |
| ├ comment gốc | 1.446 |
| └ reply | 1.875 (56%) |
| **Luồng có tranh luận** | **314** (22% số luồng, nhưng chứa **toàn bộ** 1.875 reply) |
| Luồng chỉ 1 post | 1.132 (78%) |
| Luồng dài nhất | 90 post (~5.400 token) |
| Nguồn | VnExpress, chủ đề `thue-ho-kinh-doanh`, 12 bài |
| Thời gian | 2025-06-04 → **2026-04-10** |
| File | `data/raw/social_posts.json` (2,0 MB), phẳng, mỗi luồng nằm liền nhau |

Đã xác minh: Pydantic `Post` pass 3.321/3.321, `author_hash` = sha256(userid), rò rỉ `@mention`
chở userid thô ở 1.016 reply đã vá. **Đừng crawl lại. Đừng đụng vào file crawler.**

### Contract đã đổi — đọc kỹ, ảnh hưởng trực tiếp tới P3

- **`Post.parent_id`** (mới). `null` = gốc. Kéo theo cạnh `(Post)-[:REPLY_TO]->(Post)` trong graph.
- **`PenaltyType` viết lại quanh chế tài thuế**, đo trên 3 văn bản thật:
  `LATE_PAYMENT_INTEREST` 127 node (nhiều nhất — **là lãi, không phải phạt**), `ENFORCEMENT` 85,
  `CRIMINAL` 10, `FINE` 9, `INVOICE_SUSPENSION` 5, `LICENSE_SUSPENSION`/`LICENSE_REVOCATION` **0**.
- **`Article`/`Clause`/`Point` kế thừa `Temporal`** — hiệu lực ở **mức node**, không phải mức văn bản.
- **`LegalDocument.replaces` / `.amends`** — `qlt2025.replaces = "qlt2019"`.

### Ba văn bản demo (thật, đã parse)

| doc_id | Số hiệu | Hiệu lực | Quan hệ |
|---|---|---|---|
| `qlt2019` | 38/2019/QH14 Luật Quản lý thuế | 2020-07-01 | bị `qlt2025` thay thế |
| `qlt2025` | 108/2025/QH15 Luật Quản lý thuế | **2026-07-01** | `replaces: qlt2019` ← **cặp diffing** |
| `tncn2025` | 109/2025/QH15 Luật Thuế TNCN | **2026-07-01** | — |

### Chưa ai làm (việc của P3)

`backend/discourse/{classifier,linker,misinformation}.py`, `eval/run_eval.py`,
2 file prompt — **tất cả vẫn là stub `NotImplementedError`**, y như lúc khởi tạo.

### Hai thứ đã chết theo đề tài cũ — phải xử lý, không được lờ

| File | Vấn đề |
|---|---|
| `eval/gold_set.jsonl` | Dòng `g001` duy nhất: *"Uong 1 lon bia bi tuoc bang lai vinh vien"* → `nd168-d5-k2-a`. Node **không tồn tại**. Xoá, viết lại từ đầu. |
| `demo/sample_case.md` | Xây quanh case nồng độ cồn + Nghị định 168. **Chết hoàn toàn.** Viết lại quanh case thuế bên dưới. |

---

## Case demo mới (thay cho nồng độ cồn)

**Node neo — có thật, đã kiểm:**

```
[tncn2025-d7-k1]  Cá nhân cư trú có hoạt động sản xuất, kinh doanh có mức doanh thu năm
                  từ 500 triệu đồng trở xuống không phải nộp thuế thu nhập cá nhân.
```

Tin đồn tương ứng, có thật trong dữ liệu crawl: *"Doanh thu 200 triệu là phải đóng thuế rồi"*
→ người dân nhớ **ngưỡng cũ**. Đúng cấu trúc của case nồng độ cồn cũ (dân nhớ quy định cũ),
nên lập luận "vì sao graph ăn RAG vector" giữ nguyên giá trị.

**Việc bắt buộc ở giờ 8:** hỏi Linh xem `SUPERSEDED_BY` giữa `qlt2019` ↔ `qlt2025` có sinh ra
Điểm nào liên quan ngưỡng doanh thu không. Có → dùng làm case chính, mạnh nhất.
Không → case vẫn chạy được bằng `tncn2025-d7-k1` + `Temporal.effective_from`, nhưng **phải biết
trước giờ 16**, đừng để đến lúc dựng demo mới phát hiện.

---

## Phụ thuộc

| Phụ thuộc | Của ai | Né thế nào |
|---|---|---|
| `core/llm.py` — vẫn **stub 47 dòng, 4 `NotImplementedError`**, deadline là giờ 3 | Nguyên (P4) | Chữ ký hàm đã chốt trong docstring → code theo interface, test bằng fake trả JSON cứng. **Không sửa file của Nguyên.** |
| Graph có `Point` thật để `linker.py` truy vấn | Linh (P2) | Giờ đầu dùng thẳng `data/processed/*.json` + BM25 local. Interface không đổi khi chuyển sang graph. |

**Không việc nào của P3 được đứng chờ.** Bị chặn → nhảy sang việc khác trong cùng khung giờ.

---

## Pipeline hành động

### Bước 0 · Dọn rác đề tài cũ (30 phút, làm trước tiên)

- Xoá dòng `g001` trong `eval/gold_set.jsonl`.
- Báo cả team 2 chỗ sai trong `README.md`: *"thảo luận đến 17/7/2026"* → thật là **10/4/2026**;
  toàn bộ mô tả pipeline vẫn đang nói giao thông.
- Đọc `crawl_docs.md` mục 7 — 3 quyết định thiết kế đã có sẵn ở đó, đừng nghĩ lại từ đầu.

### Bước 1 · `prompts/classify_topic.txt` (không chờ ai)

- **Enum topic đóng**, bám 3 văn bản thuế: gợi ý `nguong_doanh_thu`, `thue_tncn`, `ho_kinh_doanh`,
  `hoa_don_chung_tu`, `cuong_che_no_thue`, `khac`. **Không cho LLM tự đặt tên chủ đề** — để tự do
  thì `/trends` vỡ vì 50 biến thể cùng một chủ đề.
- Few-shot lấy từ post **thật** trong `social_posts.json`, bắt buộc có:
  - 1 post cảm xúc → `is_legal_claim=false` (vd *"ế ẩm quá"*)
  - 1 post 2 claim
  - 1 **reply ngắn ăn theo ngữ cảnh gốc** (vd *"Rất chính xác"* — 74 like) → đây là ca khó nhất, xem bước 2

### Bước 2 · `classifier.py` — gộp luồng, không gửi post lẻ

**Đây là quyết định thiết kế quan trọng nhất của P3.** `crawl_docs.md` §7.2 đã chứng minh bằng số:

| | Từng post lẻ | **Cả luồng** |
|---|---|---|
| Call LLM | 3.321 | **1.446** (−56%) |
| Token input | ~1.205k | **~642k** (−47%) |
| Ngữ cảnh | phải tự ghép | **có sẵn** |
| Bắt được đính chính | ❌ | ✅ |

Lý do thật không phải tiền: **322/1.875 reply (17%) đọc riêng là vô nghĩa.**
`classify("Rất chính xác")` → *"không có khẳng định pháp lý"*, và LLM **đúng** — 74 like bốc hơi im lặng.

> JSON lồng không cứu được. Ngữ cảnh mất ở tầng **prompt**, không phải tầng **lưu trữ**.

Cách làm:
- Gom post theo `parent_id` → thread. Render `[GỐC] post_id=... / [TRẢ LỜI] post_id=...` vào 1 prompt.
- Trả `list[Claim]`, mỗi claim mang `post_id`. `schemas.py::Claim` **đã có sẵn `post_id`** → không đụng contract.
- `llm.extract_batch(items, schema)` với **`custom_id` = `thread_id`, KHÔNG phải `post_id`**.
  Lý do: 1 luồng lỗi = mất tới 90 post; retry phải theo đúng đơn vị đã gửi.
- **Kiểm `số post_id trả về == số post gửi đi`**, thiếu → gọi lại luồng đó. Luồng 90 post là chỗ LLM bỏ sót.
- `claim_id` deterministic: `f"{post_id}-c{i}"` — chạy lại phải ra cùng id, không thì eval lệch.
- **Ưu tiên 314 luồng có tranh luận.** Hết giờ thì bỏ 1.132 luồng 1-post, không bỏ ngược lại.

**KHÔNG lọc từ khoá trước khi gọi LLM.** `crawl_docs.md` §7.3 đo rồi: bỏ 24% post để tiết kiệm 10%
token — lỗ. Cả bước phân loại **chưa tới $0,32** qua Batches. Lọc 10% tiết kiệm **3 xu**, mà vứt mất
*"Người tiêu dùng lại là người gánh thêm"* (32 like, claim kinh tế, không có chữ "thuế").
Đừng đặt một regex ngu hơn đứng trước classifier.

**Test không cần P4:** fake `extract_batch` trả 3 kết quả cứng → chạy trên `data/fixtures/mock_posts.json`.
⚠️ Mock posts vẫn là **nội dung giao thông** — dùng để test *đường ống*, không dùng để test *chất lượng nhãn*.

### Bước 3 · Gold set — bắt đầu SỚM, đây là rủi ro #1 còn lại

Gắn nhãn tay 50 claim tốn **2–3 tiếng thật**, không phải 30 phút. `DIVISION.md` xếp việc này vào
giờ 16–20 — **quá muộn**. Crawl đã xong nên P3 có thừa thời gian ở khung đầu: dùng nó vào đây.

- Viết `scripts/show_thread.py` trước (Quân đã gợi ý, §7.4) — in 1 luồng dễ đọc. Không có nó thì
  gắn nhãn bằng cách dò tay trong JSON 2 MB, rất chậm.
- Điền `eval/gold_set.jsonl` đúng format cũ: `{claim_id, text, expected_verdict, expected_citation, note}`.
- `expected_citation` **phải là node_id thật** trong `data/processed/*.json` (vd `tncn2025-d7-k1`).
  Bịa id là gold set vô giá trị.
- **Phân bổ nhãn có chủ đích**, không lấy ngẫu nhiên: ~15 `INACCURATE`, ~15 `PARTIALLY_INACCURATE`,
  ~10 `ACCURATE`, ~10 `UNVERIFIABLE`. 45/50 cùng một nhãn thì accuracy 90% vô nghĩa — BGK hỏi baseline là chết.
- Lấy claim từ **314 luồng có tranh luận**, ưu tiên luồng có đính chính (gốc sai → reply sửa).

### Bước 4 · `linker.py` — phần phải bảo vệ trước BGK

Đây là lý do dự án dùng graph database chứ không phải vector store. Slide sẽ nói về nó.

```
link_claim(claim_text, topic) -> list[Citation]
```

1. **Ứng viên** — full-text index trên `Point.text` (Linh tạo trong `graph/schema.py:INDEXES`) → top-K≈10.
   Linh chưa xong → `rank_bm25` local trên `data/processed/*.json`, interface giữ nguyên.
2. **Mở rộng theo graph** — mỗi Điểm ứng viên: lấy Khoản cha, Điều ông, và **đi `SUPERSEDED_BY` cả hai chiều**.
   Đây là điểm ăn tiền: tin đồn bám ngưỡng **cũ**, nên Điểm khớp text là Điểm cũ, còn Điểm đúng để
   trích dẫn là Điểm mới. Vector store không bắc được cầu này.
3. **LLM chọn** — `llm.extract_cached(...)`, `cached_context` = text các Điểm (ổn định → cache hit ~90%),
   claim đặt **sau** breakpoint. Prefix phải ≥1024 token (Haiku 4.5: 4096) mới cache được.

Ràng buộc cứng:
- `Citation.node_id` **phải khớp node có thật**. LLM bịa → drop. P3 chặn một lớp, Nguyên chặn lớp nữa ở API — hai lớp độc lập.
- Không có ứng viên → trả `[]`, để verdict thành `UNVERIFIABLE`. **Không đoán.**
- `REFERS_TO.method` = `"bm25+graph+llm"` để Linh nạp đúng.

### Bước 5 · `misinformation.py` + `detect_misunderstanding.txt`

```
verdict_for_claim(claim_text, citations) -> {verdict, confidence, explanation, correct_statement}
cluster_misconceptions(claims) -> list[Misconception]
detect_trends() -> list[TrendAlert]
```

- `verdict_for_claim`: prompt đã có quy tắc tốt sẵn. Điền few-shot, **bắt buộc có 1 ví dụ `UNVERIFIABLE`** —
  thiếu thì LLM ép mọi claim vào ACCURATE/INACCURATE, `UNVERIFIABLE` thành nhãn chết, accuracy tụt.
  Ví dụ `PARTIALLY_INACCURATE` nên là ca **đúng nghĩa vụ, sai ngưỡng/mức** — đây là kiểu sai phổ biến nhất
  của dư luận thuế, và cũng là cặp mà model hay lẫn.
- ⚠️ Chú ý `LATE_PAYMENT_INTEREST` **là lãi chậm nộp, không phải tiền phạt**. Claim kiểu *"chậm nộp bị phạt"*
  là `PARTIALLY_INACCURATE`, không phải `ACCURATE`. Đây là bẫy ngôn ngữ của riêng đề tài thuế — ghi vào prompt.
- `cluster_misconceptions`: **đừng dùng LLM clustering.** Embed `claim.text` → cosine ≥0,85 → gom cụm;
  `canonical_text` = claim engagement cao nhất cụm. Rẻ, nhanh, reproducible, giải thích được với BGK.
- `detect_trends`: đọc `settings.trend_min_occurrences` (=5), `trend_window_hours` (=48) từ `config.py`,
  **không hardcode**. `velocity = count / giờ trong window`; `severity` theo velocity × total_engagement
  (chốt ngưỡng LOW/MEDIUM/HIGH, ghi docstring để Nguyên hiển thị đúng).

> **⚠️ Bẫy đã biết: cửa sổ 48h trả RỖNG.** Post mới nhất là **10/4/2026**, demo diễn ngày 17/7/2026 →
> `created_at > now() - 48h` không khớp gì cả → **dashboard trend trống**. Đây là thực tế dữ liệu, không phải bug:
> sóng thảo luận đỉnh lúc luật *được thông qua* (6/2025: 824 post; 11/2025: 863), tắt dần khi luật *có hiệu lực*.
> Cách xử lý (`crawl_docs.md` §7.1): **neo trend vào mốc thời gian truyền vào**, giống `law_as_of(date)` —
> demo nói *"tại 15/12/2025, tin đồn X đang lan mạnh"*, hợp chủ đề time-travel của cả dự án. Đừng nới cửa sổ
> lên 4320h ("trend 180 ngày" nghe không giống trend). **Q3 là việc của Linh + Nguyên, nhưng P3 phải nêu ở mốc giờ 8** —
> để đến giờ 16 mới phát hiện dashboard trống là hỏng mốc tích hợp 2.

### Bước 6 · `eval/run_eval.py` — con số

```
load_gold() -> list[dict]
evaluate() -> {verdict_accuracy, citation_accuracy, per_class_f1, confusion_matrix}
```

- `verdict_accuracy` vs `expected_verdict`.
- `citation_accuracy`: `expected_citation` có nằm trong `[c.node_id for c in citations]`.
  **Báo riêng, không gộp** — hai con số trả lời hai câu hỏi khác nhau, gộp là mất điểm.
- `per_class_f1` + `confusion_matrix`: in ra terminal. Confusion matrix là thứ thuyết phục nhất khi
  BGK nghi ngờ — nó cho thấy P3 biết model sai ở đâu.
- In cả **baseline** (đoán bừa nhãn phổ biến nhất). Không có baseline thì 80% không nói lên gì.

**Accuracy < 80%:** đọc confusion matrix → sửa **prompt/few-shot**, **không sửa gold set**.
Sửa gold cho khớp output là gian lận, BGK nhìn ra ngay. Lỗi hay gặp: `ACCURATE` ↔ `PARTIALLY_INACCURATE`
lẫn nhau → thêm few-shot phân biệt "đúng nghĩa vụ, sai ngưỡng".

### Bước 7 · Viết lại `demo/sample_case.md`

File hiện tại là case nồng độ cồn — **xoá, viết lại** quanh `tncn2025-d7-k1` + số liệu thật của P3:
lần đầu xuất hiện, số lần lặp, tổng tương tác, confidence, định chính nguyên văn.
Nguyên dựng demo quanh file này → trễ là Nguyên kẹt.

### Bước 8 · Chuẩn bị trả lời BGK

- *"Làm sao biết phân loại đúng?"* → accuracy + citation_accuracy + confusion matrix + baseline, trên 50 claim gắn nhãn tay.
- *"Sao không dùng vector search cho nhanh?"* → bước 2 của `linker.py`: dân nhớ ngưỡng cũ, `SUPERSEDED_BY`
  bắc cầu sang Điểm mới. Mở đúng case ngưỡng 500 triệu ra chỉ.
- *"Dữ liệu comment có hợp pháp không?"* → chỉ nội dung công khai, `author_hash` = sha256(userid) không đảo ngược,
  không lưu `full_name`; rò rỉ `@mention` ở 1.016 reply đã tìm ra và vá. (`crawl_docs.md` §5)
- *"Sao chỉ 1 nguồn?"* → VnExpress là nguồn duy nhất còn API comment công khai; Facebook đã đóng.
  3.321 post gấp 6,6× mục tiêu. Thêm nguồn là mở rộng, không phải thiếu sót.

---

## Thứ tự ưu tiên khi trễ (cắt từ dưới lên)

| # | Hạng mục | Cắt được không |
|---|---|---|
| 1 | Gold set 50 claim + `run_eval.py` ra số | **Không.** Mất là mất điểm nặng nhất. |
| 2 | `linker.py` bước mở rộng graph | **Không.** Bỏ là dự án còn RAG thuần. |
| 3 | `verdict_for_claim` + case ngưỡng 500 triệu | **Không.** `sample_case.md` xây quanh nó. |
| 4 | `detect_trends` (neo mốc thời gian) | Không. Đây là output cảnh báo chính. |
| 5 | Gộp luồng ở classifier | Hạ cấp được — chạy post lẻ, mất 17% reply, đắt gấp đôi. Không nên. |
| 6 | Nhãn hết 3.321 post | Hạ được — chỉ nhãn 314 luồng có tranh luận. |
| 7 | `cluster_misconceptions` chuẩn | Hạ được — gom tay 3 cụm cho demo. |
| 8 | `scripts/show_thread.py` | Cắt được, nhưng cắt xong gắn nhãn chậm hơn nhiều. |

## Rủi ro riêng của P3

| Rủi ro | Dấu hiệu sớm | Xử lý |
|---|---|---|
| **Gold set để muộn** | Giờ 12 vẫn <20 dòng | Rủi ro #1 còn lại. Crawl xong rồi → dồn thời gian dư vào đây ngay. |
| Q3 trả rỗng vì cửa sổ 48h | Dashboard trend trắng ở giờ 16 | Nêu với Linh + Nguyên **ở mốc giờ 8**, không phải giờ 16. |
| Nguyên trễ `core/llm.py` quá giờ 3 | Giờ 4 vẫn `NotImplementedError` | Fake → P3 không chặn. Giờ 6 chưa có thì báo cả team: rủi ro toàn dự án. |
| LLM bỏ sót post trong luồng 90 post | Số claim trả về < số post gửi | Kiểm số lượng, gọi lại. Bắt buộc, không phải tuỳ chọn. |
| Batch lỗi giữa chừng | Thiếu luồng | `custom_id` = thread_id → chạy lại phần thiếu, đừng chạy lại cả batch. |
| Accuracy < 80% ở giờ 18 | — | Sửa few-shot, **không sửa gold**. 2h đủ cho 2 vòng lặp. |
| Topic do LLM tự đặt tên | `/trends` ra 50 chủ đề trùng nghĩa | Enum đóng ngay từ bước 1. |
| Lẫn "lãi chậm nộp" với "tiền phạt" | Nhiều `ACCURATE` sai ở claim chậm nộp | Ghi rõ vào prompt verdict. Bẫy riêng của đề tài thuế. |
