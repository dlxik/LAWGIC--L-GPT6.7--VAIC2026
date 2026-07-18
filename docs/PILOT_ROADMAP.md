# LAWGIC — Tính khả thi kinh doanh & Lộ trình Pilot

**Mô hình mục tiêu: B2B SaaS cho công ty dịch vụ kế toán / đại lý thuế phục vụ hộ kinh doanh.**

---

## 1. Thị trường & thời điểm (why now)

- Việt Nam có **~5,5 triệu hộ kinh doanh**; phần lớn thuê **công ty dịch vụ kế toán / đại lý thuế** lo tuân thủ thuế.
- Từ **01/07/2026**, cải cách thuế hộ kinh doanh có hiệu lực (bãi bỏ khoán, đổi ngưỡng miễn, bắt buộc hoá đơn điện tử). Đây là **cú sốc tuân thủ**: mỗi công ty kế toán đối mặt **lượng câu hỏi tăng vọt** từ khách và **rủi ro trích dẫn nhầm luật cũ**.
- Cửa sổ thị trường mở đúng lúc: nhu cầu "tra đúng luật hiện hành, có căn cứ" **cấp thiết nhất trong 12–18 tháng giao thời**.

## 2. Khách hàng & nỗi đau (customer & pain)

**Khách trả tiền:** công ty dịch vụ kế toán / đại lý thuế (quy mô 5–200 nhân viên nghiệp vụ).
**Người dùng:** nhân viên kế toán/tư vấn thuế trực tiếp trả lời khách hộ kinh doanh.

| Nỗi đau hiện tại | Hệ quả |
|---|---|
| Tra luật thủ công, tốn giờ mỗi câu | Giảm năng suất, không kịp mùa cao điểm |
| Dễ trích **luật đã hết hiệu lực** (2019) | Tư vấn sai → mất khách, rủi ro pháp lý/uy tín |
| Nhân viên mới chưa nắm luật mới 2026 | Onboarding chậm, chất lượng không đồng đều |
| Không có "nguồn sự thật" trích dẫn được | Khó bảo vệ tư vấn khi khách/cơ quan hỏi lại |

## 3. Giá trị LAWGIC mang lại (value proposition)

Trợ lý pháp lý **có trích dẫn Điều–Khoản–Điểm**, **phân biệt luật cũ/mới theo thời điểm**, và **từ chối khi thiếu căn cứ** (không bịa) → nhân viên:
- Trả lời khách **nhanh hơn** (giây thay vì phút tra cứu),
- **Đúng luật hiện hành** (không trích nhầm luật hết hiệu lực),
- **Có trích dẫn để bảo vệ** tư vấn,
- Onboarding nhanh (tra là ra căn cứ).

**Khác biệt bán được:** không công cụ tra cứu nào phân biệt **hiệu lực theo thời gian** (`SUPERSEDED_BY` + as-of) — đây là chính xác thứ giai đoạn giao thời 2026 cần.

## 4. Mô hình kinh doanh (business model)

**SaaS thuê bao theo bậc**, tính theo số ghế nhân viên + hạn mức tra cứu/tháng:

| Gói | Đối tượng | Gồm |
|---|---|---|
| **Starter** | 1–5 ghế | Hỏi–Đáp có trích dẫn, tra cứu, giới hạn tra/tháng |
| **Pro** | 6–50 ghế | + Cảnh báo hiểu nhầm, lọc theo ngày, hạn mức cao, hỗ trợ ưu tiên |
| **Enterprise** | 50+ / chuỗi | + White-label, API tích hợp phần mềm kế toán, SLA, phủ đủ 5 sắc thuế |

Nguồn doanh thu phụ: **API tích hợp** vào phần mềm kế toán (MISA, Fast…); gói **cập nhật văn bản** khi có luật mới.

## 5. Kinh tế vận hành (unit economics — có ý thức chi phí)

- **Chi phí biến đổi chính = lượt gọi LLM/embedding (FPT AI Marketplace).** Mỗi truy vấn Q&A ≈ 1 lượt LLM + truy hồi cục bộ.
- **Đòn bẩy biên lợi nhuận:** (a) **cache embedding** toàn corpus 1 lần → truy vấn chỉ embed câu hỏi; (b) **tra cứu không gọi LLM** (đọc thẳng graph) cho phần lớn nhu cầu; (c) hạn mức theo gói kiểm soát chi phí đuôi.
- Vì phần lớn thao tác của kế toán là **tra cứu** (không cần LLM), chi phí biên/khách rất thấp → biên gộp cao khi scale.

## 6. Lộ trình Pilot (3 giai đoạn, có tiêu chí thành công)

### GĐ 0 — Design Partner (4–6 tuần)
- **2–3 công ty kế toán** dùng thử miễn phí trên **câu hỏi thật của họ**.
- Đo: **độ chính xác trích dẫn** (đối chiếu chuyên viên), **giờ tiết kiệm/tuần**, **tỉ lệ từ chối đúng** (không bịa), phản hồi định tính (NPS).
- **Tiêu chí qua GĐ1:** citation-accuracy trên câu thật ≥ 80%, tiết kiệm ≥ 5 giờ/nhân viên/tuần, ≥ 2/3 partner muốn trả phí.

### GĐ 1 — Paid Pilot (3 tháng)
- **10–15 công ty** trả phí giảm (early-bird); ký cam kết phản hồi.
- Mở rộng **phủ luật GTGT/TTĐB/TNDN** (nạp thêm, không đổi kiến trúc); thêm **human-in-the-loop** cho câu khó (chuyên viên xác nhận trước khi trả khách).
- **Tiêu chí qua GĐ2:** retention ≥ 80%, ≥ 10 công ty trả phí đủ, MRR đạt mốc mục tiêu.

### GĐ 2 — Scale (6–12 tháng)
- 100+ công ty; **API tích hợp phần mềm kế toán**; kênh qua **hội đại lý thuế / hội kế toán**.
- Nạp văn bản **định kỳ** (streaming) + cảnh báo thay đổi luật theo khách hàng.

## 7. Chỉ số thành công (KPIs theo dõi xuyên suốt)

Chất lượng: citation-accuracy trên câu thật · tỉ lệ từ chối-đúng (an toàn) · thời gian trả lời.
Kinh doanh: giờ tiết kiệm/nhân viên · retention · MRR · CAC/LTV · tỉ lệ nâng gói.

## 8. Rủi ro & giảm thiểu (nêu thẳng)

| Rủi ro | Giảm thiểu |
|---|---|
| Độ phủ luật còn hẹp | Nạp thêm sắc thuế theo GĐ; từ chối minh bạch khi ngoài phạm vi (không bịa) |
| Sai sót trên câu khó | Human-in-the-loop GĐ1; hiển thị độ tin cậy + trích dẫn để chuyên viên tự kiểm |
| Phụ thuộc FPT API | Retry/backoff sẵn có; hạ tầng cho phép đổi nhà cung cấp LLM/embedding |
| Trách nhiệm pháp lý tư vấn | Định vị là **trợ lý cho chuyên viên**, không thay thế; luôn kèm căn cứ để người dùng quyết |

## 9. Vì sao khả thi (feasibility summary)

Nhu cầu **cấp thiết + đúng thời điểm**, khách hàng **có ngân sách và động cơ rõ** (giảm rủi ro + tăng năng suất), **chi phí biên thấp** nhờ cache + tra cứu không-LLM, và **khác biệt phòng thủ được** (phân biệt thời gian) mà đối thủ tra cứu truyền thống không có. Lộ trình pilot **đo được, tăng dần rủi ro có kiểm soát** từ design-partner → paid → scale.
