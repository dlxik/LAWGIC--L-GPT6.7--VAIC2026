# Chú giải graph LAWGIC — node, cạnh, màu sắc

> File này giải thích graph gồm những gì. Số liệu lấy trực tiếp từ graph thật
> (3.979 node, 5.401 cạnh — 3 văn bản thuế: 38/2019, 108/2025, 109/2025).
> Cuối file có sẵn một khối màu dán thẳng vào Neo4j Browser là tô màu hết.

Graph chia làm **2 nhóm node**:
- **Nhóm KHUNG** (xương sống văn bản): Văn bản → Điều → Khoản → Điểm.
- **Nhóm NGHĨA** (nội dung điều luật *nói gì*): nghĩa vụ, quyền, điều cấm, chủ
  thể, thời hạn, mức phạt.

Ý tưởng cốt lõi: node KHUNG giữ *cấu trúc*, node NGHĨA giữ *ý nghĩa*, và cạnh
nối hai nhóm lại — nhờ đó hỏi được "chủ thể X có nghĩa vụ gì theo Điều nào".

---

## 1. Các loại NODE

### Nhóm KHUNG — xương sống văn bản (màu xanh dương, đậm dần lên trên)

| Node | Số lượng | Là gì | Màu gợi ý |
|---|---|---|---|
| `LegalDocument` | 3 | Cả một văn bản luật (VD "Luật QLT 108/2025") | Xanh navy `#154A8A` |
| `Article` (Điều) | 234 | Một Điều | Xanh `#4C8EDA` |
| `Clause` (Khoản) | 988 | Một Khoản trong Điều | Xanh nhạt `#68BDF6` |
| `Point` (Điểm) | 833 | Một Điểm trong Khoản | Xanh lơ `#A5DEE5` |

> **Nguyên tắc "node lá giữ sự thật":** nhiều Khoản không có Điểm con — khi đó
> chính *text của Khoản* là quy định. Vì vậy khi tra luật, mình lấy node **sâu
> nhất** (Điểm nếu có, không thì Khoản, không thì Điều), gọi là **node lá**.

### Nhóm NGHĨA — nội dung điều luật nói gì (mỗi loại một màu riêng)

| Node | Số lượng | Là gì | Màu gợi ý |
|---|---|---|---|
| `Obligation` (Nghĩa vụ) | 1.081 | "phải làm gì" | Cam `#F79767` |
| `Right` (Quyền) | 133 | "được phép gì" | Xanh lá `#57C7A4` |
| `Prohibition` (Điều cấm) | 160 | "không được làm gì" | Đỏ `#E3564A` |
| `Penalty` (Mức phạt) | 51 | Chế tài: tiền, tước phép, hình sự... | Đỏ thẫm `#B0413E` |
| `Deadline` (Thời hạn) | 197 | Mốc/khoảng thời gian phải tuân thủ | Vàng `#F9C000` |
| `Subject` (Chủ thể) | 299 | Ai bị điều luật áp dụng (người nộp thuế, cơ quan thuế...) | Tím `#9B7BD8` |
| `TaxRate` (Thuế suất) | 46 | "0%", "10%", "thuế suất 15%" | Hồng đất `#D9A5B3` |
| `TaxBase` (Căn cứ tính thuế) | 46 | "doanh thu trừ chi phí", "giá tính thuế × thuế suất" | Nâu `#C9A26D` |
| `Exemption` (Miễn/giảm) | 43 | "500 triệu trở xuống không phải nộp thuế TNCN" | Xanh rêu `#8DAA6E` |

> **Ba node thuế** (`TaxRate`, `TaxBase`, `Exemption`) là đặc thù luật thuế, P1
> thêm vì 7 loại entity gốc (thiết kế cho nghị định xử phạt) không chứa nổi thuế
> suất / căn cứ tính thuế / miễn giảm — vốn là phần lớn nội dung luật thuế.
> `Exemption` giữ câu chuyện demo quan trọng nhất: ngưỡng **500 triệu** TNCN.

**Vì sao tách Nghĩa vụ / Quyền / Điều cấm thành 3 loại node riêng**, không gộp
làm một loại `Provision` gắn thuộc tính `type`? Vì câu hỏi thật luôn hỏi theo
loại — "người nộp thuế có **nghĩa vụ** gì", "bị **cấm** gì". Tách nhãn thì đếm
và lọc chỉ là đi theo cạnh, nhanh và chính xác. **Penalty là node riêng** (không
phải thuộc tính) vì một mức phạt có thể gắn cho nhiều điều, và còn có thuộc tính
riêng (số tháng, vĩnh viễn hay không).

---

## 2. Các loại CẠNH (quan hệ)

Cạnh có **hướng** (mũi tên). Chia 3 nhóm theo chức năng:

### A. Cạnh KHUNG — dựng cây văn bản (`HAS_*`)

| Cạnh | Đi từ → tới | Nghĩa |
|---|---|---|
| `HAS_ARTICLE` | LegalDocument → Article | Văn bản có Điều này |
| `HAS_CLAUSE` | Article → Clause | Điều có Khoản này |
| `HAS_POINT` | Clause → Point | Khoản có Điểm này |

Ba cạnh này dựng nên cái cây Văn bản → Điều → Khoản → Điểm.

### B. Cạnh NGHĨA — nối điều luật với ý nghĩa của nó

| Cạnh | Đi từ → tới | Nghĩa |
|---|---|---|
| `IMPOSES` | Điều/Khoản/Điểm → Obligation | Quy định này **đặt ra nghĩa vụ** |
| `GRANTS` | Điều/Khoản/Điểm → Right | Quy định này **trao quyền** |
| `PROHIBITS` | Khoản/Điểm → Prohibition | Quy định này **cấm** điều gì |
| `PENALIZES` | Khoản/Điểm → Penalty | Vi phạm quy định này **bị phạt** thế này |
| `HAS_DEADLINE` | Khoản/Điểm → Deadline | Quy định này **có mốc thời hạn** |
| `HAS_TAX_RATE` | Điều/Khoản/Điểm → TaxRate | Quy định này **có thuế suất** |
| `HAS_TAX_BASE` | Điều/Khoản/Điểm → TaxBase | Quy định này **có căn cứ tính thuế** |
| `HAS_EXEMPTION` | Điều/Khoản/Điểm → Exemption | Quy định này **có miễn/giảm thuế** |
| `APPLIES_TO` | Nghĩa vụ/Quyền/Cấm/Thời hạn/Miễn giảm → Subject | Điều đó **áp dụng cho ai** |

`APPLIES_TO` là cạnh nhiều nhất (**1.604**) — nó là thứ cho phép hỏi "chủ thể
này gánh những gì": đứng ở node `Subject`, đi ngược cạnh APPLIES_TO ra là thấy
hết nghĩa vụ/quyền/điều cấm của họ.

### C. Cạnh THỜI GIAN / PHIÊN BẢN — điểm bán hàng của dự án

| Cạnh | Đi từ → tới | Nghĩa |
|---|---|---|
| `SUPERSEDED_BY` | node cũ → node mới (cùng cấp) | Quy định cũ **bị thay bởi** quy định mới |
| `REPLACES` | LegalDocument → LegalDocument | Văn bản mới **thay** văn bản cũ |

`SUPERSEDED_BY` có **119 cạnh** (49 cặp Điểm + 67 cặp Khoản + 3 cặp Điều), tất
cả nối luật 2019 → luật 2025. Đây là cạnh làm được version tracking mà vector
store không có — nó biết Điều 52 cũ chính là Điều 25 mới dù số hiệu khác nhau.

---

## 3. Tổng kết đồ thị nhìn từ trên xuống

```
        LegalDocument ──HAS_ARTICLE──▶ Article ──HAS_CLAUSE──▶ Clause ──HAS_POINT──▶ Point
             │                                                    │                    │
             │REPLACES                              (mỗi node lá — Điều/Khoản/Điểm —)   │
             ▼                                       IMPOSES ▶ Obligation ─┐            │
        (văn bản cũ)                                 GRANTS  ▶ Right       │APPLIES_TO  │
                                                     PROHIBITS ▶ Prohibition ├──────────▶ Subject
                                                     PENALIZES ▶ Penalty    │
                                                     HAS_DEADLINE ▶ Deadline┘
                                                        │
                                                        │SUPERSEDED_BY (khi luật đổi)
                                                        ▼
                                                   (node phiên bản mới)
```

---

## 4. Dán màu vào Neo4j Browser (1 lần, áp hết)

Mở Neo4j Browser → gõ lệnh `:style` để xem style hiện tại. Rồi mở file style,
dán khối dưới đây vào (hoặc kéo–thả file `.grass` vào khung Browser):

```
node.LegalDocument { color: #154A8A; border-color: #0E3A6E; text-color-internal: #FFFFFF; caption: '{doc_number}'; }
node.Article       { color: #4C8EDA; border-color: #2870C2; text-color-internal: #FFFFFF; caption: '{number}'; }
node.Clause        { color: #68BDF6; border-color: #3FA0E0; text-color-internal: #000000; caption: '{number}'; }
node.Point         { color: #A5DEE5; border-color: #6DC5D0; text-color-internal: #000000; caption: '{letter}'; }
node.Obligation    { color: #F79767; border-color: #E06A3B; text-color-internal: #000000; caption: '{text}'; }
node.Right         { color: #57C7A4; border-color: #35A683; text-color-internal: #000000; caption: '{text}'; }
node.Prohibition   { color: #E3564A; border-color: #C0392B; text-color-internal: #FFFFFF; caption: '{text}'; }
node.Penalty       { color: #B0413E; border-color: #8A2F2C; text-color-internal: #FFFFFF; caption: '{type}'; }
node.Deadline      { color: #F9C000; border-color: #D6A200; text-color-internal: #000000; caption: '{text}'; }
node.Subject       { color: #9B7BD8; border-color: #7B57C0; text-color-internal: #FFFFFF; caption: '{name}'; }
node.TaxRate       { color: #D9A5B3; border-color: #C07E92; text-color-internal: #000000; caption: '{text}'; }
node.TaxBase       { color: #C9A26D; border-color: #A6804B; text-color-internal: #000000; caption: '{text}'; }
node.Exemption     { color: #8DAA6E; border-color: #6C8A4F; text-color-internal: #000000; caption: '{text}'; }
relationship.SUPERSEDED_BY { color: #C0392B; shaft-width: 3px; caption: '{change_type}'; }
relationship.APPLIES_TO    { color: #9B7BD8; }
```

Nếu dán không ăn (bản Browser mới hơi khó tính), làm tay: bấm vào **bong bóng
nhãn** ở đỉnh màn hình (VD `Article`), panel bên phải hiện ra, chọn màu. Cách
này chậm hơn nhưng chắc chắn được.

Chốt bảng màu cho nhớ:
- **Xanh dương** = khung văn bản (đậm ở trên, nhạt ở dưới)
- **Cam** = nghĩa vụ, **Lá** = quyền, **Đỏ** = cấm, **Đỏ thẫm** = phạt
- **Vàng** = thời hạn, **Tím** = chủ thể
- **Cạnh đỏ đậm SUPERSEDED_BY** = chỗ luật đã đổi — cạnh đáng chỉ tay nhất khi demo
