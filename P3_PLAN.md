# P3 — Dư luận + Đo lường · Kế hoạch hành động 24h

> Sở hữu: `scripts/fetch_social_posts.py`, `backend/discourse/`, `eval/`, `prompts/classify_topic.txt`, `prompts/detect_misunderstanding.txt`
> Branch: `p3-discourse` · Merge vào `main` ở giờ 8, 16, 21.

## Giao nộp cuối (chỉ 2 thứ này quyết định điểm của P3)

1. **≥500 post đã gắn nhãn** trong `data/processed/posts_labeled/`, đúng `schemas.Post` + `schemas.Claim`.
2. **Con số accuracy trên gold set** — `python eval/run_eval.py` in ra được, accuracy ≥80% trên ≥50 claim gắn nhãn tay.

Thứ 2 quan trọng hơn thứ 1. BGK chắc chắn hỏi *"làm sao biết phân loại đúng?"*, và
đây là câu duy nhất mà không có số thì không trả lời được. Nếu đến giờ 18 phải chọn
giữa "1000 post" và "50 claim gold + accuracy", **chọn accuracy**.

## Hai thứ P3 bị phụ thuộc

| Phụ thuộc | Của ai | Khi nào có | Né thế nào |
|---|---|---|---|
| `backend/core/llm.py` (`extract`, `extract_batch`, `load_prompt`) | P4 | Hứa giờ 3 | Code theo đúng interface đã khai báo, test bằng fake trả JSON cứng. Không sửa file của P4. |
| Graph có `Point` thật để `linker.py` truy vấn | P1→P2 | Giờ 8 (mock) / giờ 16 (đầy đủ) | Giờ 1–8 linker chạy trên `data/mock/points.json` do P3 tự bịa 5 điểm đúng schema. |

**Nguyên tắc:** không có việc nào của P3 được phép đứng chờ. Bị chặn → chuyển sang việc khác trong cùng khung giờ.

---

## Giờ 0–1 · Ngồi chung cả team

Không phải việc riêng của P3, nhưng P3 phải nói được 2 điều trước khi tản ra:

- Chốt `Post`, `Claim`, `Citation`, `Misconception` trong `schemas.py` — **P3 là người duy nhất sinh ra 4 model này**, ai đó chốt sai thì P3 gánh. Kiểm: `Claim.citations` là `list[Citation]` chứ không phải `list[str]` (cần confidence per-citation cho eval citation_accuracy).
- Hỏi P1: **3 văn bản demo là gì, URL nào**. P3 cần biết để tìm đúng bài báo có comment về đúng 3 văn bản đó. Không biết → crawl nhầm chủ đề → 500 post vô dụng.

---

## Giờ 1–8 · Crawl (chạy nền) ‖ Classifier (viết tay)

Crawl là đường găng của cả P3 — tốn thời gian nhất, rủi ro bị chặn cao nhất. **Bấm chạy ở phút thứ 1, không phải giờ 8.**

### 1.1 · Giờ 1–2 — Thử nghiệm crawl (làm trước mọi thứ)

Mục tiêu: biết trong 60 phút là nguồn nào lấy được, không phải đoán.

- Thử `fetch_comments()` trên **1 URL của mỗi nguồn**: VnExpress, Tuổi Trẻ, Dân Trí.
- Comment các báo này load bằng AJAX, không nằm trong HTML — mở DevTools → Network → tìm endpoint JSON trả comment. Gọi thẳng endpoint đó, đừng parse HTML.
- Ghi lại vào `scripts/fetch_social_posts.py` dạng comment: nguồn nào OK, endpoint gì, rate limit bao nhiêu.

**Chốt lúc giờ 2:** nếu cả 3 nguồn đều chặn → **chuyển ngay sang xuất thủ công** từ 1–2 bài báo có nhiều comment (copy DOM ra JSON). 500 post là đủ demo, không cần đẹp. Không ngồi vật lộn với anti-bot quá giờ 2 — đó là cái bẫy tiêu 6 tiếng.

### 1.2 · Giờ 2–3 — Hoàn thiện `scripts/fetch_social_posts.py`

```
fetch_comments(article_url) -> list[dict]
main() -> ghi data/raw/social_posts/{platform}_{article_slug}.json
```

Bắt buộc:
- `author_hash = sha256(author_id + salt)[:16]` — **không lưu tên/email/avatar**. Đây là ràng buộc đạo đức đã ghi trong README, BGK có thể hỏi.
- Ghi thêm `engagement` (số like/reply) — `misinformation.detect_trends()` cần nó để tính severity, thiếu là phải crawl lại.
- Idempotent: chạy lại không nhân đôi post. Key theo `post_id`.
- Sleep giữa các request, retry có backoff. Bị 429 giữa chừng mà mất sạch là mất 3 tiếng.

**Rồi bấm chạy nền và bỏ đó.** Sang 1.3 ngay.

### 1.3 · Giờ 3–6 — `prompts/classify_topic.txt` + `backend/discourse/classifier.py`

Prompt đã có khung + quy tắc. Việc của P3 là điền phần còn thiếu:
- Danh sách `topic` cố định (khoảng 5–8 chủ đề, bám 3 văn bản demo — vd `nong_do_con`, `toc_do`, `giay_phep_lai_xe`, `khac`). **Enum đóng**, không cho LLM tự đặt tên chủ đề, nếu không `/trends` sẽ vỡ vì 50 biến thể của cùng 1 chủ đề.
- 3–4 few-shot lấy từ post thật vừa crawl, **phải có 1 ví dụ `is_legal_claim=false`** (post cảm xúc) và 1 ví dụ post chứa 2 claim.

`classifier.py`:
```
classify_posts(posts: list[dict]) -> dict[str, dict]
```
- Dùng `llm.extract_batch(items, schema)` với `items = [(post_id, prompt)]`. **Kết quả về không theo thứ tự → luôn key theo `custom_id`**, đừng zip theo index.
- Định nghĩa Pydantic model cho output (`topic`, `is_legal_claim`, `claims: list[{claim_id, text}]`) ngay trong `classifier.py` — đây là model nội bộ, không đụng `schemas.py`.
- `claim_id` sinh deterministic: `f"{post_id}-c{i}"`. Chạy lại phải ra cùng id, nếu không eval sẽ lệch.

**Test không cần P4:** viết `fake_extract_batch` trả sẵn 3 kết quả cứng → chạy `classify_posts` trên 5 post mock. Xong ở giờ 6 dù P4 trễ.

### 1.4 · Giờ 6–8 — Bắt đầu gold set (đừng để đến giờ 16)

Đây là chỗ **mọi người đều trễ**: gắn nhãn tay 50 claim mất 2–3 tiếng thật, không phải 30 phút.

- Từ post thô đã crawl, chọn 50 claim đa dạng → điền `eval/gold_set.jsonl` theo đúng format dòng mẫu `g001` đã có:
  ```json
  {"claim_id","text","expected_verdict","expected_citation","note"}
  ```
- **Phân bổ nhãn có chủ đích**, không lấy ngẫu nhiên: ~15 `INACCURATE`, ~15 `PARTIALLY_INACCURATE`, ~10 `ACCURATE`, ~10 `UNVERIFIABLE`. Nếu 45/50 là INACCURATE thì accuracy 90% cũng vô nghĩa — BGK hỏi baseline là chết.
- Làm được 20 dòng ở giờ 8 là đạt. Còn lại nhét vào các khoảng chờ batch ở giờ 8–16.

> **Mốc tích hợp 1 (giờ 8) — Definition of Done của P3:**
> - [ ] ≥500 post thô trong `data/raw/social_posts/`
> - [ ] `classify_posts()` chạy được trên mock, output đúng schema
> - [ ] `classify_topic.txt` có enum topic + few-shot thật
> - [ ] ≥20 dòng gold set
> - [ ] Merge `p3-discourse` → `main`

---

## Giờ 8–16 · Linker + Misinformation (khung giờ nặng nhất)

Thứ tự bắt buộc: **bấm batch classify toàn bộ post TRƯỚC, rồi mới viết linker.** Batch mất <1h, đừng ngồi nhìn nó chạy.

### 2.1 · Giờ 8 (15 phút đầu) — Bấm chạy batch

`classify_posts()` trên toàn bộ 500+ post → `data/processed/posts_labeled/classified.json`. Batches API rẻ 50%. Bấm xong sang 2.2 ngay.

### 2.2 · Giờ 8–12 — `backend/discourse/linker.py`

**Đây là phần P3 phải bảo vệ trước BGK.** Nó là lý do dự án dùng graph database chứ không phải vector store, và slide sẽ nói về nó.

```
link_claim(claim_text, topic) -> list[dict]   # list[Citation]
```

Ba bước, làm đúng thứ tự:

1. **Lấy ứng viên** — full-text index trên `Point.text` (P2 tạo trong `graph/schema.py:INDEXES`) → top-K Điểm, K≈10. Nếu P2 chưa có index lúc giờ 8: tự BM25 bằng `rank_bm25` trên `data/mock/points.json`. Đổi sang graph sau, interface không đổi.
2. **Mở rộng theo graph** — với mỗi Điểm ứng viên: lấy Khoản cha, Điều ông, và **đi theo `SUPERSEDED_BY` cả hai chiều**. Bước này là điểm ăn tiền: tin đồn thường bám quy định **cũ**, nên Điểm đúng để trích dẫn là Điểm mới, nhưng Điểm khớp text lại là Điểm cũ. Vector store không bắc được cầu này.
3. **LLM chọn** — đưa toàn bộ ứng viên đã mở rộng cho `llm.extract_cached(...)`, cached_context = text các Điểm (ổn định, cache hit ~90%), câu hỏi = claim (đặt SAU breakpoint). Trả `list[Citation]` có `confidence`.

Ràng buộc cứng:
- `Citation.node_id` **phải khớp node có thật**. LLM bịa node_id → drop, không trả về. Đây là lớp chặn của P3, P4 còn một lớp nữa ở API — hai lớp độc lập.
- Không tìm được ứng viên nào → trả `[]`, để `misinformation` gán `UNVERIFIABLE`. **Không đoán bừa.**
- `REFERS_TO` có property `method` trong graph schema → set `"bm25+graph+llm"` để P2 nạp đúng.

### 2.3 · Giờ 12–15 — `backend/discourse/misinformation.py` + `detect_misunderstanding.txt`

Ba hàm, độ ưu tiên giảm dần:

```
verdict_for_claim(claim_text, citations) -> {verdict, confidence, explanation, correct_statement}
cluster_misconceptions(claims) -> list[Misconception]
detect_trends() -> list[TrendAlert]
```

- `verdict_for_claim`: prompt đã có quy tắc tốt. Điền few-shot, **bắt buộc có 1 ví dụ `UNVERIFIABLE`** — nếu không LLM sẽ ép mọi claim vào ACCURATE/INACCURATE và `UNVERIFIABLE` thành nhãn chết, kéo accuracy xuống. Chạy qua `extract_batch`.
- `cluster_misconceptions`: **đừng dùng LLM clustering.** Embed `claim.text` → cosine ≥ ngưỡng (0.85, tự chỉnh) → gom cụm; `canonical_text` = claim có engagement cao nhất trong cụm. Rẻ, nhanh, giải thích được với BGK. LLM clustering vừa đắt vừa không reproducible.
- `detect_trends`: đọc `settings.trend_min_occurrences` (=5) và `trend_window_hours` (=48) từ `config.py`, **không hardcode**. `velocity = count / số giờ trong window`; `severity` theo velocity × total_engagement (tự chốt ngưỡng LOW/MEDIUM/HIGH, ghi vào docstring để P4 hiển thị đúng).

### 2.4 · Giờ 15–16 — Chạy pipeline đầy đủ + giao dữ liệu cho P2

Chạy `classify → link → verdict → cluster` trên toàn bộ post → `data/processed/posts_labeled/`. Báo P2 nạp vào graph.

> **Mốc tích hợp 2 (giờ 16) — Definition of Done của P3:**
> - [ ] 500+ post đã có `topic` + `claims`
> - [ ] Claim đã có `citations` khớp node_id thật + `verdict`
> - [ ] `detect_trends()` trả ≥1 alert thật — **case "nồng độ cồn" phải nằm trong đó**, vì `demo/sample_case.md` xây quanh nó
> - [ ] Gold set đủ 50 dòng
> - [ ] Merge → `main`

---

## Giờ 16–20 · Con số (ưu tiên cao nhất của P3 trong cả 24h)

### 3.1 · Giờ 16–18 — `eval/run_eval.py`

```
load_gold() -> list[dict]
evaluate() -> {verdict_accuracy, citation_accuracy, per_class_f1, confusion_matrix}
```

- `verdict_accuracy`: so verdict pipeline vs `expected_verdict`.
- `citation_accuracy`: `expected_citation` có nằm trong `[c.node_id for c in citations]` không. **Báo riêng, không gộp vào verdict_accuracy** — hai con số này trả lời hai câu hỏi khác nhau, gộp lại là mất điểm.
- `per_class_f1` + `confusion_matrix`: in ra terminal cho đẹp. Confusion matrix là thứ thuyết phục nhất khi BGK nghi ngờ — nó cho thấy P3 biết model sai ở đâu.
- In cả **baseline**: accuracy nếu đoán bừa nhãn phổ biến nhất. Không có baseline thì 80% không có nghĩa gì.

**Nếu accuracy < 80%:** đọc confusion matrix, sửa **prompt/few-shot**, không sửa gold set. Sửa gold cho khớp output là gian lận và BGK nhìn ra ngay. Lỗi hay gặp: ACCURATE ↔ PARTIALLY_INACCURATE lẫn nhau → thêm few-shot phân biệt "đúng hành vi, sai mức phạt".

### 3.2 · Giờ 18–19 — Điền `demo/sample_case.md`

File đang có 6 chỗ `[TODO]` chờ **đúng số liệu của P3**: lần đầu xuất hiện, số lần lặp, tổng tương tác, confidence, định chính nguyên văn. P4 dựng demo quanh file này — trễ là P4 kẹt.

### 3.3 · Giờ 19–20 — Chuẩn bị trả lời BGK

Ba câu chắc chắn bị hỏi, chuẩn bị số liệu sẵn:
- *"Làm sao biết phân loại đúng?"* → accuracy + citation_accuracy + confusion matrix + baseline, trên 50 claim gắn nhãn tay.
- *"Sao không dùng vector search cho nhanh?"* → bước 2 của `linker.py`: tin đồn bám luật cũ, `SUPERSEDED_BY` bắc cầu sang Điểm mới. Mở đúng case nồng độ cồn ra chỉ.
- *"Dữ liệu comment có hợp pháp không?"* → chỉ nội dung công khai, `author_hash` sha256, không lưu danh tính.

> **Mốc 3 (giờ 20–21): ĐÓNG BĂNG.** Sau giờ 20 P3 chỉ sửa lỗi. Tính năng chưa xong thì bỏ.

---

## Giờ 21–24 · Demo

Diễn tập 2 lần có bấm giờ cùng cả team. P3 nói phần trend + con số eval — **thuộc lòng 3 con số**: accuracy, citation_accuracy, số post. Đọc vấp ở chỗ này là mất điểm phần mạnh nhất của P3.

---

## Bảng cắt tính năng (khi trễ, cắt theo đúng thứ tự này)

| Ưu tiên | Hạng mục | Cắt được không |
|---|---|---|
| 1 | Gold set 50 claim + `run_eval.py` ra số | **Không.** Mất là mất điểm nặng nhất. |
| 2 | `linker.py` bước mở rộng graph | **Không.** Bỏ là dự án còn là RAG thuần. |
| 3 | `verdict_for_claim` + case nồng độ cồn | **Không.** `sample_case.md` xây quanh nó. |
| 4 | `detect_trends` | Không. Đây là output cảnh báo chính. |
| 5 | `cluster_misconceptions` chuẩn | Hạ cấp được — gom tay 3 cụm cho demo. |
| 6 | 500 post | Hạ được xuống 200 nếu crawl chặn. Gold set vẫn phải đủ 50. |
| 7 | Đủ 3 nguồn báo | Cắt được. 1 nguồn cũng demo được. |

## Rủi ro riêng của P3

| Rủi ro | Dấu hiệu sớm | Xử lý |
|---|---|---|
| Crawl bị chặn | Giờ 2 chưa lấy được comment nào | Xuất thủ công 1–2 bài. Không vật lộn anti-bot quá giờ 2. |
| P4 trễ `llm.py` quá giờ 3 | Giờ 4 vẫn `NotImplementedError` | Đã có fake → không chặn. Giờ 6 vẫn chưa có thì báo cả team, đây là rủi ro toàn dự án chứ không riêng P3. |
| Gold set để đến giờ 16 mới làm | — | Bắt đầu từ giờ 6. Đây là lỗi kinh điển và là rủi ro số 1 của P3. |
| Batch classify lỗi giữa chừng | Kết quả thiếu post | Key theo `custom_id`, chạy lại chỉ phần thiếu. Đừng chạy lại cả batch. |
| Accuracy < 80% ở giờ 18 | — | Sửa few-shot, **không sửa gold set**. Còn 2h là đủ cho 2 vòng lặp. |
| Topic do LLM tự đặt tên | `/trends` ra 50 chủ đề trùng nghĩa | Enum đóng ngay từ giờ 3. |
