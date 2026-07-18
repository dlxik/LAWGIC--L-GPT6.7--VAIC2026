# LAWGIC — Mô tả Giải pháp

**Legal Analytics With Graph-Integrated Cognition**
Hệ thống Hỏi–Đáp pháp luật thuế & Giám sát hiểu nhầm trên Đồ thị tri thức có yếu tố thời gian

---

## 1. Tóm tắt giải pháp

LAWGIC là hệ thống **GraphRAG pháp lý** giải quyết hai bài toán liền mạch trên cùng một đồ thị tri thức:

1. **Hỏi–Đáp có trích dẫn, chống ảo giác** — trả lời câu hỏi thuế cho hộ kinh doanh, mỗi câu trả lời **bắt buộc kèm trích dẫn Điều–Khoản–Điểm** của văn bản đang còn hiệu lực **tại đúng thời điểm hỏi**; không đủ căn cứ thì **từ chối**, không đoán.
2. **Giám sát dư luận & phát hiện hiểu nhầm** — nối luồng bình luận công khai vào điều luật, tự động phát hiện các **hiểu nhầm về thuế đang lan truyền**, đối chiếu với luật để đưa ra **định chính có căn cứ**.

Điểm cốt lõi phân biệt LAWGIC với RAG vector thuần: **tri thức pháp lý được mô hình hoá dạng đồ thị có yếu tố thời gian** (`effective_from/effective_to` ở mức node + quan hệ `SUPERSEDED_BY`), cho phép truy vấn *"luật áp dụng TÍNH ĐẾN NGÀY X"* — điều mà vector store không làm được vì nó chỉ so độ giống văn bản, không hiểu hiệu lực thời gian.

---

## 2. Bài toán & động lực

Từ **01/07/2026**, hàng loạt quy định thuế với hộ kinh doanh thay đổi lớn (bãi bỏ phương pháp khoán, đổi ngưỡng miễn, bắt buộc hoá đơn điện tử). Trong giai đoạn giao thời:

- **Người dân hiểu sai** dựa trên quy định CŨ; hiểu nhầm lan nhanh trên mạng xã hội mà không cơ quan nào đính chính kịp thời.
- **Công cụ tra cứu hiện có** (và chatbot RAG thông thường) **không phân biệt được luật cũ/mới theo thời gian** — trả về điều khoản "giống chữ nhất", thường là luật đã hết hiệu lực → **trả lời sai một cách tự tin**, đặc biệt nguy hiểm trong lĩnh vực pháp lý.

LAWGIC giải quyết đúng khoảng trống này: **trả lời đúng theo thời điểm + phát hiện & định chính hiểu nhầm đang lan**.

---

## 3. Insight cốt lõi

> Trong pháp luật, **"điều luật giống nhất về mặt chữ" ≠ "điều luật đúng để trích dẫn"**.

Tin đồn thuế thường bám vào **ngưỡng/quy định CŨ**. Điểm luật khớp text nhất với một câu hỏi thường chính là điểm của luật đã hết hiệu lực. Chỉ có **quan hệ `SUPERSEDED_BY` trên đồ thị** mới bắc được cầu từ điểm luật cũ sang điểm luật mới tương ứng, và chỉ **hiệu lực ở mức node** mới cho phép lọc đúng theo ngày. Đây là lý do bài toán **bắt buộc dùng cơ sở dữ liệu đồ thị**, không phải chỉ để "cho khác biệt".

---

## 4. Kiến trúc tổng thể

```
        VĂN BẢN LUẬT (.docx)                 DƯ LUẬN (bình luận công khai)
                │                                      │
     [Parser bất biến]                        [Thu thập + gom luồng]
     tách Điều/Khoản/Điểm                             │
     + kiểm 7 bất biến nội dung                [Phân loại chủ đề + tách claim]
                │                                      │
     [Trích xuất thực thể]                     [Liên kết claim → Điều/Khoản/Điểm]
     nghĩa vụ/chủ thể/thuế suất/                  (hybrid retrieval + graph)
     miễn trừ/chế tài                                  │
                │                              [Phán định đúng/sai/không đủ căn cứ]
     [Diffing luật cũ↔mới]                            │
     tạo SUPERSEDED_BY +                       [Gom cụm hiểu nhầm + phát hiện trend]
     đóng effective_to                                │
                └──────────────┬───────────────────────┘
                               ▼
                    ĐỒ THỊ TRI THỨC (Neo4j)
        LegalDocument · Article · Clause · Point · Entity
        Post · Claim · Misconception
        + effective_from/to, SUPERSEDED_BY, REFERS_TO, CONTRADICTS
                               │
                    ┌──────────┴──────────┐
              API (FastAPI)          Retrieval engine
              /qa /search /trends    TF-IDF + FPT Embedding
              /misconception /graph  + graph expansion
                               │
                    Dashboard (3 tab)
              Cảnh báo hiểu nhầm · Hỏi–Đáp · Tra cứu
```

**Hạ tầng:** FastAPI (Python) · Neo4j 5 + APOC · FPT AI Marketplace (`gpt-oss-20b` cho suy luận, `Vietnamese_Embedding` cho truy hồi ngữ nghĩa) · Frontend thuần (HTML/JS/CSS + cytoscape.js, không build step).

**Quy mô dữ liệu thực:** 3 văn bản luật · 234 Điều · 988 Khoản · 833 Điểm · 119 quan hệ `SUPERSEDED_BY`; 3.321 bình luận → 1.375 claim → 119 cụm hiểu nhầm.

---

## 5. Phương pháp chi tiết

### 5.1. Đồ thị tri thức pháp lý có yếu tố thời gian

- **Parser bất biến:** DOCX → cây Điều–Khoản–Điểm với **ID xác định theo vị trí** (idempotent khi nạp lại). Bảy kiểm tra bất biến (đặc biệt *char-coverage*: tổng ký tự con phải phủ hết cha) **chặn lỗi nuốt nội dung** — lỗi ingestion nguy hiểm nhất mà thường âm thầm.
- **Hiệu lực ở mức NODE:** mỗi Điều/Khoản/Điểm mang `effective_from`/`effective_to`. Không đặt hiệu lực ở mức văn bản vì một văn bản có thể sửa đổi từng điều vào các thời điểm khác nhau.
- **Diffing luật cũ↔mới:** ghép Điều theo tiêu đề rồi ghép Điểm trong Điều; ngưỡng tương đồng **suy ra từ phân phối bimodal đo trên dữ liệu thật** (không đoán). Sinh cạnh `SUPERSEDED_BY` và **đóng `effective_to`** của điểm cũ tại ngày giao thời — nền tảng cho truy vấn theo thời gian.

### 5.2. Truy hồi lai ghép (Hybrid Retrieval)

Ba tầng bổ sung nhau, mỗi tầng vá điểm yếu tầng trước:

1. **Ngữ nghĩa (FPT Embedding):** bắc cầu "200 triệu" ↔ "500 triệu" (cùng nói về ngưỡng, khác chữ) mà TF-IDF cho ~0.
2. **Từ vựng (TF-IDF):** bám chính xác thuật ngữ luật.
3. **Mở rộng theo đồ thị:** kéo cả họ Điều liên quan + đi `SUPERSEDED_BY` sang luật mới.

Query người dùng được **chuẩn hoá** trước khi truy hồi (bung viết tắt: *tncn→thu nhập cá nhân*; đồng nghĩa đời thường→văn bản: *"miễn thuế"→"không phải nộp thuế"*), thu hẹp khoảng cách ngôn ngữ dân dã ↔ văn bản luật.

### 5.3. Hỏi–Đáp: chống ảo giác + phân biệt thời gian

- **Chống ảo giác (2 lớp):** LLM chỉ được chọn `node_id` trong tập ứng viên; mọi `node_id` LLM phát ra được **đối chiếu lại với node có thật trong đồ thị**, ID bịa bị loại; **không còn trích dẫn hợp lệ → từ chối cứng** ("Không đủ căn cứ…"). Đây là posture đúng cho sản phẩm pháp lý: **thà từ chối hơn trả lời sai**.
- **Phân biệt thời gian (as-of):** ưu tiên ngày trong câu hỏi → ô chọn ngày → mặc định hôm nay; lọc bỏ điều luật chưa/đã hết hiệu lực tại mốc đó. Cùng một câu hỏi, đổi ngày → đổi đáp án luật cũ/mới.
- **Phát hiện "quy định đã bãi bỏ":** nếu các ứng viên khớp nhất đều đã hết hiệu lực tại mốc hỏi mà luật mới không có tương đương → trả lời *"KHÔNG còn áp dụng kể từ [ngày]"* và trích chính điều cũ (dán nhãn hết hiệu lực) — hữu ích hơn hẳn "không tìm thấy", và chặn ảo giác "vẫn áp dụng".

### 5.4. Giám sát dư luận & phát hiện hiểu nhầm

Bình luận → phân loại chủ đề & tách claim → **liên kết claim vào Điều/Khoản/Điểm** (hybrid retrieval) → **phán định** đúng/sai/không đủ căn cứ (đối chiếu luật) → **gom cụm** các hiểu nhầm giống nhau → **xếp hạng cảnh báo** theo mức lan (số lần lặp × tương tác × tốc độ). Mỗi cảnh báo hiển thị: câu SAI đang lan · câu ĐÚNG (định chính lấy từ claim tin cậy nhất) · điều luật bị vi phạm · bằng chứng post.

---

## 6. Điểm khác biệt (defensible)

| # | Khác biệt | Vì sao RAG vector thuần không làm được |
|---|---|---|
| 1 | **Truy vấn luật theo thời điểm** (`effective_from/to` + `SUPERSEDED_BY`) | Vector so độ giống chữ, không hiểu hiệu lực → trả luật đã hết hạn |
| 2 | **Nối luật ↔ dư luận** (misinformation grounded in law) | Không có tầng đồ thị nối claim↔điều luật↔định chính |
| 3 | **Chống ảo giác bằng validate citation** | RAG sinh tự do, không kiểm chứng ID trích dẫn có thật |
| 4 | **Đánh giá trung thực, tái lập** (gold gán tay + số khớp file commit) | — |

---

## 7. Phương pháp đánh giá (kế hoạch đo lường)

*Ở mốc này giải pháp mới hoàn thiện phần kiến trúc & pipeline; phần định lượng sẽ báo cáo ở mốc sau. Dưới đây là **phương pháp đánh giá** chúng tôi cam kết theo — thiết kế để khách quan, tái lập, không tự chấm dễ cho mình.*

**Bộ chuẩn gán tay (gold set):** xây tập kiểm thử **gán nhãn thủ công theo văn bản luật** cho từng thành phần — trích xuất thực thể, liên kết claim, và Hỏi–Đáp (câu hỏi + đáp án chuẩn + trích dẫn kỳ vọng, gồm cả câu lạc đề để đo khả năng từ chối). Có bước **validator** kiểm gold không chứa `node_id` bịa, nhãn hợp lệ, đủ mẫu mỗi lớp.

**Hai lăng kính đo song song (để công bằng cho tiếng Việt pháp lý):**
- **Exact-match:** `citation_accuracy` (trích đúng Điều–Khoản–Điểm), `answer_correctness` (số/ngưỡng đúng), `answerable_answered` (không từ chối oan), **`offtopic_refused`** (lạc đề PHẢI từ chối — đo chống bịa).
- **Semantic (kiểu RAGAS):** `answer_similarity`, `answer_relevancy`, `context_recall`, `faithfulness` — dùng embedding để so **nghĩa**, tránh phạt oan khi cùng ý khác chữ.

**Nguyên tắc trung thực:** báo cáo tách bạch từng chiều (không gộp che khuyết điểm); mọi con số **tái lập được** từ script + gold trong repo; **chủ động nêu hạn chế** thay vì tuyên bố hoàn hảo.

---

## 8. Hạn chế & hướng phát triển (tự nêu thẳng)

Chúng tôi chủ động nêu giới hạn — vì trong pháp lý, **biết mình sai ở đâu quan trọng hơn tuyên bố hoàn hảo**:

1. **Phạm vi luật:** hiện phủ Luật Quản lý thuế (2019/2025) + Luật TNCN 2025, tập trung hộ kinh doanh. Các sắc thuế khác (GTGT/TTĐB/TNDN) chưa nạp → câu hỏi ngoài phạm vi sẽ bị **từ chối** (đúng thiết kế chống bịa, nhưng giảm độ phủ). Mở rộng chỉ cần nạp thêm văn bản, không đổi kiến trúc.
2. **Bộ gold sẽ do một người gán, kích thước vừa** → khi báo cáo định lượng cần bổ sung đa-annotator để đo độ đồng thuận, tránh khoảng tin cậy quá rộng.
3. **Phụ thuộc API LLM/embedding bên ngoài** (FPT) → nhạy với rate-limit; đã có retry backoff + jitter + Retry-After, nhưng độ trễ chưa tối ưu cho tải cao.
4. **Diffing bán tự động:** ghép điều cũ↔mới dựa độ tương đồng, recall chưa 100% — cần rà soát tay cho các thay đổi phức tạp.

**Hướng phát triển:** mở rộng đủ 5 sắc thuế; nạp định kỳ văn bản & dư luận (streaming); đa-annotator + RAGAS đầy đủ; cache embedding phân tán; hàng đợi tách LLM khỏi web để chịu tải.

---

## 9. Kết luận

LAWGIC không chỉ là chatbot tra luật. Nó là **đồ thị tri thức pháp lý có yếu tố thời gian** nối **văn bản luật ↔ dư luận xã hội**, giải quyết đúng bài toán giao thời 2026: **trả lời đúng theo thời điểm, phát hiện & định chính hiểu nhầm đang lan, và không bao giờ bịa**. Mọi quyết định kỹ thuật (mô hình, cách kết hợp, ngưỡng) đều được **thiết kế để kiểm chứng bằng gold gán tay**, và nhóm **chủ động nêu hạn chế của chính mình** — đó là chuẩn mực chúng tôi tin một sản phẩm pháp lý phải đạt.
