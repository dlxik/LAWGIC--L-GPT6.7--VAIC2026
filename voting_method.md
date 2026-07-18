# Voting đa model — cơ chế hoạt động & vì sao hiệu quả

> Giải thích cách P1 kết hợp 2 LLM để trích thực thể từ luật thuế, giảm
> hallucination **32% → 17%** mà gần như **không mất recall**. Số liệu ở
> [`benchmark.md`](benchmark.md) (Bảng 3 & 4). Code: `eval/vote_combine.py`,
> `scripts/combine_voting.py`.

---

## 1. Vấn đề: một LLM trích thì hay "bịa"

Trích thực thể (chủ thể / nghĩa vụ / chế tài…) từ văn bản luật bằng **một** LLM
cho ra **hallucination 32%** — cứ 3 span trích ra thì ~1 span sai. Với văn bản
pháp luật, sai kiểu này nguy hiểm: gán nhầm chủ thể = sai lệch nghĩa vụ pháp lý.

Quan trọng: **phần lớn "bịa" KHÔNG phải bịa chữ** (chữ không có trong text), mà là
**sai vai** — model lấy đúng cụm từ có thật nhưng **gán nhầm vai trò**. Ví dụ thật
từ `tncn2025-d22`:

```
Text: "Thuế thu nhập cá nhân đối với thu nhập từ đầu tư vốn của cá nhân
        không cư trú được xác định bằng..."

gpt-oss-20b:  subjects = ["cá nhân không cư trú"]   ← SAI VAI
```

"Cá nhân không cư trú" **có thật** trong text, nhưng ở đây họ là **đối tượng bị
đánh thuế**, không phải **chủ thể hành động**. Đây là câu quy tắc tính thuế, không
có ai "làm" gì cả. Model một mình rất hay mắc lỗi tinh vi này.

Lọc bằng code (kiểm "chữ có trong text không") **không cứu được** — vì chữ *có*
thật. Cần một cơ chế bắt được lỗi *ngữ nghĩa*, không phải lỗi *chính tả*.

---

## 2. Ý tưởng cốt lõi

> **Chạy 2 model khác nhau độc lập. Chỉ giữ span mà CẢ HAI cùng trích.**

Trực giác: hai model kiến trúc khác nhau (`gpt-oss-20b` của OpenAI và
`gemma-4-31B-it` của Google) **hiếm khi mắc CÙNG một lỗi sai vai**. Khi 20b nhầm
"cá nhân không cư trú" thành chủ thể, gemma đọc câu đó không nhầm → gemma **không
trích** span đó → **phép giao loại nó ra**.

Nói cách khác: **sự đồng thuận của hai bộ óc độc lập là bộ lọc ngữ nghĩa** mà một
mình model hay code đều không làm được.

---

## 3. Luồng hoạt động — từng bước

```
                 ┌─────────────────────────────────────────────┐
                 │  1.842 node (Điều/Khoản/Điểm) đã parse       │
                 └───────────────────┬─────────────────────────┘
                                     │
                 ┌───────────────────┴─────────────────────┐
                 ▼                                          ▼
     ┌───────────────────────┐                 ┌───────────────────────┐
     │  MODEL A: gpt-oss-20b │                 │  MODEL B: gemma-31B   │
     │  trích độc lập        │                 │  trích độc lập        │
     │  (cùng prompt EN)     │                 │  (cùng prompt EN)     │
     └───────────┬───────────┘                 └───────────┬───────────┘
                 │ predA[node][field] = [span…]             │ predB[node][field]
                 └───────────────────┬──────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │  2. CHUẨN HOÁ + SO KHỚP từng span            │
                 │     NFC → thường → bỏ dấu câu                │
                 │     khớp nếu: chứa nhau  HOẶC  ratio ≥ 0.60  │
                 └───────────────────┬─────────────────────────┘
                                     ▼
          ┌──────────────────────────────────────────────────────────┐
          │  3. HỢP PHIẾU theo trường                                 │
          │                                                          │
          │   • 9 trường thực thể → GIAO (A ∩ B)                     │
          │       giữ span của A nếu B có span khớp                  │
          │   • penalties        → GIỮ NGUYÊN A (20b)               │
          │       (gemma gán sai loại chế tài → không cho bỏ phiếu)  │
          └───────────────────┬──────────────────────────────────────┘
                              ▼
                 ┌─────────────────────────────────────────────┐
                 │  4. GHI graph cuối: entities_<doc>.json      │
                 │     (P2 nạp vào Neo4j)                        │
                 └─────────────────────────────────────────────┘
```

### Bước 1 — Hai model trích độc lập
Mỗi model chạy trên **toàn bộ 1.842 node**, cùng một prompt tiếng Anh, cùng cách
gộp node (8 node/lượt gọi). Kết quả lưu riêng:
`entities_20bfull_<doc>.json` và `entities_gemma_<doc>.json`.
→ *Độc lập là điều kiện sống còn: nếu hai model xem output của nhau thì hết "hai
bộ óc độc lập".*

### Bước 2 — Chuẩn hoá + so khớp span
Hai model diễn đạt hơi khác nhau ("phải nộp thuế" vs "nộp thuế"). Để so được:

```python
def _norm(s):                       # chuẩn hoá
    s = NFC(s).lower().strip()
    s = bỏ dấu câu (.,;:"'())
    return gộp khoảng trắng

def _similar(a, b):                 # độ giống 0..1
    na, nb = _norm(a), _norm(b)
    if na in nb or nb in na: return 1.0    # chứa nhau = khớp
    return SequenceMatcher(na, nb).ratio()  # else so ký tự
```

Hai span coi là "**khớp**" khi `_similar ≥ 0.60`. Luật "chứa nhau thì khớp" xử lý
đúng đặc thù luật: *"phải X"* và *"X"* là cùng một thứ.

### Bước 3 — Hợp phiếu (chỗ ma thuật xảy ra)

```python
def vote(a_list, b_list):
    # giữ span của A CHỈ KHI B có span khớp
    return [a for a in a_list
            if any(_similar(a, b) >= 0.60 for b in b_list)]
```

- **9 trường thực thể** (subjects, obligations, rights, prohibitions, deadlines,
  references, tax_rates, tax_base, exemptions) → dùng `vote()` = **giao**.
- **penalties** → **không giao**, giữ nguyên của 20b. Vì sao: xem §5.3.

### Bước 4 — Ghi graph
Ghép lại thành `entities_<doc>.json` — đây là file P2 (Linh) nạp vào Neo4j.

---

## 4. Ví dụ chạy thật — node `tncn2025-d22`

| | subjects |
|---|---|
| **Text gốc** | *"Thuế TNCN đối với thu nhập từ đầu tư vốn của **cá nhân không cư trú** được xác định bằng…"* |
| Model A (20b) trích | `["cá nhân không cư trú"]` ← sai vai |
| Model B (gemma) trích | `[]` ← đọc đúng, không có chủ thể hành động |
| **Giao A ∩ B** | `[]` ✅ |
| Gold (đáp án đúng) | `[]` ✅ |

20b bịa 1 chủ thể → gemma không xác nhận → **giao loại đúng**. Nếu chỉ dùng 20b,
graph sẽ có một cạnh sai "cá nhân không cư trú *là chủ thể của* Điều 22".

Cùng cơ chế cứu **node demo** `tncn2025-d7-k1` (ngưỡng 500 triệu): 20b bịa
"Ủy ban Thường vụ Quốc hội" làm chủ thể; gemma không có → giao loại → chỉ giữ
"Chính phủ" (đúng gold).

Trên toàn graph: 20b trích **~3.629 span**, giao loại **748 span (~21%)** mà gemma
không xác nhận → hallucination tụt từ **32% xuống 17%**.

---

## 5. Vì sao voting tốt "xuất sắc" — 3 lý do

### 5.1. Lỗi của hai model độc lập → hiếm khi trùng
Hallucination là lỗi **ngẫu nhiên theo từng model** (mỗi model nhầm chỗ khác nhau).
Xác suất **cả hai cùng bịa y hệt một span** rất thấp. Nên giao ≈ "lọc nhiễu bằng
đồng thuận" — nhiễu bị dập, tín hiệu thật (span đúng) sống sót vì **model tốt nào
cũng thấy**.

### 5.2. Recall KHÔNG tụt — điều phản trực giác
Lo ngại tự nhiên: "giao thì mất span chỉ 1 model thấy → recall tụt". **Đo thực tế
bác điều này**: recall chỉ giảm **3%** (92→89) trong khi precision tăng **12%**.

Lý do: **cả hai model vốn recall cao (92–93%)** — span *đúng* thường **hiển nhiên**
nên **cả hai đều bắt được**. Chỉ span *mơ hồ/sai* mới là loại "một model thấy, một
model không". Giao đánh trúng đúng loại rác đó mà gần như không đụng span thật.

> Điều kiện: voting giữ recall **chỉ khi** cả hai model đều recall cao. Nếu một
> model recall thấp (hay bỏ sót), giao sẽ tụt recall mạnh. Đây là lý do phải
> **benchmark chọn 2 model recall cao trước**, không ghép bừa.

### 5.3. Hybrid vá điểm mù của giao
Giao có một tác dụng phụ: nếu một model **mù hẳn** một trường, giao sẽ xoá sạch
trường đó. gemma có **penalty-type = 0%** (gán sai loại chế tài toàn bộ) → giao đòi
gemma đồng ý sẽ **triệt tiêu** mọi penalty.

Khắc phục — **hybrid**: giao 9 trường thực thể (nơi cả hai đều khá) **nhưng giữ
nguyên penalty của 20b** (nơi 20b mạnh 71%, gemma mù). Kết quả: F1 84% **VÀ**
penalty-type 71% — lấy điểm mạnh của mỗi model, tránh điểm mù.

---

## 6. Các biến thể đã thử — vì sao hybrid thắng

Không chỉ thử một cách rồi chốt; đo **5 cấu hình** để chắc chọn đúng:

| Cấu hình | Cơ chế | F1 | Precision | Recall | Hallucination |
|---|---|---:|---:|---:|---:|
| 20b đơn | 1 model | 78% | 68% | 92% | 32% |
| gemma đơn | 1 model | 81% | 72% | 93% | 28% |
| **A ∩ B** (giao) | giữ span cả hai đồng ý | 84% | 80% | 89% | 20% |
| A ∪ B (hợp) | giữ span của bất kỳ model nào | 75% | 61% | 98% | 39% |
| A ∪ B + lọc verbatim | hợp, rồi bỏ span không có trong text | 75% | 61% | 98% | 39% |
| **A∩B ent + A pen** ⭐ | giao 9 trường + giữ penalty 20b | **84%** | **80%** | **89%** | **20%** |

**Hai điều bảng này dạy:**

1. **Hợp (∪) làm tệ đi** — gộp cả hallucination của hai model, precision sập còn 61%.
   Recall lên 98% nhưng đổi bằng nhiễu tăng vọt. Sai hướng.
2. **Lọc verbatim VÔ DỤNG** — `A∪B` và `A∪B + lọc` **giống hệt**. Bằng chứng đanh
   thép rằng hallucination ở đây là **sai vai** (chữ có thật) chứ không phải bịa
   chữ. Lọc bằng code không chạm tới được → **chỉ voting mới là đòn bẩy**.

---

## 7. Khi nào KHÔNG nên dùng voting

Voting không phải thuốc tiên. Nó **chỉ hiệu quả khi**:

- **Cả hai model recall cao** (không thì giao tụt recall — §5.2).
- **Hai model đủ khác nhau** (khác nhà/kiến trúc) để lỗi độc lập. Ghép hai bản của
  cùng một model thì lỗi trùng, giao vô nghĩa.
- **Chịu được 2× chi phí** (chạy hai model). Với graph demo thì đáng; với hệ thống
  gọi API triệu lượt/ngày thì phải cân nhắc.
- **Có một model bù được điểm mù của model kia** (như penalty-type) → dùng hybrid,
  đừng giao mù quáng.

---

## 8. Bản đồ code

| File | Vai trò |
|---|---|
| `scripts/run_full_model.py` | Chạy 1 model trên toàn bộ 1.842 node, lưu có hậu tố |
| `scripts/combine_voting.py` | Hợp phiếu hybrid → `entities_<doc>.json` cuối (P2 nạp) |
| `eval/bench_raw.py` | Trích 100 node gold, lưu span thô để voting trên gold |
| `eval/vote_combine.py` | Đo 5 cấu hình voting trên gold (bảng §6) |
| `eval/benchmark_p1.py` | Đo graph cuối vs gold (Bảng 4 trong benchmark.md) |

**Tái lập:**
```bash
python scripts/run_full_model.py gpt-oss-20b    20bfull   # model A
python scripts/run_full_model.py gemma-4-31B-it gemma     # model B
python scripts/combine_voting.py                          # hybrid → graph cuối
python eval/benchmark_p1.py                               # kiểm chất lượng
```

---

**Một câu tóm tắt cho BGK:** *thay vì tin một LLM, chúng em cho hai model độc lập
"bỏ phiếu" — chỉ giữ điều cả hai đồng ý — nên hallucination giảm gần một nửa mà
gần như không mất recall, vì span luật đúng thì model nào cũng thấy, còn span bịa
thì mỗi model bịa một kiểu nên bị loại khi đối chiếu.*
