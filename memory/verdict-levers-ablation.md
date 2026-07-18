---
name: verdict-levers-ablation
description: Ablation kết quả các lever tăng verdict accuracy (voting/tie-break/full-article/gold-relabel), 2026-07-18
metadata:
  type: project
---

Đo ngày 2026-07-18 bằng `eval/_ablate_verdict.py` (cùng 5 mẫu/claim chấm nhiều config
một lượt, TF-IDF-only USE_EMBEDDINGS=0 recall 100%, n=48). Chạy 2 lần → **biến động
lớn giữa các lần**: C1 run1=60.4%, run2=68.8% (lệch 8.4đ, CI ±14% là thật). Nguồn nhiễu:
LLM linker chọn node khác nhau giữa lần + voting temp0.5. → KHÔNG tin một con số một lần chạy.

Kết quả các lever (robust qua cả 2 run):
- **Voting (VERDICT_SAMPLES=5, temp0.5) THẮNG single-shot temp=0: +4đ (run1) tới +10đ
  (run2).** Giả thuyết "voting hại" BỊ BÁC. GIỮ voting. Cứu mạnh INAC (F1 0.67→0.81) + PART.
- **Tie-break commit ≡ confidence: 0 khác biệt accuracy cả 2 run** (chỉ lật 2/48 ca hoà,
  không ca nào đổi đúng/sai). Trung tính. Giữ 'commit' vì có lý + nhích nhẹ F1 INAC/UNVE, KHÔNG hại.
- **Full-article (đưa TRỌN Điều 7 cho verdict thay vì citation linker chọn) HẠI: −6 tới −10đ.**
  Cho model đọc cả điều luật → thêm khoản để bới lỗi → ACCU→PART nhảy 1→6. **Citation HẸP mà
  linker chọn lại GIÚP verdict** bằng cách không làm phân tâm. BÁC lever này.

Bottleneck verdict giờ = **ranh giới ACCURATE↔PARTIAL** (ACCU recall ~0.45-0.64 dao động).
3 gốc lỗi ACCU: (1) linker LLM-selection RỚT khoản đúng dù nó nằm trong candidate — claim 33
cite k3-a nhưng linker chỉ đưa k1+k2 → verdict oan INAC (lỗi LINKER cascade, KHÔNG phải verdict);
(2) tranh chấp nhãn gold; (3) claim mơ hồ thật.

Gold rubric (user chốt 2026-07-18): claim đúng cơ chế nhưng **sai TRẦN thuế suất → PARTIALLY**
(model đúng, gold sai). Đã sửa gold [34],[36] ACCURATE→PARTIALLY_INACCURATE (nói "0,5-2%" trong
khi k3 tới 5%). Backup: eval/gold_set.jsonl.bak. NHƯNG re-score cho thấy **NET-ZERO** cho C1 run2
(model tự lật: 1 claim chấm PART +1, claim kia chấm ACCU −1) — vì claim khó gán nhãn cũng là claim
model KHÔNG NHẤT QUÁN. Sửa nhãn đúng về label nhưng KHÔNG nâng số đáng tin. Claim [22] (chú thích
"cả lãi+gốc" sai khái niệm) để nguyên ACCURATE — ngoài rubric, chờ user quyết.

Kết luận: lever CƠ CHẾ verdict (voting/tie-break/law-context) đã CẠN. Dư địa còn lại =
(a) giảm BIẾN ĐỘNG để số demo tin được (tăng mẫu / hạ temp / cache linker selection),
(b) sửa chất lượng LINKER-selection (đừng rớt khoản anh em) — nhưng full-article là fix SAI.
Xem [[demo-numbers-measured]] và [[acc-bottleneck-retrieval]].

FIX LINKER-SELECTION đã làm (2026-07-18, eval/_diag_selection.py): đo thấy candidate_recall
100% nhưng single_recall chỉ 65.7% — bước LLM-chọn-node rớt khoản đúng ở 12/35 claim vì LLM
MÙ cấu trúc Điều 7 (lạc sang QLT/Điều khác do trùng chữ; lẫn k1/k2/k3). Fix = thêm BẢN ĐỒ
Điều 7 vào prompt chọn (linker.py::_ARTICLE7_MAP + _selection_prompt, tách hàm dùng chung).
Kết quả: single_recall 65.7%→74.3% (+8.6đ) mà avg |citation| GIỮ GỌN 2.6→2.9 (KHÔNG bloat —
đúng loại fix: chọn chính xác hơn chứ không nhiều hơn). run_eval: citation 65.7%→68.6%.
NHƯNG verdict vẫn 60.4% (đáy dải nhiễu) — fix bỏ được 1 failure-mode (wrong-clause cascade)
nhưng nó là thiểu số lỗi verdict, bị BIẾN ĐỘNG ±8đ nuốt. → linker fix là thắng cho CITATION +
tính đúng đắn (verdict thấy đúng khoản hơn), KHÔNG chứng minh được nâng verdict trong 1 run.
Union-5-lần: recall cao (91%) nhưng bloat citation 5.9 → BỎ (hại verdict). Test offline: 23 pass.

Code đã thêm (chưa commit): env override VERDICT_SAMPLES / VERDICT_TIEBREAK (misinformation.py),
USE_EMBEDDINGS (linker.py); tie-break 'commit' thành default. TF-IDF-only 60-69% ≥ embeddings-on
58.3% → cân nhắc để USE_EMBEDDINGS mặc định off cho cả production (tránh timeout 524 FPT).
