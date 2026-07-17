# Case mau: nong do con

> Nguon: 3 van ban trong `data/raw/legal_docs/` va 512 post trong `data/raw/social_posts/`
> (mock cho den khi P1 va P3 nap du lieu that o gio thu 8).

## Van ban

**Van ban moi (dang hieu luc):**
Nghị định 168/2025/NĐ-CP — hiệu lực từ 01/07/2026.
Điều 5 Khoản 2 Điểm a: "Phạt tiền từ 6.000.000 đồng đến 8.000.000 đồng đối với
người điều khiển xe ô tô mà trong máu hoặc hơi thở có nồng độ cồn nhưng chưa
vượt quá 50 miligam/100 mililit máu hoặc chưa vượt quá 0,25 miligam/1 lít khí
thở. Ngoài ra bị tước quyền sử dụng Giấy phép lái xe từ 10 tháng đến 12 tháng."

Điều 5 Khoản 9 Điểm a: khung cao nhất — 30–40 triệu đồng + tước GPLX 22–24 tháng
(nồng độ cồn > 80mg/100ml máu). **Không có "tước vĩnh viễn".**

**Văn bản cũ (đã bị thay thế một phần):**
Nghị định 100/2019/NĐ-CP, Điều 5 Khoản 10 Điểm a: 30–40 triệu đồng — cùng khung
tiền phạt với điểm mới nhưng câu chữ khác.

## Tin đồn đang lan truyền

> "Uống 1 lon bia bị tước bằng lái vĩnh viễn"

| Chỉ số | Giá trị |
|---|---|
| Lần đầu xuất hiện | 15/07/2026 08:12 |
| Số lần lặp trong 48h | 47 |
| Tổng tương tác | 12.384 |
| Vận tốc lan truyền | ~0.98 lần/giờ |
| Cấp độ | HIGH |

## Hệ thống đối chiếu

- Claim → `REFERS_TO` → `nd168-d5-k2-a` (confidence 0.87) và `nd168-d5-k9-a` (0.82)
- Verdict: **INACCURATE**
- Thực tế: chỉ tước bằng có thời hạn (10–12 tháng ở mức nhẹ, 22–24 tháng ở mức
  cao nhất). Không có tước vĩnh viễn ở bất kỳ khoản nào.
- Định chính: "Theo Điểm a Khoản 9 Điều 5 Nghị định 168/2025/NĐ-CP: mức phạt cao
  nhất (nồng độ cồn > 80mg/100ml máu) là 30–40 triệu đồng kèm tước GPLX 22–24
  tháng — **không tước vĩnh viễn**. Mức nhẹ (nồng độ thấp) chỉ 6–8 triệu đồng,
  tước GPLX 10–12 tháng."

## Tại sao graph ăn RAG vector ở case này

Tin đồn "vĩnh viễn" gắn với **mức phạt của văn bản CŨ** (nd100) dù cả 2 văn bản
đều có mức 30–40 triệu. Nhờ `SUPERSEDED_BY` ở mức Điểm giữa
`nd100-d5-k10-a → nd168-d5-k9-a`, hệ thống chỉ ra được:

1. Người dân đang nhớ nhầm quy định cũ, không phải bịa hoàn toàn.
2. Điểm khác biệt cụ thể (thời hạn tước bằng), không phải đọc lại cả điều luật.
3. Định chính tập trung vào chỗ đổi, giúp truyền thông chính xác hơn.

Vector store thuần thì gộp 2 điểm lại (embedding gần như trùng nhau) và không
biết cái nào còn hiệu lực tại ngày X.
