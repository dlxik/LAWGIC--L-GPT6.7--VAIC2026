# Gửi Linh (P2) — P1 đổi schema, graph cần sửa

> Từ: Nguyên (P1). Tóm tắt những gì P1 thay đổi ảnh hưởng tới `loader.py` /
> `schema.py` của Linh, và **chính xác phải sửa gì**. Có 1 việc **bắt buộc**
> (kèm 1 bug ngầm) + vài việc để biết.

---

## TL;DR

P1 thêm **3 trường thuế** vào `ExtractedEntities` (`tax_rates`, `tax_base`,
`exemptions`). Hiện `load_entities()` **bỏ qua chúng im lặng** → **84 node có dữ
liệu thuế không lên graph**, gồm cả **node demo** (ngưỡng 500 triệu TNCN).

Sửa **2 chỗ trong `loader.py`** (kèm tránh 1 bug đè node), cập nhật **`schema.py`**
cho khớp. Chi tiết dưới.

---

## 1. BẮT BUỘC — 3 trường thuế đang bị rơi

`ExtractedEntities` giờ có 10 trường (trước 7):

```
subjects, obligations, rights, prohibitions, penalties, deadlines, references
+ tax_rates    ← MỚI  ("0%", "10%", "thuế suất 15%")
+ tax_base     ← MỚI  ("doanh thu trừ chi phí", "giá tính thuế × thuế suất")
+ exemptions   ← MỚI  ("500 triệu trở xuống không phải nộp thuế TNCN")
```

`load_entities()` (loader.py) chỉ map 4 trường qua `_ENTITY_REL`
(obligations/rights/prohibitions/deadlines) + subjects + penalties. **3 trường
thuế không có trong `_ENTITY_REL` → không tạo node → mất trắng.**

**Số liệu thật trong graph cuối** (`data/processed/entities_*.json`):
- **84 node** có ≥1 trường thuế
- 46 span `tax_rates`, 46 span `tax_base`, 43 span `exemptions`
- Node demo `tncn2025-d7-k1`: `exemptions = ["mức doanh thu năm từ 500 triệu đồng
  trở xuống không phải nộp thuế thu nhập cá nhân"]` — **không sửa thì demo mất câu
  quan trọng nhất.**

---

## 2. ⚠️ BUG NGẦM — đừng chỉ thêm `field[:3]`, nó ĐÈ node

`load_entities` sinh id bằng `entity_id = f"{node_id}-{field[:3]}{i}"`. Với 4 trường
cũ thì `[:3]` ra duy nhất (obl/rig/pro/dea). **Nhưng:**

```
tax_rates[:3]  = "tax"
tax_base[:3]   = "tax"   ← TRÙNG!
```

→ `tax_rates[0]` và `tax_base[0]` cùng ra `entity_id = "<node>-tax0"` → `MERGE` vào
**cùng một node**, cái sau đè cái trước. Nhiều node có cả rate lẫn base (46/46 span)
→ **mất một nửa dữ liệu thuế mà không báo lỗi gì**.

Nên phải đổi cách sinh prefix, **không dùng `field[:3]`** cho phần thuế.

---

## 3. Sửa `backend/graph/loader.py` — chính xác

### (a) `_ENTITY_REL` (dòng ~74): thêm prefix riêng làm phần tử thứ 3

```python
# CŨ
_ENTITY_REL = {
    "obligations": ("Obligation", "IMPOSES"),
    "rights": ("Right", "GRANTS"),
    "prohibitions": ("Prohibition", "PROHIBITS"),
    "deadlines": ("Deadline", "HAS_DEADLINE"),
}

# MỚI — thêm prefix duy nhất (tránh collision "tax")
_ENTITY_REL = {
    "obligations":  ("Obligation",  "IMPOSES",       "obl"),
    "rights":       ("Right",       "GRANTS",        "rig"),
    "prohibitions": ("Prohibition", "PROHIBITS",     "pro"),
    "deadlines":    ("Deadline",    "HAS_DEADLINE",  "dea"),   # giữ "dea" như cũ
    "tax_rates":    ("TaxRate",     "HAS_TAX_RATE",  "txr"),   # MỚI
    "tax_base":     ("TaxBase",     "HAS_TAX_BASE",  "txb"),   # MỚI
    "exemptions":   ("Exemption",   "HAS_EXEMPTION", "exm"),   # MỚI
}
```

### (b) vòng lặp trong `load_entities` (dòng ~264): dùng prefix mới

```python
# CŨ
for field, (label, rel) in _ENTITY_REL.items():
    for i, text in enumerate(ent.get(field, [])):
        entity_id = f"{node_id}-{field[:3]}{i}"

# MỚI
for field, (label, rel, prefix) in _ENTITY_REL.items():
    for i, text in enumerate(ent.get(field, [])):
        entity_id = f"{node_id}-{prefix}{i}"
```

Chỉ vậy — `_MERGE_ENTITY` có sẵn dùng lại được, không phải viết Cypher mới.

### (c) Lưu ý về subjects gắn vào entity thuế

Vòng lặp hiện gắn `subjects` (APPLIES_TO) vào **mọi** entity. Với `exemptions` thì
**đúng và hữu ích** (miễn trừ áp cho "cá nhân cư trú"…). Với `tax_rates`/`tax_base`
thì hơi thừa nhưng **vô hại** (một TaxRate nối tới Subject). Đề xuất: **để nguyên
cho đơn giản**. Nếu muốn sạch thì bọc `if field not in ("tax_rates", "tax_base")`
quanh đoạn gắn subject — tuỳ Linh, không bắt buộc.

---

## 4. Sửa `backend/graph/schema.py`

### (a) Docstring — thêm node + relationship mới (dòng ~12 và ~24)

```
  Obligation | Right | Prohibition | Deadline {node_id, text}
+ TaxRate | TaxBase | Exemption {node_id, text}          ← THÊM

  (Article|Clause|Point)-[:PROHIBITS]->(Prohibition)
+ (Article|Clause|Point)-[:HAS_TAX_RATE]->(TaxRate)      ← THÊM
+ (Article|Clause|Point)-[:HAS_TAX_BASE]->(TaxBase)      ← THÊM
+ (Article|Clause|Point)-[:HAS_EXEMPTION]->(Exemption)   ← THÊM
```

### (b) CONSTRAINTS — **không bắt buộc**

Các label entity cũ (Obligation/Right/…) hiện **cũng không có constraint** trên
`node_id`, nên 3 label thuế mới **chạy được mà không cần thêm**. Nếu Linh muốn nhất
quán thì thêm cả 7 (obligation + 3 thuế); còn không thì bỏ qua cũng đúng theo pattern
hiện tại. Đừng để nó chặn việc nạp.

---

## 5. Để biết (không phải sửa gấp)

- **`PenaltyType` enum mở rộng** — thêm `LATE_PAYMENT_INTEREST`, `ENFORCEMENT`,
  `INVOICE_SUSPENSION`, `CRIMINAL`, `LICENSE_SUSPENSION`, `LICENSE_REVOCATION`.
  Loader lưu `pen["type"]` dạng chuỗi nên **không phải sửa gì**. Chỉ lưu ý test
  `test_no_permanent_penalty_anywhere`: luật thuế **không** có 2 loại LICENSE nên
  test vẫn xanh, nhưng biết để khỏi ngạc nhiên khi thấy type mới.
- **`references`** (trích dẫn "khoản 4 Điều 2", "Luật này") — có trong entity nhưng
  loader **chưa** map ở mức node (đây là hiện trạng cũ, không phải P1 đổi). Muốn có
  cạnh Point→Point theo trích dẫn thì cần resolver text→node_id (khó, để sau). Không
  chặn demo.
- **`LegalDocument.replaces/amends`** — P1 đã thêm vào schema, `loader.py:244` đã đọc
  đúng → không phải làm gì.

---

## 6. Kiểm tra sau khi sửa

```bash
# nạp lại graph
python -m backend.graph.loader          # hoặc script nạp của Linh

# đếm node thuế đã lên chưa (mong: 84 node có, ~135 entity thuế)
# Cypher:
MATCH (n)-[:HAS_TAX_RATE|HAS_TAX_BASE|HAS_EXEMPTION]->(e)
RETURN labels(e)[0] AS loai, count(e) AS so ORDER BY so DESC
# mong: TaxRate 46, TaxBase 46, Exemption 43

# node demo phải có exemption:
MATCH (p {point_id: "tncn2025-d7-k1"})-[:HAS_EXEMPTION]->(e) RETURN e.text
# mong: "...500 triệu đồng trở xuống không phải nộp thuế TNCN"

python -m pytest tests/test_graph.py     # phải vẫn xanh
```

---

## 7. Dữ liệu ở đâu

- Graph P1 sinh ra: `data/processed/entities_{qlt2019,qlt2025,tncn2025}.json`
  (**1.842 node**, cấu hình voting hybrid — xem `benchmark.md` / `voting_method.md`).
- Mỗi phần tử = 1 dict: `{node_id, subjects, obligations, rights, prohibitions,
  penalties, deadlines, references, tax_rates, tax_base, exemptions}`.
- Contract đầy đủ: `backend/models/schemas.py` → class `ExtractedEntities`.

Có gì không rõ nhắn mình. Phần must-fix (mục 1–3) là chỗ dễ mất điểm demo nhất
(exemptions = câu chuyện ngưỡng 500 triệu), nên ưu tiên.
