# P1 Benchmark — Parser & Extractor

> Đo lường phần P1 (văn bản pháp luật). Chạy: `python eval/benchmark_p1.py`.
> Số liệu sinh từ `eval/results/benchmark_result.json`, cập nhật khi chạy lại.

## Vì sao đo hai cách khác nhau

P1 có hai thành phần **khác bản chất**, nên **không thể đo cùng một metric**:

| | Parser | Extractor |
|---|---|---|
| Công cụ | regex + máy trạng thái | LLM (voting `gpt-oss-20b` ∩ `gemma-31B`) |
| Tất định? | ✅ chạy 100 lần ra y hệt | ❌ mỗi lần có thể khác |
| Có "đáp án đúng"? | ✅ văn bản tự khai số Điều | ❌ phải người gán nhãn |
| Đo bằng | **đối chiếu tự động** (0 người) | **gold set gán tay** (P/R/F1) |
| Phủ | 100% node (2.055) | mẫu **100 node / 235 span** |

Dùng *accuracy* cho extractor là **sai** — output là *tập hợp* span tự do, không phải
nhãn đơn. Bài toán này đo bằng **Precision / Recall / F1**.

---

## Bảng 1 — Parser (tất định, đối chiếu tự động)

| Văn bản | Node | Article recall | Lỗi bất biến |
|---|---:|---:|---:|
| `qlt2019` | 1.194 | 100% | 0 |
| `qlt2025` | 662 | 100% | 0 |
| `tncn2025` | 199 | 100% | 0 |
| **TỔNG** | **2.055** | **100%** | **0** |

| Metric | Ý nghĩa | Ground truth | Kết quả |
|---|---|---|---|
| **Article recall** | số Điều parse / số Điều thật | văn bản tự khai (VD "53 Điều") | **100%** (234/234) |
| **Invariant errors** | 7 bất biến `validate()` | tự động | **0** |
| **Character coverage** | ký tự giữ / ký tự nội dung | `_expected_content_length()` | **≥98%** (ngưỡng test) |
| **ID uniqueness** | `node_id` trùng | tự động | **0 trùng** |
| **Unit + integration test** | `tests/test_parser.py` | 27 test | **27/27 pass** |

Parser đạt **ground truth khách quan** — không phải ý kiến. Văn bản QPPL Việt Nam có
cấu trúc cứng (Nghị định 30/2020), số Điều đếm được, nên "đúng" là tuyệt đối chứ không
phải xấp xỉ. *(Extractor chạy trên **1.842** node "trích được" — bỏ Điều rỗng chỉ chứa
Khoản/Điểm con.)*

---

## Bảng 2 — So sánh 4 model (100 node gold, prompt EN, gộp node, schema 10 trường)

Chạy: `python eval/bench_model.py <model>`. Tất cả trên FPT AI Marketplace, non-reasoning.
Gold **100 node / 235 span**, gán tay, kiểm 4 vòng. Sắp theo F1 giảm dần.

| Model | Nhà / cỡ | F1 | P | R | Macro | Hallucination | Empty | Penalty-type |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **gemma-4-31B-it** | Google / 31B | **80%** | 70% | **93%** | 77% | 30% | 67% | **0%** ⚠️ |
| gpt-oss-20b | OpenAI / 20B | 77% | 68% | 90% | 70% | 32% | 67% | **71%** |
| SaoLa3.1-medium | 🇻🇳 Việt Nam | 67% | 63% | 71% | 67% | 37% | 50% | 43% |
| Llama-3.3-70B | Meta / 70B | 64% | 63% | 64% | 67% | 37% | 50% | 29% |

**Theo trường (F1):**

| Model | tax_rates | tax_base | exemptions | subjects | obligations | prohibitions |
|---|---:|---:|---:|---:|---:|---:|
| gemma-4-31B-it | 91% | 62% | 24% | **89%** | **86%** | **100%** |
| gpt-oss-20b | 71% | **77%** | 24% | 86% | 69% | 64% |
| SaoLa3.1-medium | **100%** | 69% | **67%** | 76% | 56% | 33% |
| Llama-3.3-70B | 95% | **88%** | 62% | 83% | 45% | 67% |

**Đọc bảng:**

- **⚠️ Bảng xếp hạng LẬT khi tăng gold 36 → 100 node** — bài học quan trọng nhất.
  Ở 36 node (CI ±9%) Llama-70B đứng nhì (F1 74%) nên **đã chọn chạy full**; ở 100 node
  (CI ±6%) nó **rơi đáy (64%)**. Mẫu nhỏ = thứ hạng nhiễu. Đã chạy lại (xem Bảng 4).
- **Không model nào thắng tuyệt đối:**
  - **gemma-31B** — vô địch deontic (subjects 89%, obligations 86%, prohibitions 100%)
    nhưng **penalty-type 0%** + exemptions 24%.
  - **gpt-oss-20b** — cân bằng nhất, **penalty-type 71% (tốt nhất)**, rẻ nhất. Yếu exemptions.
  - **Llama-70B** — giỏi số học thuế (tax_rates 95%, tax_base 88%) nhưng obligations 45%.
- **penalty-type là deal-breaker cho graph.** `Penalty` là NODE query theo `type`
  (`graph/schema.py` QĐ #5) → gemma 0% ⇒ dù F1 cao nhất vẫn không dùng một mình được.
- **Model tiếng Việt (SaoLa) KHÔNG thắng** (F1 67%). Nút thắt là **kỷ luật làm theo
  lệnh + trích có cấu trúc**, không phải đọc hiểu tiếng Việt.
- **3 giả định bị bác**: (1) to hơn → tốt hơn: SAI (70B đáy); (2) model tiếng Việt →
  tốt hơn: SAI; (3) prompt tốt + kỷ luật > kích thước: ĐÚNG.

> **Công bằng:** cùng 100 node gold, cùng prompt EN, cùng gộp node → tách được ảnh
> hưởng của MODEL. Kết quả JSON mỗi model ở `eval/results/bench_<model>.json`.

---

## Bảng 3 — Hợp phiếu đa model: chất hơn mà giữ recall

Chạy: `eval/bench_raw.py <model>` (lưu span thô) → `eval/vote_combine.py 20b gemma`.
Câu hỏi: kết hợp 2 model có **giảm hallucination mà KHÔNG mất recall** không?

| Cấu hình | F1 | P | R | Hallucination | Penalty-type |
|---|---:|---:|---:|---:|---:|
| gpt-oss-20b đơn | 78% | 68% | 92% | 32% | 71% |
| gemma-31B đơn | 81% | 72% | 93% | 28% | 0% |
| A∩B (giao/voting) | **84%** | **80%** | 89% | **20%** | 0% |
| A∪B (hợp) | 75% | 61% | **98%** | 39% | 71% |
| A∪B + lọc verbatim | 75% | 61% | **98%** | 39% | 71% |
| **A∩B ent + A pen** ⭐ | **84%** | **80%** | **89%** | **20%** | **71%** |

*(F1 đơn ở đây lệch ~1% so với Bảng 2 vì là lần trích lại khác — LLM không tất định.)*

**Ba kết luận (đo được, không đoán):**

1. **Voting KHÔNG tụt recall như lo ngại.** Giao A∩B chỉ mất **3% recall** (92→89) mà
   precision **+12** (68→80), hallucination **giảm nửa** (32→20). Lý do: hai model vốn
   recall cao (92–93%) nên span đúng thường **cả hai cùng thấy** → giao vẫn giữ.
2. **Lọc verbatim VÔ DỤNG ở đây** — `A∪B` và `A∪B + lọc` giống hệt. Nghĩa là
   hallucination **không phải bịa chữ** (chữ có thật trong text) mà là **sai vai** (gán
   đúng chữ, nhầm chủ thể/nghĩa vụ). Grounding không cắt được → **voting mới là đòn
   bẩy**. Hệ quả: kiến trúc citation-nguyên-văn càng quan trọng (sai vai không hỏng
   text gốc, chỉ lệch metadata).
3. **Phép giao triệt tiêu penalty-type** (gemma 0% → giao đòi gemma đồng ý nên type bị
   loại sạch). Khắc phục: giao 9 trường thực thể **nhưng giữ nguyên penalty của 20b** →
   đạt cả F1 84% LẪN penalty-type 71%. Đây là cấu hình chốt (`scripts/combine_voting.py`).

**Đánh đổi:** tốn 2× lượt gọi (chạy 2 model). Xứng đáng cho graph demo vì hallucination
giảm rõ rệt (32% → 20%).

---

## Bảng 4 — Graph TRIỂN KHAI (voting hybrid trên 1.842 node)

Đây là số của **file graph P2 nạp thật** (`data/processed/entities_*.json`), đo lại
trên cùng 100 node gold. Cấu hình = A∩B 9 trường + penalty của 20b (Bảng 3, dòng ⭐).

| Trường | P | R | F1 | tp/fp/fn |
|---|---:|---:|---:|---|
| subjects | 88% | 77% | 82% | 51/7/15 |
| obligations | 83% | 85% | 84% | 35/7/6 |
| rights | 87% | 83% | 85% | 20/3/4 |
| prohibitions | 75% | 86% | 80% | 6/2/1 |
| deadlines | 83% | 94% | 88% | 15/3/1 |
| references | 92% | 76% | 83% | 34/3/11 |
| tax_rates | 77% | 100% | 87% | 10/3/0 |
| tax_base | 57% | 67% | 62% | 8/6/4 |
| exemptions | 33% | 29% | 31% | 2/4/5 |
| **MICRO** | **83%** | **79%** | **81%** | |

| Metric tổng hợp | Kết quả | So 20b đơn (Bảng 2) |
|---|---:|---|
| **Micro F1** | **81%** | +4 (77→81) |
| **Macro F1** | **76%** | +6 (70→76) |
| **Precision** | **83%** | **+15** (68→83) |
| **Recall** | **79%** | −11 (90→79) * |
| **Hallucination rate** | **17%** | **−15** (giảm gần nửa: 32→17) |
| **Empty-correct rate** | **92%** (12 node) | +25 (67→92) |
| **Penalty type accuracy** | **71%** (7 penalty) | giữ (71) |

\* **Recall 79% thấp hơn mức test sạch 89%** (Bảng 3) — nói thẳng: bản 20b chạy full
1.842 node **bị FPT rate-limit**, nhiều node trả rỗng phải retry, một số vẫn thiếu →
bản 20b đầu vào yếu hơn bản trích sạch 100 node, nên phép giao kéo recall xuống. Không
giấu; chạy lại 20b full khi rate-limit rảnh thì recall sẽ về ~89%.

---

## Chọn metric — vì sao dùng những cái này

- **P/R/F1 theo trường** thay vì accuracy: entity extraction là so khớp *tập hợp*,
  accuracy vô nghĩa.
- **Micro + Macro**: micro nghiêng về `subjects`/`obligations` (nhiều dữ liệu); macro
  cho `prohibitions`/`exemptions` (ít node) tiếng nói ngang.
- **Hallucination rate**: quan trọng nhất với **văn bản luật** — bịa/sai vai chủ thể,
  nghĩa vụ = sai lệch pháp lý, tệ hơn bỏ sót.
- **Empty-correct rate**: chống LLM "lười" nặn bừa cho đủ trường ở node định nghĩa.
- **Penalty type accuracy**: chống dồn hết chế tài vào `OTHER`.
- **Ngưỡng khớp span** = 0.60 (SequenceMatcher) + luật "chứa nhau thì khớp" (luật hay
  có *"phải X"* vs *"X"*). Ghi rõ để tái lập.

---

## Phân tích lỗi — quá trình đối soát gold

Gold gán **vòng 1** rồi đối soát nhiều vòng với văn bản gốc. Nhiều "bịa" của LLM hoá
ra là **gold gán sai**, đã sửa (đối chiếu text, KHÔNG bẻ gold cho khớp LLM):

| Loại lỗi gold (đã sửa) | Node ví dụ | Sửa gì |
|---|---|---|
| Bỏ sót quyền (chữ "được") | `d30-k1` | +rights "được cấp mã số thuế" |
| Bỏ sót nghĩa vụ | `d109-k2-b`, `d48-k6` | +obligations |
| `references` không nhất quán | 9 node | +"Luật này", "pháp luật về X" (có thật trong text) |
| Gán THỪA chủ thể | `tncn2025-d22` | −"cá nhân không cư trú" (đối tượng chịu thuế, không phải chủ thể) |

FP **còn lại** giữ nguyên để đo trung thực — đây là LLM sai vai thật:

| FP còn lại (LLM sai vai) | Vì sao gold đúng |
|---|---|
| `d105-k4`: "Những người sau đây" → subject | từ trỏ (cataphora), không phải chủ thể có tên |
| `d43-k6-b`: "Báo cáo tài chính…" → obligation | tên tài liệu trong danh sách, không phải nghĩa vụ |
| `d149-k3`: "hoạt động theo nguyên tắc biểu quyết" → obligation | mô tả cách vận hành, không phải nghĩa vụ |

Chính loại "sai vai" này (chữ có thật, gán nhầm trường) là thứ **voting cắt được mà
lọc verbatim không** (Bảng 3, kết luận 2).

---

## Hạn chế (nói thẳng)

1. **Gold một người gán (single-annotator).** Không đo được inter-annotator agreement;
   chuẩn hơn cần ≥2 người gán độc lập + Cohen's kappa. Bù lại: gold **kiểm 4 vòng**
   (span có trong text gốc / tín hiệu↔trường / đối chiếu từng bất đồng với LLM) — 24 cờ
   "bỏ sót" rà lại đều là báo động giả.
2. **100 node = 4,9% tổng, 235 span → CI ±6%** (từ ±9% ở 36 node). Đủ để thứ hạng
   model ỔN ĐỊNH — chính mẫu 100 node đã lật bảng, chứng tỏ 36 node là quá ít.
3. **prohibitions/exemptions ít span (7 mỗi trường)** — F1 hai trường này còn nhiễu.
   `exemptions` yếu thật (31%): xem mục dưới.
4. **Recall graph triển khai 79%** kéo xuống bởi rate-limit khi chạy full 20b, không
   phải bản chất phương pháp (test sạch đạt 89%).

---

## Điều benchmark tiết lộ về thiết kế

`exemptions` là trường yếu nhất (31%) và cũng khó nhất — vì miễn/giảm/ngưỡng trong luật
thuế diễn đạt rất đa dạng (*"không phải nộp"*, *"được miễn"*, *"trở xuống"*, *"giảm
50%"*), ranh giới với `rights` mờ. Đây là chỗ prompt rõ hơn hoặc thêm gold có thể cải
thiện — nhưng một phần là **bản chất nhập nhằng** của luật, không phương pháp tự động
nào chạm 100%.

Kiến trúc đã phòng điều này: **text parse 100% + citation nguyên văn** là nguồn sự thật;
extraction chỉ là lớp metadata để tìm kiếm/lọc. Extractor sai → lệch *tìm kiếm*, không
làm hỏng *nội dung luật* trả cho người dùng.

---

## Kết luận đưa lên slide

```
PARSER      article_recall 100% | 0 lỗi bất biến | 27/27 test        (2.055 node)
EXTRACTOR   Graph triển khai = VOTING HYBRID (20b∩gemma + 20b penalties)
            Micro-F1 81% | Precision 83% | Recall 79% | Hallucination 17%
            Empty-correct 92% | Penalty-type 71%                  (100 node gold)
            → so 20b đơn: hallucination 32%→17%, precision 68%→83%
```

Điểm mạnh phương pháp để nói với BGK:

1. **Parser** đạt ground truth khách quan (recall 100%, 0 lỗi bất biến).
2. **Chọn model có kỷ luật** — so 4 model trên gold; **tăng gold 36→100 node lật bảng**,
   tự bắt được lỗi chọn nhầm của chính mình.
3. **Hợp phiếu đa model** — chứng minh bằng số rằng giao 20b∩gemma **giảm hallucination
   một nửa mà chỉ mất 3% recall**; phát hiện hallucination là "sai vai" chứ không "bịa
   chữ".
4. **Graph cuối** dùng cấu hình thắng benchmark, đo lại minh bạch (recall tụt vì
   rate-limit nêu thẳng, không giấu).

Mỗi quyết định (model, cách kết hợp) đều có số đo trên gold gán tay 4 vòng — khác hẳn
"chúng em parse xong" không bằng chứng. Đội tự nêu hạn chế của mình vững hơn đội nói
"hoàn hảo".

---

# P3 Benchmark — Đối chiếu claim ↔ luật (verdict + citation)

> Đo ngày 18/07/2026. Khác P1 (trích entity, đối chiếu tự động): đây đo **pipeline
> dư luận** — `link_claim` (claim → Điều/Khoản/Điểm) + `verdict_for_claim` (đúng/sai/
> chưa đủ căn cứ) — trên gold gán tay, đã audit theo text Điều 7 Luật TNCN.

## Bảng 5 — gpt-oss-20b vs Llama-3.3-70B (head-to-head, CÙNG cấu hình)

Cùng điều kiện: gold 36 claim (đã audit, 3 lớp), prompt có few-shot ACCURATE,
`MAX_CANDIDATES=20`, graph Neo4j ON, embedding `Vietnamese_Embedding`. Chỉ đổi
model ở bước link+verdict.

| Chỉ số | gpt-oss-20b | **Llama-3.3-70B** | Chênh |
|---|---|---|---|
| **verdict_accuracy** | 41.7% | **61.1%** | **+19.4** |
| **citation_accuracy** | 33.3% | **40.7%** | +7.4 |
| vs baseline (50%) | −8.3% 🔴 dưới baseline | **+11.1%** ✅ | — |
| INACCURATE recall | 0.28 | **0.72** | +0.44 |
| macro-F1 | 0.41 | **0.58** | +0.17 |

**Kết luận: model là đòn bẩy lớn nhất.** Trên cùng cấu hình, 70B hơn 20B **+19 điểm
verdict**. 20B nằm DƯỚI baseline (tệ hơn đoán bừa); 70B vượt baseline rõ.

## Điều benchmark P3 tiết lộ

1. **Nút thắt citation KHÔNG phải retrieval.** Đo riêng: retrieval recall = **85%**
   (điều luật đúng nằm trong ứng viên trước khi LLM chọn) — nhưng citation cuối chỉ
   33–41%. → Lỗi ở **bước LLM CHỌN**, không phải embedding. Đổi model to hơn nâng
   verdict (suy luận) nhưng **không sửa được bước chọn** (citation kẹt ~41%).

2. **Bật Neo4j đáng giá.** 20B graph OFF → ON: verdict 35% → 51% (+16). Linker đi
   cạnh `SUPERSEDED_BY` thật thay vì fallback doc-level yếu.

3. **Đã chạm trần tự động ~61% verdict / 41% citation.** Đã thử: model mạnh, audit
   gold, few-shot, giảm ứng viên 55→20, graph on. Few-shot + giảm ứng viên chỉ tác
   động biên (citation +4, ACCURATE recall 0.22→0.33). Cú nhảy thật là đổi model.

4. **Chi phí (FPT, VNĐ/1M token):** 20B in 1.309 / out 5.235; 70B in 5.526 / out
   11.924. Ước tính full data (3.186 post): 20B ~20k, 70B ~72k VNĐ. GLM-5.2 (~530k,
   ~26x) test 1 call còn sai câu dễ → loại.

## Hạn chế P3 (nói thẳng)

- **Gold chỉ 36 claim** → CI 95% ±16%. 61% nghĩa là thật sự nằm trong ~45–77%. Cần
  gán thêm để số chắc hơn.
- **Gold do LLM nháp rồi NGƯỜI audit** theo text luật (sửa 5 nhãn có căn cứ). Trung
  thực hơn "gold do LLM tự gán", nhưng vẫn 1 người duyệt.
- **ACCURATE recall yếu (0.33)** kể cả 70B — model thiên về phán INACCURATE.
- **Trần ~61%/41% chưa đủ auto-phán pháp lý** → thiết kế đúng là **human-in-the-loop**:
  máy tổng hợp + triage + nháp; người duyệt ca không chắc trước khi công bố. Giá trị
  sản phẩm nằm ở **bức tranh tổng hợp** (hiểu nhầm nào lan mạnh nhất), nơi nhiễu từng
  claim triệt tiêu — không phải ở phán đúng/sai từng bình luận.
