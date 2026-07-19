# LAWGIC — Lời thoại demo (đọc thẳng từng chữ)

> **Cách dùng:** phần **[TRONG NGOẶC ĐẬM]** = việc bạn LÀM (bấm/gõ). Phần chữ thường = bạn **ĐỌC nguyên văn**. Đọc thong thả, tự tin.
> Chuẩn bị: mở sẵn Tab web (`localhost:8000`, tab Cảnh báo) + Tab Neo4j Browser (đã Connect, dán sẵn Cypher). Chế độ Khách.

---

**[Bắt đầu quay — màn hình đang ở tab "Cảnh báo hiểu nhầm"]**

Xin chào ban giám khảo. Từ ngày mùng 1 tháng 7 năm 2026, luật thuế đối với hộ kinh doanh thay đổi rất lớn. Trong giai đoạn giao thời này, người dân rất dễ hiểu sai, và những hiểu lầm đó lan cực nhanh trên mạng xã hội. LAWGIC nối hai luồng dữ liệu — văn bản luật và dư luận xã hội — trên cùng một đồ thị tri thức, để tự động phát hiện và định chính.

**[Nhấn vào cảnh báo màu đỏ mức HIGH đầu tiên — "Thu nhập 120 triệu…"]**

Đây là một hiểu nhầm hệ thống đang cảnh báo: "Thu nhập một trăm hai mươi triệu một năm thì không phải nộp thuế". Nó đã lặp lại hai mươi ba lần, với hơn hai nghìn lượt tương tác. Bên trái, màu đỏ, là điều mọi người đang tin — và nó sai. Bên phải, màu xanh, là sự thật theo luật, kèm trích dẫn Điều 7 Luật Thuế thu nhập cá nhân.

**[Cuộn xuống mục "Điều luật bị vi phạm" rồi "Bằng chứng lan truyền"]**

Và đây không phải nói suông: hệ thống chỉ ra chính xác các điều luật bị vi phạm, có trích dẫn đầy đủ, cùng với những bài đăng thật làm bằng chứng. Mỗi cảnh báo đều truy ngược được về luật gốc.

**[Bấm sang tab "Hỏi – Đáp"]**

Tiếp theo là phần lõi, và cũng là khác biệt lớn nhất của chúng tôi.

**[Gõ: "Hội đồng tư vấn thuế xã phường còn hoạt động từ 1/7/2026 không?" → bấm Hỏi → đợi kết quả]**

Tôi hỏi: "Hội đồng tư vấn thuế xã phường còn hoạt động từ ngày mùng 1 tháng 7 năm 2026 không?". Hệ thống trả lời: KHÔNG — hội đồng này không còn hoạt động kể từ mùng 1 tháng 7 năm 2026. Và nó trích dẫn chính Điều 28 của Luật cũ năm 2019, dán nhãn rõ ràng là đã hết hiệu lực.

**[Sửa trong ô câu hỏi: đổi "1/7/2026" thành "1/6/2026" → bấm Hỏi lại]**

Bây giờ tôi chỉ đổi đúng một con số — hỏi tính đến ngày mùng 1 tháng 6 năm 2026. Vẫn là câu hỏi đó. Và lần này, hệ thống trả lời: CÓ — hội đồng vẫn còn hoạt động, bởi vì tại thời điểm ấy luật cũ chưa hết hiệu lực. Đây chính là điều mà một chatbot tìm kiếm ngữ nghĩa thông thường không làm được — nó chỉ so độ giống về mặt chữ, chứ không hiểu được hiệu lực của luật theo thời gian.

**[Nhấn vào một node bất kỳ trong đồ thị điều luật bên phải]**

Mỗi trích dẫn đều nằm trong một đồ thị Điều – Khoản – Điểm. Tôi nhấn vào một điểm là đọc được ngay nội dung luật gốc. Đây là một đồ thị thật, không phải một kho vector.

**[Nhấn chip "câu hỏi không liên quan" → bấm Hỏi]**

Và khi câu hỏi nằm ngoài phạm vi — ví dụ "có nên đầu tư tiền ảo không" — hệ thống từ chối trả lời, nói rõ "không đủ căn cứ". Trong lĩnh vực pháp lý, thà từ chối còn hơn bịa. Mọi trích dẫn đều được đối chiếu với node có thật; nếu mô hình bịa ra mã điều luật, nó bị loại bỏ ngay.

**[Bấm sang Tab 2 — Neo4j Browser (đã dán sẵn Cypher) → nhấn Enter → chờ graph hiện ra]**

Còn đây là cơ chế đứng sau tất cả: quan hệ SUPERSEDED_BY — nối điều luật cũ năm 2019 sang điều luật mới năm 2025. Chính quan hệ này cho phép "du hành thời gian" mà quý vị vừa thấy. Và đây là lý do vì sao bài toán này bắt buộc phải dùng cơ sở dữ liệu đồ thị, chứ không phải kho vector.

**[Quay lại tab web → bấm tab "Tra cứu" → gõ "hóa đơn điện tử" → bấm Tìm → nhấn kết quả đầu tiên → tick ô "Chỉ luật đang hiệu lực"]**

Và cuối cùng, dành cho người làm chuyên môn như kế toán: tra cứu và đọc nguyên văn điều luật gốc, đúng theo thời điểm hiệu lực, không cần qua AI.

**[Nhìn vào camera / dừng thao tác]**

LAWGIC là một trợ lý pháp lý trả lời đúng thời điểm, luôn có căn cứ, và không bao giờ bịa. Chúng tôi hướng tới mô hình phục vụ các công ty dịch vụ kế toán và đại lý thuế cho hộ kinh doanh. Xin cảm ơn ban giám khảo.

---

## Trả lời phần hỏi đáp (đọc khi bị hỏi)

**"Khác gì ChatGPT / RAG thường?"**
Dạ, RAG vector trả về điều luật giống nhất về mặt chữ — mà thường lại là luật đã hết hiệu lực. Chúng tôi lưu hiệu lực ở mức từng điều khoản, cộng với quan hệ SUPERSEDED_BY, nên trả đúng luật theo thời điểm. Như quý vị vừa thấy: cùng một câu hỏi, đổi ngày là đổi đáp án.

**"Làm sao biết nó không bịa?"**
Dạ, mỗi câu trả lời đều kèm trích dẫn được đối chiếu với node có thật trong đồ thị; không đủ căn cứ thì hệ thống từ chối. Chúng tôi đo bằng bộ gold gán nhãn thủ công, có cả bảng khớp chính xác lẫn khớp ngữ nghĩa, và nêu thẳng hạn chế.

**"Mô hình kinh doanh?"**
Dạ, chúng tôi làm B2B cho các công ty dịch vụ kế toán và đại lý thuế phục vụ hộ kinh doanh — giúp họ giảm giờ tra cứu và giảm rủi ro trích nhầm luật cũ. Lộ trình gồm ba giai đoạn: đối tác dùng thử, rồi trả phí, rồi mở rộng.

---

## Ghi nhớ khi quay
- Hai câu "hội đồng" (1/7 và 1/6) đã test — chạy đúng 100%. Đừng đổi chữ.
- Lỡ lag hoặc trả sai: **quay lại đúng đoạn đó**, đừng chữa live.
- Thiếu giờ: cắt đoạn "Tra cứu" trước, rồi đến đoạn "Neo4j Browser". **Tuyệt đối giữ đoạn đổi ngày 1/7 → 1/6.**
