---
name: acc-bottleneck-retrieval
description: Why verdict/citation accuracy is low — retrieval recall + broken embeddings + noisy corpus (measured)
metadata:
  type: project
---

Điều tra ngày 2026-07-18: acc thấp KHÔNG do LLM/prompt mà do tầng retrieval của `backend/discourse/linker.py`.

Số đo trên `eval/gold_set.jsonl` (35 claim có expected_citation):
- Candidate recall TF-IDF+family+graph (toàn corpus) = **62.9%** → trần trên của citation acc.
- Embedding-only recall@8 = **42.9%** (tệ hơn TF-IDF). Cosine của điều luật đúng chỉ 0.23–0.42, hạng 39–770.
- Lọc corpus xuống chỉ tncn2025 → TF-IDF recall = **82.9%**.

Ba nguyên nhân, ưu tiên giảm dần:
1. **Corpus nhiễu**: 1194/2055 node (58%) là qlt2019 (Luật QLT cũ), gần như không liên quan tranh luận ngưỡng thu nhập. 34/35 đáp án đúng nằm trong tncn2025 Điều 7 (chỉ 199 node). → Fix rẻ nhất: ưu tiên/lọc tncn2025+qlt2025 ở bước retrieval, giữ qlt2019 trong graph cho câu chuyện SUPERSEDED_BY.
2. **Embeddings hỏng thực chất**: FPT `Vietnamese_Embedding` quá yếu cho domain, không bắc cầu colloquial↔legalese. Cache KHÔNG lệch model (self-cosine=1.0). Comment trong `embeddings.py`/`linker.py` viết "cos 0.62 / hybrid 86%" là SAI, chưa đo lại. Hybrid interleave đẩy ứng viên tốt của TF-IDF ra → nên tắt hoặc thay model.
3. Điều luật đúng thường khác con số/ngược cực với claim ("200tr/500k ngày" vs "500 triệu", "phải nộp" vs "không phải nộp") → TF-IDF trượt đúng như thiết kế dự đoán.

Bộ câu hỏi gold thì ỔN: mọi claim gradable đều có expected_citation, nhãn hợp lý. Vài claim quá ngắn (g065) là khó thật chứ không sai.

Hệ quả: con số demo (verdict 60.4%, citation 54.3% trong git log) dựa trên tuyên bố recall sai — phải đo lại sau khi fix. Xem [[demo-numbers-need-remeasure]].
