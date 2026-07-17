# Crawl dư luận — tài liệu bàn giao cho P3

> Quân (P1) làm hộ phần crawl của P3 vì đây là rủi ro #1 theo [DIVISION.md](DIVISION.md).
> Phần còn lại của P3 (`classifier` / `linker` / `misinformation` / `eval`) vẫn là của Hiền.

**Trạng thái:** ✅ Yêu cầu #3 của đề bài (*theo dõi thảo luận mạng xã hội*) — xong, đã kiểm chứng.

---

## 1. Kết quả

| | |
|---|---|
| **Post** | **3.321** — mục tiêu DIVISION.md là ≥500 → gấp **6,6×** |
| ├ comment gốc | 1.446 |
| └ reply | 1.875 (**56%**) |
| Bài báo nguồn | 12 |
| Tác giả duy nhất | 1.893 |
| Thời gian | 04/6/2025 → 10/4/2026 |
| Luồng dài nhất | 90 post |
| File | `data/raw/social_posts.json` (2,0 MB) |

---

## 2. Lấy dữ liệu ở đâu

### Nguồn đã thử và loại

| Nguồn | Kết quả | Ghi chú |
|---|---|---|
| **Facebook** | ❌ loại | Không còn API công khai lấy comment |
| **thuvienphapluat.vn** | ❌ loại | Không có mục bình luận |
| **VnExpress** | ✅ **dùng** | API JSON công khai, không cần key, không cần đăng nhập |

### API VnExpress — hai endpoint

**Comment gốc:**
```
GET https://usi-saas.vnexpress.net/index/get
    ?objectid={article_id}      # ID bài, 7 chữ số
    &objecttype=1
    &siteid=1000000
    &offset=0&limit=100         # limit tối đa 100
    &sort=like&is_onload=1&frommobile=0
Header: Referer: https://vnexpress.net/
```

**Reply** — mất 30 phút dò, ghi lại kẻo quên:
```
GET https://usi-saas.vnexpress.net/index/getreplay
    ?objectid={article_id}      # ⚠️ BÀI, không phải comment_id
    &id={comment_id}            # ⚠️ comment gốc truyền qua `id`
    &objecttype=1
    &siteid=1000000
    &limit=100&offset=0         # ⚠️ thiếu offset → "Invalid offset"
```

Hai bẫy đã trả giá:
- `objectid={comment_id}` → `{"error":1,"errorDescription":"Invalid id"}`
- Thiếu `offset` → `"Invalid offset"`

**Vì sao phải gọi riêng:** `COMMENT_API` trả `replys: {total: 47, items: []}` — báo có 47 reply nhưng **không đưa**. Không gọi `getreplay` là mất **56% dữ liệu**, im lặng.

### Danh sách bài

Quét trang chủ đề `https://vnexpress.net/topic/thue-ho-kinh-doanh-28377` (p1–p3) → **58 bài**.
Lấy **12 bài nhiều thảo luận nhất** (`MAX_ARTICLES`), probe `limit=1` đọc `total` để chọn.

**Vì sao ít bài mà đủ luồng, thay vì nhiều bài mà cụt:**
Thảo luận là **cả luồng**. Hiểu nhầm và đính chính nằm cạnh nhau:
```
gốc:   "Doanh thu 200 triệu là phải đóng thuế rồi"
reply: "Bạn nhầm, từ 2026 là 500 triệu cơ"
```
53 bài × chỉ gốc = 2.892 câu nói lẻ.
12 bài × (gốc + toàn bộ reply) = **3.321 post có ngữ cảnh**. Ít bài hơn 4,4× mà **nhiều dữ liệu hơn**.

---

## 3. File code đã sửa

| File | Thay đổi | Chủ sở hữu |
|---|---|---|
| `scripts/fetch_social_posts.py` | Viết mới hoàn toàn (303 dòng) | P3 |
| `backend/models/schemas.py` | **+ `Post.parent_id`** | ⚠️ **contract chung** |
| `backend/graph/schema.py` | **+ `(Post)-[:REPLY_TO]->(Post)`** | ⚠️ **contract chung** |
| `backend/graph/loader.py` | **+ `_MERGE_REPLY_TO`** | P2 (Linh) |
| `.gitignore` | ngoại lệ cho `social_posts.json` | chung |

**Ba file contract đã sửa khi Linh đang ngưng.** Linh cần biết.

Chi tiết `loader.py`:
```cypher
MATCH (child:Post {post_id: $post_id})
MERGE (parent:Post {post_id: $parent_id})   -- MERGE, KHÔNG phải MATCH
MERGE (child)-[:REPLY_TO]->(parent)
```
`MERGE` node cha để reply nạp **trước** gốc vẫn nối được. Thứ tự nạp không được phép quyết định graph đúng hay sai.

---

## 4. Định dạng JSON

Mảng **phẳng** `list[Post]`, mỗi **luồng nằm liền nhau** (gốc → reply của nó).

```json
{
  "post_id": "vne-61662018",
  "platform": "vnexpress_comment",
  "url": "https://vnexpress.net/nguong-chiu-thue-voi-ho-kinh-doanh-toi-thieu-phai-500-trieu-dong-4965888.html",
  "author_hash": "fdc1bfde36537771",
  "content": "Cứ cho rằng mức lãi \"đáng mơ ước\" 20% đi chăng nữa thì doanh thu 500Tr cũng chỉ mang lại thu nhập 100Tr/năm thấp hơn mức phải nộp thuế của người hưởng lương rất nhiều.",
  "created_at": "2025-11-19T12:19:24+00:00",
  "engagement": 744,
  "parent_id": null
}
```

### Giải thích từng trường

| Trường | Nguồn (field VnExpress) | Ý nghĩa |
|---|---|---|
| `post_id` | `"vne-" + comment_id` | Khoá duy nhất. Tiền tố `vne-` để sau thêm nguồn khác (`tt-`, `dt-`) không đụng id |
| `parent_id` | `null` = gốc; `"vne-xxx"` = reply của post đó | Chở luồng → cạnh `REPLY_TO` |
| `platform` | cố định `"vnexpress_comment"` | Phân biệt nguồn; thêm báo khác không đổi schema |
| `url` | quét slug từ trang chủ đề | **Nguồn kiểm chứng** |
| `author_hash` | `sha256(userid)[:16]` | Ẩn danh một chiều |
| `content` | `content`, đã lọc HTML + `@mention` | Text cho LLM |
| `created_at` | `creation_time` (unix) → ISO **UTC** | Q3 lọc thời gian |
| `engagement` | **`userlike`** | Sức lan toả; Q3 xếp hạng bằng `sum(engagement)` |

### ⚠️ `parent_id` — chỗ dễ nhầm nhất

```
parent_id = "TÔI trả lời AI"
parent_id ≠ "AI trả lời TÔI"
```

`vne-61662018` có `parent_id: null` **nhưng có 58 reply**. `null` nghĩa là *"đây là comment gốc"*, **không phải** *"không ai rep nó"*.

Mũi tên chỉ **lên trên**: con biết cha, cha không biết con. Muốn biết có ai rep mình → tự đếm:
```python
kids = {}
for p in posts:
    if p["parent_id"]:
        kids.setdefault(p["parent_id"], []).append(p)
len(kids.get("vne-61662018", []))   # 58
```
Neo4j đọc ngược cạnh: `MATCH (r:Post {post_id:$id})<-[:REPLY_TO]-(reply) RETURN count(reply)`

**Không có trường `reply_count`** — cố ý. Đếm được từ `parent_id`; lưu hai chỗ thì hôm nào lệch nhau không biết tin cái nào.

### Ba trường có bẫy

| Bẫy | Sai thành | Đúng là |
|---|---|---|
| Like | `rating` — **dict rỗng** → engagement luôn = 0, Q3 mất ý nghĩa | **`userlike`** |
| Ẩn danh | hash `full_name` — tên thật **suy ngược được bằng bảng tra** | hash **`userid`** |
| Múi giờ | lưu giờ VN | lưu **UTC** + offset, Neo4j `datetime()` đọc thẳng |

### Trường KHÔNG lưu — cố ý

`full_name` (tên thật), `userid` thô, `replys.total` (trùng), `article_id` (đã có trong url), `t_r_1..4`/`is_pin`/`type` (chỉ số nội bộ VnExpress).

Nguyên tắc: **chỉ giữ thứ đề bài cần**. Mỗi trường thừa là một trường phải giải thích với BGK — nhất là khi nó dính người thật.

---

## 5. Quyền riêng tư

Đề bài: *"Comment chỉ lấy nội dung công khai, tác giả được hash, không lưu danh tính."*

**Rò rỉ đã tìm ra và vá** — chỉ xuất hiện ở **reply**, comment gốc không bao giờ dính:

```html
<!-- content thô của reply -->
<span class="reply_name myuser" data-userid="1073324795">@trungtuyen938</span>:&nbsp;Nên người mua...
                              └─── userid THÔ ───┘  └─ tên tài khoản thật ─┘
```

**1.016 post (31%)** dính. `_clean_content()` cắt **cả khối** `<span>` chứ không chỉ tag — `parent_id` đã cho biết trả lời ai, tiền tố `@mention` là thừa mà lại chở danh tính.

### Bảng kiểm — chạy lại sau mỗi lần crawl

| Kiểm | Hiện tại |
|---|---|
| Pydantic `Post` | ✅ 3.321/3.321 |
| `data-userid` thô trong content | ✅ 0 |
| `@handle` tên thật | ✅ 0 |
| HTML tag / entity sót | ✅ 0 / 0 |
| Email thật / SĐT | ✅ 0 / 0 |
| Reply mồ côi (`parent_id` không tồn tại) | ✅ 0 |
| URL sai định dạng | ✅ 0 |
| Content rỗng | ✅ 0 |

---

## 6. Hạn chế đã biết

| | Vấn đề | Ảnh hưởng |
|---|---|---|
| 1 | **Không có comment tháng 7/2026.** Mới nhất 10/4/2026 | `Q3_TRENDING_MISCONCEPTIONS` lọc `created_at > datetime() - 48h` → **dashboard trend TRỐNG**. Xem mục 7 |
| 2 | **Crawler 0 test** | Bốn bug (404, mất reply, rò userid, đo nhầm file) đều lọt vì không ai bấm thử. Món nợ |
| 3 | `Post.url` trỏ **bài**, không trỏ **comment** | VnExpress không neo được từng comment. Bấm ra bài, phải tự tìm |
| 4 | Chỉ 1 nguồn (VnExpress) | Tuổi Trẻ / Dân Trí có API riêng, chưa dò |
| 5 | README ghi *"thảo luận đến 17/7/2026"* | **Sai** — thật là 10/4/2026. Cần sửa |

### Vì sao không có comment tháng 7/2026

Sóng thảo luận đỉnh lúc luật **được thông qua** (6/2025: 824 post, 11/2025: 863), rồi tắt dần. Đến lúc luật **có hiệu lực** (1/7/2026) thì báo chí đã chuyển chủ đề. Đây là **thực tế của dữ liệu**, không phải lỗi crawl.

---

## 7. Hướng phát triển

### 7.1 Sửa Q3 — bắt buộc, nếu không dashboard trống

Hai cách:

| | Cách | Đánh giá |
|---|---|---|
| A | Nới `TREND_WINDOW_HOURS` (48 → ~4320) | Nhanh, nhưng "trend 180 ngày" nghe không giống trend |
| **B** | **Neo Q3 vào mốc thời gian truyền vào**, giống `law_as_of(date)` | **Nên chọn.** Demo nói *"tại 15/12/2025, tin đồn X đang lan mạnh"* — hợp chủ đề time-travel của cả dự án, và hay hơn |

Việc của Linh (Q3) + Nguyên (dashboard).

### 7.2 Gửi CẢ LUỒNG cho LLM, không gửi từng post lẻ

**Đây là quyết định thiết kế quan trọng nhất còn lại của P3.**

Vấn đề: **322/1.875 reply (17%) đọc riêng là vô nghĩa.**

```
REPLY [74 like]: "Rất chính xác"
   ↳ gốc: "Cái vấn đề ở đây là không rõ ràng giữa doanh thu và thu nhập…"
```

`classify("Rất chính xác")` → LLM trả *"không có khẳng định pháp lý"* — **và nó đúng**. 74 like bốc hơi, im lặng.

⚠️ **JSON lồng KHÔNG cứu được chuyện này.** Lồng hay phẳng, nếu code vẫn truyền `post["content"]` một mình vào LLM thì vẫn mất ngữ cảnh y hệt. Ngữ cảnh mất ở tầng **prompt**, không phải tầng **lưu trữ**.

**Cách đúng — gộp luồng:**

```
Đây là một luồng thảo luận. Trích khẳng định pháp lý cho TỪNG bình luận.

[GỐC] post_id=vne-61662018
Cứ cho rằng mức lãi "đáng mơ ước" 20% đi chăng nữa thì doanh thu 500Tr...

  [TRẢ LỜI] post_id=vne-61662092
  Theo tính toán của tôi thì phải tầm 1,5 tỷ mới chịu thuế...
```

Trả về `list[Claim]`, mỗi claim mang `post_id`. **`schemas.py::Claim` đã có sẵn `post_id`** → không đụng contract.

Thắng cả ba mặt:

| | Từng post lẻ | **Cả luồng** |
|---|---|---|
| Call LLM | 3.321 | **1.446** (−56%) |
| Token input | ~1.205k | **~642k** (−47%) |
| Ngữ cảnh | phải tự ghép | **có sẵn** |
| Bắt được đính chính | ❌ | ✅ |

Lợi ích thứ tư quan trọng nhất: LLM thấy **dư luận tự sửa nhau** → đúng yêu cầu #6 (*phát hiện hiểu nhầm*).

**Hai rủi ro:**
1. **LLM bỏ sót post trong luồng dài** (lớn nhất: 90 post / ~5.400 token). Bắt buộc kiểm `số post_id trả về == số post gửi đi`, thiếu thì gọi lại.
2. **Hỏng cả cụm** — 1 luồng lỗi = mất 90 post. Batches retry theo `custom_id` → `custom_id` phải là **thread_id**, không phải post_id.

**Ưu tiên 314 luồng có tranh luận:** 78% "luồng" chỉ có 1 post (1.132 gốc không ai rep). Chỉ **314 luồng (22%)** thật sự có tranh luận — nhưng chứa **toàn bộ 1.875 reply**. Đó là chỗ hiểu nhầm sinh ra và lan.

### 7.3 Có cần tiền xử lý để tiết kiệm token? — **KHÔNG**

Đo thật:

```
Tổng nội dung: 730.028 ký tự ≈ 209k token
```

| Lọc thử | Bỏ được | Token tiết kiệm |
|---|---|---|
| Post < 25 ký tự | 83 | **0,4k (0%)** |
| Không có từ khoá pháp lý | 762 | 21,1k (10%) |
| Trùng lặp y hệt | **4** | ~0 |
| **Tổng nếu lọc hết** | 781 (24% post) | **~10%** |

**Kết luận: bỏ 24% post để tiết kiệm 10% token — lỗ.**

Tính tiền cụ thể (Haiku 4.5 $1/1M input, Batches −50%):
```
209k token nội dung + 1.446 × 300 token prompt ≈ 640k input
→ ~$0,64 Haiku  →  ~$0,32 qua Batches
```

**Cả bước phân loại tốn chưa tới nửa đô.** Lọc 10% tiết kiệm được **3 xu**.

Và lọc theo từ khoá là **nguy hiểm**:
```
[23 like] "ế ẩm quá"                              ← không có từ khoá, nhưng là tín hiệu thật
[32 like] "Người tiêu dùng lại là người gánh thêm" ← claim kinh tế, không có chữ "thuế"
```
Regex vứt đi thứ mà LLM lẽ ra nhận ra. **Phân loại là việc của classifier — đó chính là lý do nó tồn tại.** Đừng đặt một regex ngu hơn đứng trước nó.

**Đáng làm** (không phải để tiết kiệm token):

| | Việc | Lý do |
|---|---|---|
| ✅ | Bỏ HTML + `@mention` | **Đã làm.** Riêng tư + đỡ nhiễu LLM |
| ✅ | Gộp khoảng trắng | **Đã làm** |
| ✅ | Gộp luồng (7.2) | −47% token **và** ngữ cảnh tốt hơn |
| ✅ | Prompt caching cho phần hướng dẫn | Rẻ ~90% khi lặp — nhưng prefix phải ≥1024 token (Haiku 4.5: 4096) |
| ❌ | Lọc từ khoá | Bỏ 24% dữ liệu, tiết kiệm 3 xu, mất tín hiệu thật |

### 7.4 Mở rộng (chỉ khi xong việc chính)

| | Việc | Được gì |
|---|---|---|
| 1 | **Thêm nguồn**: Tuổi Trẻ, Dân Trí, VietnamNet | Đa dạng dư luận. `platform` đã sẵn sàng, `post_id` có tiền tố |
| 2 | Nới `MAX_ARTICLES` 12 → 58 | ~10.000 post. **Không cần** — đã gấp 6,6× mục tiêu |
| 3 | **Test cho crawler** | Trả nợ mục 6.2 |
| 4 | `scripts/show_thread.py` | Hiền cần khi gắn nhãn 50 claim cho gold set |

---

## 8. Chạy lại

```bash
python scripts/fetch_social_posts.py     # ~10 phút, ghi đè data/raw/social_posts.json
```

Tham số ở đầu file: `MAX_ARTICLES=12`, `TOPIC_PAGES=3`, `PAGE_SIZE=100`, `REQUEST_DELAY=0.25`.

`REQUEST_DELAY` là phép lịch sự với máy chủ VnExpress — **đừng hạ xuống 0**. Ta đang dùng API công khai của người ta, không có thoả thuận nào.

---

## 9. Việc tiếp theo của Hiền

Theo thứ tự phụ thuộc:

1. **`prompts/classify_topic.txt`** — không chờ ai, làm được ngay
2. **`classifier.py`** — theo thiết kế 7.2 (gộp luồng). Chờ `core/llm.py` của Nguyên, nhưng chữ ký hàm đã chốt trong docstring → code trước, test bằng fake
3. **`linker.py`** — cần graph của Linh chạy
4. **`misinformation.py`** — ưu tiên 314 luồng có tranh luận
5. **`eval/run_eval.py` + gắn nhãn tay 50 claim** — `gold_set.jsonl` đang có **1 dòng**. DIVISION.md: *"Không có con số này là mất điểm nặng"*

**Tất cả đều chờ `core/llm.py` (Nguyên) — hiện vẫn là stub 47 dòng, 4 `NotImplementedError`. DIVISION.md ghi deadline giờ 3.**
