---
name: demo-numbers-measured
description: Số eval hiện tại (metric chính = phát hiện tin sai 86.8%), 2026-07-18
metadata:
  type: project
---

Đo TB 3 run ngày 2026-07-18, TF-IDF (USE_EMBEDDINGS=0), n=48 gold, vote5.

**METRIC CHÍNH cho demo (user chốt) = PHÁT HIỆN TIN SAI**: nhị phân INACCURATE vs
còn lại = **86.8%** (P=0.75, R=0.86). Đây là câu trả lời đúng cho hệ misinformation
"có bắt đúng claim sai không?". Đã đưa thành đầu ra chính của run_eval.py
(detection_accuracy, in đầu báo cáo). baseline đoán bừa INACCURATE = 29.2%.

Các số phụ:
- verdict 4-lớp: ~59.7% TB (58/58/62%), CI ±14%. CHẶN bởi ranh giới ACCURATE↔PARTIAL
  mơ hồ BẢN CHẤT (không phải bug) — ~25% claim nằm trên ranh giới, model đã gần trần
  nhãn-người. Đừng hứa 4-lớp ≥70%.
- citation_accuracy: **76.2%** TB (từ ~66% nhờ fix linker bản đồ Điều 7). Thắng thật, vững.
- Các cách gộp lớp (đo được): gộp PART+INAC=62.5%; gộp ACCU+PART=72.2%; nhị phân bắt
  INACCURATE=86.8%. Chỉ nhị phân + ACCU+PART merge vượt 70%; nhị phân semantics mạnh nhất.

BIẾN ĐỘNG đo lường: cùng config lệch tới ±8đ giữa các run (linker temp0 + voting temp0.5).
→ LUÔN đo ≥3 run lấy TB, đừng trích 1 con số.

Lịch sử fix (git + phiên này): fix A neo Điều 7 (recall→100%); vote5 (verdict +4-10đ,
GIỮ); tie-break commit (trung tính); full-article-to-verdict (HẠI −10đ, BỎ); linker bản
đồ Điều 7 (citation +10đ); prompt siết UNVERIFIABLE (UNVE recall +, verdict net-0). Sửa
gold 34,36 ACCU→PART (rubric sai-trần-%, net-0 vì model tự lật). Xem
[[verdict-levers-ablation]] và [[acc-bottleneck-retrieval]].

CẦN SỬA (slide/test còn ghi SAI): test_linker.py:92 + slide ghi "hybrid 86%" — số bịa,
chưa từng đo đúng. citation thật ~76% TF-IDF.
