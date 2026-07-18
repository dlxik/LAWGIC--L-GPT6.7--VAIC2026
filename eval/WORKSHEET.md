# Bàn gắn nhãn gold set — P3

> Sinh bởi `python scripts/make_worksheet.py` (seed cố định, chạy lại ra cùng danh sách).
> **Không sửa file này bằng tay** — nhãn điền vào `eval/gold_set.jsonl`.

## Cách làm

1. Mở `eval/gold_set.jsonl` cạnh file này. Mỗi dòng một claim, `claim_id` khớp mục bên dưới.
2. Với từng dòng, điền:
   - `expected_verdict`: `ACCURATE` | `PARTIALLY_INACCURATE` | `INACCURATE` | `UNVERIFIABLE`
   - `expected_citation`: node_id CÓ THẬT, vd `tncn2025-d7-k1`. Kiểm:
     `python scripts/show_law.py --check tncn2025-d7-k1`
   - `note`: vì sao — câu này chính là thứ trả lời BGK khi họ hỏi một ca cụ thể.
   - `text`: sửa lại thành câu claim đứng độc lập NẾU bình luận quá dài / nhiều claim.
     Đang điền sẵn nguyên văn để không ai cài quan điểm vào câu hỏi thi.
3. Xong chạy `python eval/check_gold.py` — soát node_id có thật, đủ nhãn, phân bổ có cân.

## Chỉ tiêu phân bổ (quan trọng hơn tổng số)

| Verdict | Cần | Vì sao |
|---|---|---|
| `INACCURATE` | ~15 | Nhãn chính, tin đồn thật |
| `PARTIALLY_INACCURATE` | ~15 | Lớp khó nhất — ca 505 triệu nằm đây |
| `ACCURATE` | ~10 | Chứng minh không phải cứ gắn "sai" là xong |
| `UNVERIFIABLE` | ~10 | Bỏ lớp này thì LLM ép hết vào 3 lớp kia |

Có 60 ứng viên cho mục tiêu 50 — **dư 10 để cân phân bổ**. Lớp nào đủ rồi thì
dòng thừa để `expected_verdict: "SKIP"`, `check_gold.py` sẽ bỏ qua.

Lấy ngẫu nhiên 50 cái sẽ ra ~40 `INACCURATE` — lúc đó một model đoán bừa
"INACCURATE" cho mọi thứ cũng đạt 80%, và cả bài eval vô nghĩa.

## Bẫy đã biết của đề tài thuế

- **`tncn2025-d7-k2` vs `k3` là hai cách tính KHÁC NHAU.** k2 (mặc định): thuế trên
  *thu nhập* (doanh thu − chi phí) × 15%. k3 (tuỳ chọn, ≤3 tỷ): thuế trên *phần
  doanh thu vượt* 500 triệu × 0,5–5%.
  → "doanh thu 505tr thì chỉ 5tr bị tính thuế" nói như quy tắc chung =
  `PARTIALLY_INACCURATE` (chỉ đúng nếu chọn k3).
  → "**nếu nộp theo doanh thu** thì chỉ nộp phần trên 500tr" = `ACCURATE` (đúng k3-a).
- **Tiền chậm nộp là LÃI, không phải PHẠT** (`LATE_PAYMENT_INTEREST`, 127 node —
  loại nhiều nhất). "Chậm nộp bị phạt" → `PARTIALLY_INACCURATE`, không phải `ACCURATE`.
- **Ngưỡng 500 triệu tính theo NĂM**, không phải tháng. "Bán 40tr/tháng chưa phải
  đóng thuế" = 480tr/năm → đúng, nhưng phải kiểm phép nhân.
- **Ý kiến ≠ claim.** "500 triệu quá thấp" là kiến nghị → không phải claim.
  Nếu bình luận không chứa claim nào, để `expected_verdict: "SKIP"`.
- **Nói về DỰ THẢO không phải luật hiện hành.** "200 triệu như dự định ban đầu"
  → `UNVERIFIABLE` (luật không nói về dự thảo), hoặc `SKIP`.



## Bản đồ điều luật (đọc một lần, dùng cho cả 60 claim)

Đây là vùng luật mà dư luận đã crawl đang bàn tới. Tra node khác:
`python scripts/show_law.py --grep "..."` · `python scripts/show_law.py tncn2025-d7`

**Ngưỡng miễn thuế**

- `tncn2025-d7-k1` — Điều 7 Khoản 1 109/2025/QH15<br>Cá nhân cư trú có hoạt động sản xuất, kinh doanh có mức doanh thu năm từ 500 triệu đồng trở xuống không phải nộp thuế thu nhập cá nhân. Chính phủ trìn…

**Cách tính MẶC ĐỊNH — trên thu nhập (doanh thu − chi phí)**

- `tncn2025-d7-k2` — Điều 7 Khoản 2 109/2025/QH15<br>Thuế thu nhập cá nhân đối với thu nhập từ kinh doanh của cá nhân cư trú có doanh thu năm trên mức quy định tại khoản 1 Điều này được xác định bằng thu…
- `tncn2025-d7-k2-a` — Điều 7 Khoản 2 Điểm a 109/2025/QH15<br>Thu nhập tính thuế được xác định bằng doanh thu của hàng hóa, dịch vụ bán ra trừ (-) đi chi phí liên quan đến hoạt động sản xuất, kinh doanh trong kỳ …
- `tncn2025-d7-k2-b` — Điều 7 Khoản 2 Điểm b 109/2025/QH15<br>Cá nhân kinh doanh có doanh thu năm trên mức quy định tại khoản 1 Điều này đến 03 tỷ đồng: thuế suất 15%;…
- `tncn2025-d7-k2-c` — Điều 7 Khoản 2 Điểm c 109/2025/QH15<br>Cá nhân kinh doanh có doanh thu năm trên 03 tỷ đồng đến 50 tỷ đồng: thuế suất 17%;…
- `tncn2025-d7-k2-d` — Điều 7 Khoản 2 Điểm d 109/2025/QH15<br>Cá nhân kinh doanh có doanh thu năm trên 50 tỷ đồng: thuế suất 20%. Thu nhập từ cho thuê bất động sản quy định tại khoản 4 Điều này không áp dụng cách…

**Cách tính TUỲ CHỌN — trên phần doanh thu vượt 500tr (chỉ khi ≤3 tỷ)**

- `tncn2025-d7-k3` — Điều 7 Khoản 3 109/2025/QH15<br>Cá nhân kinh doanh có doanh thu năm trên mức quy định tại khoản 1 Điều này đến 03 tỷ đồng được lựa chọn nộp thuế theo quy định tại điểm a và điểm b kh…
- `tncn2025-d7-k3-a` — Điều 7 Khoản 3 Điểm a 109/2025/QH15<br>Doanh thu tính thuế được xác định bằng phần doanh thu vượt trên mức quy định tại khoản 1 Điều này;…
- `tncn2025-d7-k3-b` — Điều 7 Khoản 3 Điểm b 109/2025/QH15<br>Phân phối, cung cấp hàng hoá: thuế suất 0,5%;…
- `tncn2025-d7-k3-c` — Điều 7 Khoản 3 Điểm c 109/2025/QH15<br>Dịch vụ, xây dựng không bao thầu nguyên vật liệu: thuế suất 2%. Riêng hoạt động cho thuê tài sản, đại lý bảo hiểm, đại lý xổ số, đại lý bán hàng đa cấ…
- `tncn2025-d7-k3-d` — Điều 7 Khoản 3 Điểm d 109/2025/QH15<br>Sản xuất, vận tải, dịch vụ có gắn với hàng hoá, xây dựng có bao thầu nguyên vật liệu: thuế suất 1,5%;…
- `tncn2025-d7-k3-e` — Điều 7 Khoản 3 Điểm e 109/2025/QH15<br>Hoạt động kinh doanh khác: thuế suất 1%.…

**Cho thuê bất động sản**

- `tncn2025-d7-k4` — Điều 7 Khoản 4 109/2025/QH15<br>Cá nhân cho thuê bất động sản, trừ hoạt động kinh doanh lưu trú, nộp thuế thu nhập cá nhân được xác định bằng phần doanh thu vượt trên mức quy định tạ…

**Hộ kinh doanh kê khai (luật MỚI)**

- `qlt2025-d13` — Điều 13 108/2025/QH15<br>…

**Thuế khoán (chỉ có ở luật CŨ — luật mới đã bỏ)**

- `qlt2019-d51` — Điều 51 38/2019/QH14<br>…

**Hoá đơn điện tử**

- `qlt2025-d26` — Điều 26 108/2025/QH15<br>…
- `qlt2019-d89` — Điều 89 38/2019/QH14<br>…

**Chậm nộp — là LÃI, không phải phạt**

- `qlt2025-d16` — Điều 16 108/2025/QH15<br>…
- `qlt2019-d59` — Điều 59 38/2019/QH14<br>…

**Cưỡng chế**

- `qlt2025-d48` — Điều 48 108/2025/QH15<br>…
- `qlt2025-d49` — Điều 49 108/2025/QH15<br>…
- `qlt2019-d132` — Điều 132 38/2019/QH14<br>…

## Danh sách claim

---

## g001  ·  `vne-59909332`  ·  34 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Doanh thu 1 tỷ cũng có người lãi 500 triệu nhưng cũng có người chỉ lãi 100 triệu tùy từng mặt hàng. Việc đánh thuế cho tất cả hàng quán cuối cùng người kinh doanh chả mất gì người tiêu dùng mới là người chịu.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59909332`

_Cụm từ trùng với_ `tncn2025-d7-k1` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g002  ·  `vne-59909839`  ·  7 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59908249`):
> Nên đánh thuế người giàu thay vì thuế người nghèo, giá chung cư q9 xa lắc lơ mở bán đã 100tr/m2 thì ai mua nổi? Việc áp dụng cách thuế mới sẽ chỉ làm giá cả tăng là ko tránh khỏi, người dân mua hàng cứ mặc định thời gian tới cộng thêm 5% vào giá
**Bình luận cần gắn nhãn:**
> Thuế hộ kinh doanh bình thường như quần áo, tạp hóa... chỉ 1.5% thôi nhé. Dịch vụ ăn uống mới 4.5%. Và trước giờ vẫn vậy

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59908249`

---

## g003  ·  `vne-59909969`  ·  29 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> Muốn hộ kinh doanh kết nối kê khai thuế mà cái phần mềm lại bắt phải mua. Chưa biết lãi lời như nào mà mỗi năm ít nhất mất chục triệu tiền hoá đơn.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59909969`

_Cụm từ trùng với_ `qlt2025-d13-k6`, `qlt2025-d24-k2-e`, `qlt2025-d45-k4-c`, `qlt2025-d25-k1-a`, `qlt2025-d8-k2`, `qlt2025-d6-k2` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g004  ·  `vne-59912059`  ·  19 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59908098`):
> Theo quan điểm của cá nhân tôi thì chỉ nên đánh thuế với những doanh nghiệp hay cty còn hộ kinh doanh chưa nên áp dụng vì hiện tại các hộ kinh doanh đa phần là buôn bán nhỏ lẻ
**Bình luận cần gắn nhãn:**
> Bạn hiểu thuế trên doanh thu là gì không? Ví dụ danh thu của bản 1 tỷ nhưng lợi nhuận chỉ 50tr. Tôi thu được có 50tr nhưng tôi phải đóng thuế cho 1 tỷ.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59908098`

---

## g005  ·  `vne-59914323`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59908723`):
> Với quán ăn và tạp hóa thì tỷ suất lợi nhuận họ thấp chứ ko cao, chủ yếu lấy công làm lời, lợi nhuận nhờ bán số nhiều, doanh thu 1 tỷ thì hết sức bình thường mà phải lên công ty thì đúng khổ, 1 ngày bán 100 tô bún 30k thì doanh thu 1 tỷ rồi nhưng lợi nhuận thực tế chưa chắc được 20% cho ít nhất 2 lao động trong nhà, nếu làm sổ sách kế toán ko đầy đủ thì lợi nhuận sổ sách có khi bị đẩy lên cực, tạp
**Bình luận cần gắn nhãn:**
> Mình ko nói chuyện ko đóng thuế hay trốn thuế. Mình đang nói doanh thu 1 tỷ là bắt buộc lập công ty, năm nay chưa bắt buộc, năm sau là bắt buộc.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59908723`

---

## g006  ·  `vne-59915084`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59908220`):
> Vậy là người dùng chịu chứ có phải người bán đâu nhỉ.
**Bình luận cần gắn nhãn:**
> Có vẻ bạn chưa nắm được tinh thân của thuế khoán và thuế không khoán. Các hộ doanh thu dưới 1 tỷ/năm thì đóng thuế khoán, trên 1 tỷ thì đóng thuế không khoán. Nếu doanh thu đã trên 1 tỷ rồi thì không còn nhỏ lẻ nữa đâu bạn.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59908220`

_Cụm từ trùng với_ `qlt2019-d51-k4`, `qlt2019-d51-k2`, `qlt2019-d51-k1`, `qlt2019-d44-k2-c`, `qlt2019-d51-k3` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g007  ·  `vne-59918049`  ·  0 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Cho đóng thuế khoán tự khai, muốn khai bao nhiêu thì khai quá dễ dàng và quá nhẹ nhàng, giờ tính thuế theo doạnh thu có 1,5% thì cho là cao. Có mất khách hàng hay không là do mình, mình không lợi dụng tăng giá thì khách hàng mất đi đâu?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59918049`

_Cụm từ trùng với_ `qlt2019-d51-k4`, `qlt2019-d51-k2`, `qlt2019-d51-k1`, `qlt2019-d44-k2-c`, `qlt2019-d51-k3` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g008  ·  `vne-59918245`  ·  3 like  ·  rổ C·mơ hồ
**Ngữ cảnh — bình luận gốc** (`vne-59908098`):
> Theo quan điểm của cá nhân tôi thì chỉ nên đánh thuế với những doanh nghiệp hay cty còn hộ kinh doanh chưa nên áp dụng vì hiện tại các hộ kinh doanh đa phần là buôn bán nhỏ lẻ
**Bình luận cần gắn nhãn:**
> Thi bây giờ cũng thu theo doanh thu bạn bán được chứ có thu hơn hay tăng thuế suất gì đâu? Ok chua?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59908098`

_Cụm từ trùng với_ `tncn2025-d20-k3`, `tncn2025-d7-k3-e`, `tncn2025-d7-k3-b`, `tncn2025-d7-k2-c`, `tncn2025-d7-k3-d`, `tncn2025-d7-k2-b` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g009  ·  `vne-59918449`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59909694`):
> Nhà tôi bán sữa, tả cho tre em, một lon sữa gần 1 triệu nhưng lời vài chục ngàn chứ đâu nhiều, còn tiền thuê nhà, điện nước, tiền nhân công... vậy lời được bao nhiêu mà tính VAT trên doanh thu? Tính thuế vậy thì người bán hàng làm công không af?
**Bình luận cần gắn nhãn:**
> Quy luật thị truờng là thế từ ngàn năm nay rồi bạn ! mà nói thật nêu kd có doanh thu dưói 1 tỷ thì chỉ cần từ 1 đến 2 lao động , và nguồn lọi đem lại đủ cho họ sống , tất nhiên họ không thể làm theo kiểu mua đầu chọ bán cuối chợ mà phài có kỹ năng kd dể cạnh tranh .

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59909694`

---

## g010  ·  `vne-59925565`  ·  30 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> Còn khấu trừ thuế đầu vào như thế nào? Một hộ kinh doanh bán cho hộ khác kinh doanh tiếp theo, nếu không được khấu trừ thuế đầu vào thì là thuế chồng thuế? Thuế thu nhập tính trên doanh thu chưa khấu trừ chi phí đã là hợp lý chưa?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925565`

---

## g011  ·  `vne-59926350`  ·  6 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-59925147`):
> Má tôi có sạp rau nhỏ lẻ cạnh chợ bán nửa ngày có phải kê khai nộp thuế ko nhỉ?
**Bình luận cần gắn nhãn:**
> có đăng ký kinh doanh là phải kê khai thuế hết. Đóng thuế môn bài hàng năm. Ngoài ra DOANH THU >100tr/1 năm (tương đương >273.972đ/ ngày) là đóng thêm thuế GTGT và thuế TNCN rồi. ở đâu ra mức 1tr/ ngày thế

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925147`

_Cụm từ trùng với_ `qlt2025-d13-k6`, `qlt2025-d24-k2-e`, `qlt2025-d45-k4-c`, `qlt2025-d25-k1-a`, `qlt2025-d8-k2`, `qlt2025-d6-k2` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g012  ·  `vne-59926477`  ·  5 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59925675`):
> Với doanh thu từ 100 triệu đồng/năm thì lợi nhuận là bao nhiêu mà phải nộp thuế thu nhập cá nhân nhỉ.
**Bình luận cần gắn nhãn:**
> doanh thu 100tr/năm bắt buộc phải đóng 1,5% thuế GTGT và TNCN (tối thiểu khoảng hơn 200k/tháng) + ít nhất 300k thuế môn bài/năm mà không cần quan tâm lợi nhuận bao nhiêu. Thực tế ra nhiều HKD trừ các chi phí ra thu nhập còn thấp hơn đi làm công ty mà nhiều người đâu có biết

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925675`

---

## g013  ·  `vne-59926702`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59924937`):
> Khi phát hiện vụ việc hàng giả, hàng nhái, hàng kém chất lượng thì ai cũng phẫn nộ. Nhưng khi bị kiểm tra lại bảo hàng tôi mua trôi nổi, làm gì có hóa đơn, tôi bán cho người nghèo nên hàng chỉ được như vậy.
**Bình luận cần gắn nhãn:**
> Bán hàng thật, đúng giá ( có hoá đơn chứng từ, có nguồn gốc xuất sứ hẳn hoi) thì với mức lương bình quân chỉ 8,7 triệu đồng/tháng xin lỗi chỉ có nhịn chi tiêu thôi, hàng hoá thật đó ế ẩm hết.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59924937`

---

## g014  ·  `vne-59926966`  ·  16 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-59925380`):
> tôi còn trẻ, ăn học đầy đủ, nhưng đọc văn bản của ngành thuế với các từ ngữ chuyên ngành còn cảm thấy đau đầu, khó hiểu. rồi tìm về 7 loại sổ sách kế toán là thấy thua rồi. ngành thuế cần hướng dẫn cụ thể (theo kiểu cầm tay chỉ việc) chứ đừng nói chung chung, chả biết đường nào mà làm cho đúng cả
**Bình luận cần gắn nhãn:**
> vde là thu thuế theo doanh thu, mà có khi họ đang gồng lỗ. Ví dụ nhà hàng doanh thu 200tr/tháng. Mà mặt bằng, nhân viên, điện nước có khi còn lỗ, giờ thêm thuế trên doanh thu thì họ sống sao

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925380`

---

## g015  ·  `vne-59927311`  ·  1 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59916141`):
> Hộ kinh doanh lo chỉ là vin cớ thôi. Cụ thể 1 tô phở 50k, thì phải nộp 750 đồng (1,5% giá tô phở), trong đó khách chịu 500 đồng, chủ quán chịu 250 đồng, vậy thì có đáng lo không. Tăng 500 đồng/tô để nộp thuế có hạn chế khách hàng đến ăn ko?
**Bình luận cần gắn nhãn:**
> 1.5% cho rau, 1.5% cho gia vị, 1.5% cho gas, 1.5% cho vắt phở. 1.5% 1.5% thịt ... vv để tạo ra một tô phở người bán phở đã phải chịu 1 đống thuế khác nhau. giá tăng 5ngàn-10ngàn để bù vào thuế là ít rồi. thử kinh doanh đi rồi biết.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59916141`

---

## g016  ·  `vne-59927468`  ·  0 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-59925147`):
> Má tôi có sạp rau nhỏ lẻ cạnh chợ bán nửa ngày có phải kê khai nộp thuế ko nhỉ?
**Bình luận cần gắn nhãn:**
> Ai bảo thu nhập dưới 100tr ko phải nộp thuế vậy bạn?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925147`

---

## g017  ·  `vne-59927679`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59925380`):
> tôi còn trẻ, ăn học đầy đủ, nhưng đọc văn bản của ngành thuế với các từ ngữ chuyên ngành còn cảm thấy đau đầu, khó hiểu. rồi tìm về 7 loại sổ sách kế toán là thấy thua rồi. ngành thuế cần hướng dẫn cụ thể (theo kiểu cầm tay chỉ việc) chứ đừng nói chung chung, chả biết đường nào mà làm cho đúng cả
**Bình luận cần gắn nhãn:**
> Thúng xôi, quầy bánh mà doanh thu 1tỷ/năm thì cũng nên tìm hiểu cách làm đi.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925380`

---

## g018  ·  `vne-59928193`  ·  5 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-59925264`):
> Thực tế như thế này là công bằng cho tất cả mọi người. Hộ kinh doanh xưa nay có thể hưởng lợi bởi chính sách cũ thì giờ phải thay đổi. Như người đi làm công ăn lương ở công ty, thường thì sẽ bị thu thuế trước khi nhìn thấy tiền lương. Nên nhiều lúc tưởng đi làm công ty là thu nhập cao nhưng quay lại không bằng một người bán xôi, hay vàng mã. Có bất cập thì xử lý thôi, xã hội mới phát triển được.
**Bình luận cần gắn nhãn:**
> Ngta ví dụ để bạn hình dung 100tr doanh thu phải mất 1tr5 tiền thuế, trong khi lời lãi bn ko biết.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59925264`

---

## g019  ·  `vne-59956782`  ·  19 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59954867`):
> Cái vấn đề ở đây là không rõ ràng giữa "doanh thu" và "thu nhập". Tiểu thương chủ yếu bán số lượng lấy lời nhỏ lẻ, vốn 100 lời 2-3, thuế lấy mất 1.5 thì sao mà chịu nổi
**Bình luận cần gắn nhãn:**
> Tạp hoá bỏ ra 85 triệu/ tháng lời 8,5 triệu, đóng thuế 1,5 triệu. 1 người bán thì chạy tối mặt luôn. Trải cảnh đó rồi nói nhé bạn.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59954867`

---

## g020  ·  `vne-59956945`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59955199`):
> Người lớn tuổi ở mức ko rành thiết bị công nghệ mà đang làm chủ một cơ sở KD với doanh thu trung bình hơn 1 tỷ đồng/năm tương đương trên dưới 85tr/tháng thì thực sự nên yêu cầu họ phải làm cho bằng được. Kiếm được cỡ đó tiền thì chắc chắn đủ thông minh, logic để nắm bắt các thủ thuật thao tác hết sức cơ bản như này. Hãy thử khảo sát xem bao nhiêu người lớn tuổi trên 60 đang có cơ sở KD với thu nhậ
**Bình luận cần gắn nhãn:**
> Doanh thu 85tr/tháng chư không phải thu nhập. Thu nhập chắc cỡ 20%, cao là 30% thì cũng chỉ được 17-25 tr/ thì sao gọi là thu nhập cao?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59955199`

---

## g021  ·  `vne-59969149`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-59955199`):
> Người lớn tuổi ở mức ko rành thiết bị công nghệ mà đang làm chủ một cơ sở KD với doanh thu trung bình hơn 1 tỷ đồng/năm tương đương trên dưới 85tr/tháng thì thực sự nên yêu cầu họ phải làm cho bằng được. Kiếm được cỡ đó tiền thì chắc chắn đủ thông minh, logic để nắm bắt các thủ thuật thao tác hết sức cơ bản như này. Hãy thử khảo sát xem bao nhiêu người lớn tuổi trên 60 đang có cơ sở KD với thu nhậ
**Bình luận cần gắn nhãn:**
> Thì bạn cứ giải thích với bên thuế như thế thôi, lúc họ tìm đến mà ko có hoá đơn đầu vào/đầu ra thì giải thích với họ như thế, cần gì phải đóng cửa hay khóc lóc Tôi mua bia uống thì quan tâm gì bên bán lãi lỗ thế nào. 2 người cùng bán bia, người A lãi 5-7% nhưng người B chưa chắc. Có thể bán bia giả lãi 50-70% cũng nên

_Đọc cả luồng:_ `python scripts/show_thread.py vne-59955199`

---

## g022  ·  `vne-61406451`  ·  65 like  ·  rổ B·ngưỡng
**Bình luận cần gắn nhãn:**
> Nếu doanh thu 1 năm 200tr thì chỉ cần ngày bán hơn 500k đã phải nộp thuế rồi. Lợi nhuận giả sử 10% thì mới là 50k/ngày

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61406451`

---

## g023  ·  `vne-61406501`  ·  759 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> 200 tr/1 năm = 555k/ ngày doanh thu , chưa tính đến công sức bỏ ra , tiền điện , tiền nước , chi phí mặt bằng .... Còn lãi được bao nhiêu ? Haizzz . Đi làm công ty cho đỡ mệt đầu .

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61406501`

---

## g024  ·  `vne-61407664`  ·  69 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Ông nào đề xuất ra con số 200tr này đúng là đỉnh thiệt. Vậy tính ra doanh thu khoảng 555k 1 ngày, lợi nhuận khoảng 20-30% thì mỗi ngày lời hơn 100k-150k, mỗi tháng kiếm chưa được 5 triệu mà đã đóng thuế ròi trong khi mức giảm trừ gia cảnh chuẩn bị lên 15,5 triệu

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61407664`

---

## g025  ·  `vne-61408095`  ·  8 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> Tui rất muốn thuê một mặt bằng nhỏ bán ăn, uống nhưng thực tế thấy những quy định, chính sách luôn đổi thay, thậm chí khó thực hiện nên thôi, làm thợ đụng, ai cần mình làm, đắp đổi qua ngày cho nhẹ đầu .

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61408095`

---

## g026  ·  `vne-61409583`  ·  11 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61406501`):
> 200 tr/1 năm = 555k/ ngày doanh thu , chưa tính đến công sức bỏ ra , tiền điện , tiền nước , chi phí mặt bằng .... Còn lãi được bao nhiêu ? Haizzz . Đi làm công ty cho đỡ mệt đầu .
**Bình luận cần gắn nhãn:**
> Bán đc 500k 1 ngày ko biết lãi nổi 200k ngày bằng lương công nhân 6 triệu 1 tháng chưa nữa mà bắt nộp thuế chi ko biết ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61406501`

---

## g027  ·  `vne-61549346`  ·  4 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61545151`):
> Thêm gánh nặng chi phí và sức lực, gây ra tâm trạng hoang mang với hộ kinh doanh nhỏ vốn đã rất vất vả. :(
**Bình luận cần gắn nhãn:**
> Kinh doanh vì lợi nhuận. Thử hỏi khi đã tốn 10% thuế nhập đầu vào bắt buộc thì họ sẽ làm gì để vẫn còn lợi nhuận?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61545151`

---

## g028  ·  `vne-61662094`  ·  19 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61662018`):
> Cứ cho rằng mức lãi "đáng mơ ước" 20% đi chăng nữa thì doanh thu 500Tr cũng chỉ mang lại thu nhập 100Tr/năm thấp hơn mức phải nộp thuế của người hưởng lương rất nhiều.
**Bình luận cần gắn nhãn:**
> 100Tr/năm thấp hơn mức phải nộp thuế của người hưởng lương rất nhiều là sao bạn ? mình ko hiểu ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662018`

---

## g029  ·  `vne-61662207`  ·  86 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Thôi cứ chốt 100tr/ tháng tính ra là 1 tỉ 2/ năm. Qua mốc đó rồi hãy bàn tới việc thu thuế của họ. Bởi vì lợi nhuận kinh doanh lãi vốn dao động có thể từ 10% đến 20%. Rồi còn chưa kể chi phí thuê mặt bằng, nhân công, điện nước, thời gian làm kinh doanh ( có thể trên 8h/ ngày so với lao động đi làm thuê).

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662207`

---

## g030  ·  `vne-61662238`  ·  185 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61662018`):
> Cứ cho rằng mức lãi "đáng mơ ước" 20% đi chăng nữa thì doanh thu 500Tr cũng chỉ mang lại thu nhập 100Tr/năm thấp hơn mức phải nộp thuế của người hưởng lương rất nhiều.
**Bình luận cần gắn nhãn:**
> là doanh thu 500tr lãi chỉ được 100tr còn đi làm thì mức thu nhập không chịu thuế là 15.5*12 = 186tr . Nói đến đây chắc bạn hiểu rồi nhỉ ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662018`

---

## g031  ·  `vne-61662309`  ·  101 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Doanh thu 200 triệu một năm, tương đương 16.6 triệu/ tháng bao gồm giá vốn, chi phí mặt bằng , này còn ai mở ra buôn bán kinh doanh nhỏ lẻ nữa

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662309`

---

## g032  ·  `vne-61663454`  ·  2 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61662208`):
> Ngưỡng 500tr là hợp lý. Thấp hơn người dân không có động lực để kinh doanh, mức 200tr nói thẳng ra thì chỉ lấy công làm lời, đóng thuế nữa là mất luôn 1 nửa tiền công. Giống như bạn đi làm chịu thế 50% thu nhập.
**Bình luận cần gắn nhãn:**
> Tháng nào cũng đóng 1,5% trên doanh thu đây này bạn. Mình bán nhiều chỗ, có sàn mỗi tháng được 8tr vẫn tự trừ thuế trên từng đơn hàng dù chưa biết mình có đạt doanh thu 100tr 1 năm không này.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662208`

---

## g033  ·  `vne-61663562`  ·  8 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61662018`):
> Cứ cho rằng mức lãi "đáng mơ ước" 20% đi chăng nữa thì doanh thu 500Tr cũng chỉ mang lại thu nhập 100Tr/năm thấp hơn mức phải nộp thuế của người hưởng lương rất nhiều.
**Bình luận cần gắn nhãn:**
> Giả sử người làm công ăn lương phải thu nhập 15tr 1 tháng mới chịu thuế trong khi hộ kinh doanh doanh thu 500tr 1 năm cho là lãi 10% nghĩa là 1 năm lãi có 50t chưa nổi 5tr /tháng chưa tính chi phí đã phải chịu thuế. Trong khi phải lo nhiều rồi vốn, rủi do. Điều này sẽ đẩy rất nhiều hộ kd phá sản không thể trụ nổi

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61662018`

---

## g034  ·  `vne-61688868`  ·  1 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61688481`):
> Hộ kinh doanh làm đỉnh cao lắm thì lời khoảng 20% là cùng rồi, vì thu nhập trên 11tr/tháng là phải đóng thuế, suy ra doanh thu 55tr/tháng mới được thu nhập 11tr/tháng, suy ra doanh thu 1 năm trên 660tr mới phải đóng thuế, nếu ngưỡng thu thuế, dưới mức này thì chẳng ai làm hộ kinh doanh làm gì cả, vì tôi nhắc lại 1 lần nữa được bao nhiêu hộ kinh doanh lời 20%/tháng??. Nếu lạm phát dẫn đến thu nhập 
**Bình luận cần gắn nhãn:**
> hộ kinh doanh nhỏ lẻ thì lời trung bình khoảng 15% đến 35% trên doanh thu, cái khó ở đây là kiểm soát được đầu vào va đầu ra để tính doanh thu.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61688481`

---

## g035  ·  `vne-61714445`  ·  3 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61714254`):
> Có bác nào hiểu cho 1 cái ví dụ cụ thể nhé. Cảm ơn
**Bình luận cần gắn nhãn:**
> Vd bác kinh doanh lãi 100tr/năm thì nộp 15% tương đương 15tr đó là áp dụng cho hộ kd có doanh thu dưới 3ty(nghĩa là cả lãi +gốc)

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61714254`

---

## g036  ·  `vne-61716100`  ·  2 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Sau khi DOANH THU - CHI PHÍ BÁN HÀNG vừa xong thì bị mất 15%, nhưng chưa trừ các chi phí sinh hoạt, gia cảnh!?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61716100`

---

## g037  ·  `vne-61745905`  ·  0 like  ·  rổ C·mơ hồ
**Ngữ cảnh — bình luận gốc** (`vne-61714309`):
> Giữ thuế như 2024 về trước đi. Cty thì hóa đơn. Kinh doanh nhỏ lẻ, chợ thì thuế khoán. Khuyến khích dân tự kinh doanh. Còn kiểu thuế trên lợi nhuận hay doanh thu thì chỉ làm cuộc sống của tất cả người dân khó khăn nhà nước lại phải trợ cấp. Vừa gây bức xúc cho người dân kinh doanh đã mệt mỏi mới đủ sống lại mất thời gian vào giấy tờ sổ sách hay máy móc ghi hóa đơn
**Bình luận cần gắn nhãn:**
> Quan trọng đa phần các hộ kinh doanh hay người bán hàng đang bán phá giá. sản phẩm đáng nhé 900k giá gốc phải bán thành 950k thì người bán họ bán có 910-920k thì lấy đâu tiền đóng thuế

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61714309`

---

## g038  ·  `vne-61748042`  ·  4 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61746334`):
> 500 vẫn là mức rất thấp bởi cứ cho tỷ suất lợi nhuận đáng mơ ước là 5% thì lợi nhuận tính ra cũng chỉ 25 triệu/năm đã phải tính toán kê khai và đóng thuế là chưa hợp lý
**Bình luận cần gắn nhãn:**
> Đúng rồi. Nếu doanh thu 501 triêu, thì chỉ phải đóng thuế 5% của 1 triệu vượt ngưỡng thôi.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61746334`

---

## g039  ·  `vne-61748611`  ·  4 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61747043`):
> Nếu tính đúng, tính đủ thì 500 triệu một năm tức là doanh thu bình quân chưa đến 42 triệu một tháng. Nếu lời bình quân 20% thì cũng chỉ thu nhập được 8,4 triệu một tháng cho một hộ gia đình kinh doanh, còn thua xa thu nhập của một người lao động bình thường thì phải chịu nộp thuế nữa thì người ta sống như thế nào ???
**Bình luận cần gắn nhãn:**
> 500 là ngưỡng đóng thuế. Có nghĩa là 499 triệu là mức chưa chịu thuế. Nếu bạn KD từ 600tr thì là 600-500=100*1.5% Nghĩa là 1.5tr nếu vượt, cái cần xác định không phải là 500 mà là tại sao lại là 500 chứ ko phải là 200 hay 800?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61747043`

---

## g040  ·  `vne-61748882`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61747094`):
> Mọi người nói nhiều đến ngưỡng chịu thuế mà quên đi rằng mức đóng thuế 5~7% doanh thu cho ngành ăn uống, dịch vụ là rất nhiều, chỉ nên ở mức 0.5~1.5%.
**Bình luận cần gắn nhãn:**
> 7% là do có cộng 5% VAT thôi (thuế này phải tính vào giá bán, người dùng cuối trả) còn TNCN chỉ là 2%

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61747094`

---

## g041  ·  `vne-61748892`  ·  3 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61746334`):
> 500 vẫn là mức rất thấp bởi cứ cho tỷ suất lợi nhuận đáng mơ ước là 5% thì lợi nhuận tính ra cũng chỉ 25 triệu/năm đã phải tính toán kê khai và đóng thuế là chưa hợp lý
**Bình luận cần gắn nhãn:**
> Lãi 5% nhưng nó là 5% trên số vốn và vốn thì quay vòng cụ ạ. Ví dụ người ta có vốn 100 triệu thì doanh thu 1 tháng có khi đã 150 triệu rồi và nó lãi trên 150 triệu đó. Gửi ngân hàng mà được thế à???

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61746334`

---

## g042  ·  `vne-61749518`  ·  1 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61747043`):
> Nếu tính đúng, tính đủ thì 500 triệu một năm tức là doanh thu bình quân chưa đến 42 triệu một tháng. Nếu lời bình quân 20% thì cũng chỉ thu nhập được 8,4 triệu một tháng cho một hộ gia đình kinh doanh, còn thua xa thu nhập của một người lao động bình thường thì phải chịu nộp thuế nữa thì người ta sống như thế nào ???
**Bình luận cần gắn nhãn:**
> doanh thu bắn ăn uống 1ty/năm thì lời ít nhất cũng 400t rồi, mặt hàng ăn uống là lợi nhuận cao lắm đó, đâu 20% đâu. nên bạn tính như vậy không đúng thực tế à.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61747043`

---

## g043  ·  `vne-61749760`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61746334`):
> 500 vẫn là mức rất thấp bởi cứ cho tỷ suất lợi nhuận đáng mơ ước là 5% thì lợi nhuận tính ra cũng chỉ 25 triệu/năm đã phải tính toán kê khai và đóng thuế là chưa hợp lý
**Bình luận cần gắn nhãn:**
> Chạy xe ôm công nghệ doanh thu trên áp từ 100 triệu trở lên là phải đóng 1,5% thuế rồi đó bạn. Trừ chi phí hao mòn xe, xăng nhớt tầm 30% thì chỉ còn có 70tr. (99.999.999 thì không đóng thuế, 100tr là đóng 1,5tr, các hãng xe công nghệ trừ tiền trong tk tài xế nộp thay)

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61746334`

---

## g044  ·  `vne-61750054`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61746334`):
> 500 vẫn là mức rất thấp bởi cứ cho tỷ suất lợi nhuận đáng mơ ước là 5% thì lợi nhuận tính ra cũng chỉ 25 triệu/năm đã phải tính toán kê khai và đóng thuế là chưa hợp lý
**Bình luận cần gắn nhãn:**
> 5% trên doanh thu, khác với 5% vốn bỏ ra bạn. Tạo được lợi nhuận 5% trên doanh thu là điều cũng ko phải dễ đâu.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61746334`

---

## g045  ·  `vne-61750765`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61747274`):
> Doanh thu 500 triệu/năm tương đương khoảng 42 triệu/tháng. Với lãi suất bình quân/doanh thu là 16% thì thu nhập bình quân của cơ sở kinh doanh là 6,8 triệu/tháng. Như vậy nếu từ năm 2026 mức thu nhập phải chịu thuế của người lao động là từ 15,5 triệu/tháng trong khi thu nhập của một cơ sở kinh doanh phải chịu thuế là từ 6,8 triệu/tháng là chưa hợp lý.
**Bình luận cần gắn nhãn:**
> Kinh doanh ngành gì? Mà có lãi đến 16%/ doanh thu? Tôi kd cũng chưa được 10% bạn ơi

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61747274`

---

## g046  ·  `vne-61751689`  ·  1 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61747043`):
> Nếu tính đúng, tính đủ thì 500 triệu một năm tức là doanh thu bình quân chưa đến 42 triệu một tháng. Nếu lời bình quân 20% thì cũng chỉ thu nhập được 8,4 triệu một tháng cho một hộ gia đình kinh doanh, còn thua xa thu nhập của một người lao động bình thường thì phải chịu nộp thuế nữa thì người ta sống như thế nào ???
**Bình luận cần gắn nhãn:**
> Nếu bạn làm không hơn được 500tr để đóng thuế thì bạn chỉ đủ ăn

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61747043`

---

## g047  ·  `vne-61771112`  ·  38 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61769838`):
> Hộ kd không tính thuế theo lợi nhuận được đâu, rất phức tạp. Nên tính thuế theo doanh thu. Mức tính thuế từ 2 tỷ trở lên và thuế suất thấp xuống.
**Bình luận cần gắn nhãn:**
> Bắt buộc in hóa đơn và tính thuế trên từng sản phẩm bán ra! Tại sao chạy xe công nghệ đều phải đóng thuế trên từng cuốc xe mà hộ kinh doanh đòi mức doanh thu chịu thuế 500 triệu trở lên??

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61769838`

_Cụm từ trùng với_ `tncn2025-d7-k1` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g048  ·  `vne-61771743`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61770261`):
> Với lãi suất 10%/doanh thu thì để có thu nhập 15,5 triệu/tháng, hộ kinh doanh phải đạt doanh thu 1,55 tỉ/tháng, tương đương 1,86 tỉ/năm. Như vậy mức doanh thu/năm hợp lý mà hộ kinh doanh phải chịu thuế là từ 1,8 tỉ/năm.
**Bình luận cần gắn nhãn:**
> "Với lãi suất 10%/doanh thu thì để có thu nhập 15,5 triệu/tháng, hộ kinh doanh phải đạt doanh thu 1,55 tỉ/tháng, tương đương 1,86 tỉ/năm" Nhân chia sai be bét vậy sao mà làm kê khai thuế được ! :') :')

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61770261`

_Cụm từ trùng với_ `qlt2025-d13-k6`, `qlt2025-d24-k2-e`, `qlt2025-d45-k4-c`, `qlt2025-d25-k1-a`, `qlt2025-d8-k2`, `qlt2025-d6-k2` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g049  ·  `vne-61772525`  ·  12 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61769838`):
> Hộ kd không tính thuế theo lợi nhuận được đâu, rất phức tạp. Nên tính thuế theo doanh thu. Mức tính thuế từ 2 tỷ trở lên và thuế suất thấp xuống.
**Bình luận cần gắn nhãn:**
> Vì chay xe công nghệ tỷ lệ lợi nhuận trên doanh thu cao! Một đồng vốn có khi 2 đồng lãi! Còn bán lẻ như hộ kinh doanh thì 100 đồng vốn chỉ lãi 5 đồng, có khi hoà vốn, hoặc lỗ!

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61769838`

---

## g050  ·  `vne-61772566`  ·  8 like  ·  rổ C·mơ hồ
**Ngữ cảnh — bình luận gốc** (`vne-61769838`):
> Hộ kd không tính thuế theo lợi nhuận được đâu, rất phức tạp. Nên tính thuế theo doanh thu. Mức tính thuế từ 2 tỷ trở lên và thuế suất thấp xuống.
**Bình luận cần gắn nhãn:**
> xe công nghệ là tập đoàn lớn, doanh thu cả hàng ngàn tỷ, thì đóng thuế trên từng cuốc xe là đúng rồi

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61769838`

---

## g051  ·  `vne-61785881`  ·  1 like  ·  rổ C·mơ hồ
**Ngữ cảnh — bình luận gốc** (`vne-61771582`):
> Nhà tôi bán tạp hoá tại Từ Liêm, doanh thu hiện khoảng 3.6 tỷ/ năm và đang dùng thuế khoán, với dự thảo thuế mới thu 15% trên lơi nhuận+chi phí nhân công+điện,nc+chi phí thuê CH nhà tôi chắc chắn sẽ đóng cửa !
**Bình luận cần gắn nhãn:**
> Mặt bằng và nhân công là hai chi phí lới nhất . nếu thu trừ chi không đủ lấy gì đóng thuế . mà tăng giá quá cao ít khách hàng cũng phải đóng cửa . giới trẻ giờ quá khổ kỳ vọng của gia đình dòng họ

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61771582`

---

## g052  ·  `vne-61799239`  ·  0 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61770838`):
> Ngưỡng miễn thuế 500 triệu/năm cho hộ kinh doanh vẫn chưa hợp lý. Với biên lợi nhuận trung bình khoảng 10%, doanh thu 500 triệu tương đương lợi nhuận khoảng 50 triệu/năm. Trong khi người làm công ăn lương được miễn tới 186 triệu/năm chưa kể giảm trừ gia cảnh. Nếu căn cứ theo mức miễn thuế TNCN hiện hành để đảm bảo công bằng, ngưỡng phù hợp cho hộ kinh doanh phải vào khoảng 2 tỷ đồng/năm thì mới tư
**Bình luận cần gắn nhãn:**
> đọc hết các bình luận thấy bác này cùng ý kiến với em nhất. làm sao cho cân bằng với ngưỡng thu nhập tối thiểu chịu thuế là 17tr/ tháng đổ lên thì ít nhất cũng phải có doanh thu 2 tỷ/ năm rồi

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61770838`

---

## g053  ·  `vne-61829144`  ·  0 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61746334`):
> 500 vẫn là mức rất thấp bởi cứ cho tỷ suất lợi nhuận đáng mơ ước là 5% thì lợi nhuận tính ra cũng chỉ 25 triệu/năm đã phải tính toán kê khai và đóng thuế là chưa hợp lý
**Bình luận cần gắn nhãn:**
> Doanh thu 1 tháng là 150 triệu thì tổng doanh thu cả năm sẽ cỡ 150 x 12 triệu, là 1 tỷ 8 rồi còn gì.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61746334`

---

## g054  ·  `vne-61853489`  ·  203 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Ngưỡng 500 triệu/năm có vẻ hơi thấp, nhiều hộ kinh doanh nhỏ lẻ có thể gặp khó khăn khi phải nộp thuế dù lợi nhuận không đáng kể. Hy vọng sau một thời gian áp dụng cơ quan chức năng xem xét mức phù hợp hơn để hỗ trợ nhóm kinh doanh siêu nhỏ.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61853489`

_Cụm từ trùng với_ `tncn2025-d7-k1` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g055  ·  `vne-61854127`  ·  96 like  ·  rổ A·ngẫu nhiên
**Ngữ cảnh — bình luận gốc** (`vne-61853440`):
> Tôi thấy mức 500 triệu chưa hợp lý
**Bình luận cần gắn nhãn:**
> 500tr/năm thì lợi nhuận phải tầm ít nhất 40% sau khi trừ chi phí mặt bằng , điện nước.....chia ra thu nhập mỗi tháng mới đc 15.5tr tức mức thu nhập ko phải nộp thuế. Hộ KD hay mô hình nào đạt mức lợi nhuận 40% ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61853440`

---

## g056  ·  `vne-61854208`  ·  8 like  ·  rổ A·ngẫu nhiên
**Bình luận cần gắn nhãn:**
> Hơi mù mờ chỗ này. Nếu doanh thu dưới 500 triệu thì mình cần làm gì? 1. Không cần khai? 2. Khai nhưng không cần đóng (với xác nhận là không hơn 500 triệu) ? 3. Khai, đóng và cuối năm làm hoàn thuế? Điều này khá khó vì hoàn thuế lâu.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61854208`

_Cụm từ trùng với_ `tncn2025-d7-k1` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g057  ·  `vne-61854247`  ·  1 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> Nhà tôi 2 vc nuôi 2 con; 1 đứa học đại học công thành phố khác, 1 đứa học cấp 2 trường công, 501tr đóng xong thuế không biết lấy cái gì trả tiền thuê nhà luôn.

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61854247`

---

## g058  ·  `vne-61855929`  ·  2 like  ·  rổ B·ngưỡng
**Ngữ cảnh — bình luận gốc** (`vne-61853440`):
> Tôi thấy mức 500 triệu chưa hợp lý
**Bình luận cần gắn nhãn:**
> 500 triệu lợi nhuận chứ không phải tổng doanh thu

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61853440`

_Cụm từ trùng với_ `tncn2025-d7-k1` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.

---

## g059  ·  `vne-61857070`  ·  3 like  ·  rổ C·mơ hồ
**Bình luận cần gắn nhãn:**
> Tôi thắc mắc: Ví dụ. Một hộ kinh doanh bán Phở, trong đó các nguyên liệu như mì chính, mắm, muối, điện, nước, thịt và các nguyên liệu khác có thể đã có thuế VAT khi nhập về rồi. Vậy tại sao khi bán ra 1 tô phở lại phải chịu thêm thuế VAT lần nữa ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61857070`

---

## g060  ·  `vne-61865485`  ·  1 like  ·  rổ B·ngưỡng
**Bình luận cần gắn nhãn:**
> Tôi xin hỏi . Những hộ bán trên 500tr. gỉa sử 1 tỷ 2 năm thì có được trừ đi 500tr miễn thuế , còn lại 700 triệu vượt mới phải đóng thuế phải không ạ ?

_Đọc cả luồng:_ `python scripts/show_thread.py vne-61865485`

_Cụm từ trùng với_ `qlt2025-d19-k4`, `qlt2025-d19-k1`, `qlt2025-d19-k4-b`, `tncn2025-d3`, `tncn2025-d1`, `qlt2025-d19-k4-a` — gợi ý thô, KHÔNG phải đáp án. Xem bản đồ ở trên.
