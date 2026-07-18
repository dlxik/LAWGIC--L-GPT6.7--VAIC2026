---
name: demo-readiness
description: Trạng thái sẵn sàng demo + cờ đỏ lệch domain giữa demo_script và dữ liệu thật
metadata:
  type: project
---

Sau phiên 2026-07-18, các việc demo đã xong / còn treo.

ĐÃ XONG:
- Trend (tính năng chủ lực) BẬT trung thực: `run_pipeline.py --as-of 2025-11-20
  --window 48 --min-occ 3` -> 1 trend "120tr phải nộp thuế" = 4 claim/48h ngày
  19/11/2025 (đợt bùng thật). _count_in_window giờ đếm member_times thật, không
  xấp xỉ cả cụm. severity LOW vì engagement 98 < 100 (ngưỡng MEDIUM) — trung thực.
- Số bịa đã xoá: test_linker.py "hybrid 86%"; sample_case.md verdict60,4/citation54,3
  + claim "graph 43->54". Nay ghi số thật: phát hiện tin sai 86,8%, citation 76,2%.
- Metric chính = phát hiện tin sai (INACCURATE nhị phân) trong run_eval.py.

CỜ ĐỎ CHƯA GIẢI QUYẾT (cần team quyết):
- **demo_script.md mô tả DOMAIN KHÁC dữ liệu thật.** Kịch bản nói về nghị định 168
  "uống bia bị tước bằng vĩnh viễn", "47 lần lặp, 12k tương tác, HIGH" — nhưng
  dữ liệu social thật (data/processed/posts_labeled) là THUẾ hộ kinh doanh, trend
  thật "4 claim/48h, 98 tương tác, LOW". Graph neo4j có node giao thông (nd100/nd168)
  nhưng post lại về thuế. => Kịch bản demo và data KHÔNG khớp. Con số 47/12k/HIGH
  trong demo_script là BỊA/placeholder. Phải chọn: (a) làm demo theo case THUẾ (có
  data thật, sample_case.md sẵn sàng), hay (b) crawl thêm data giao thông cho khớp
  kịch bản rượu-bia. KHÔNG được diễn số 47/12k/HIGH khi dashboard chạy ra thuế.

Cấu hình demo ổn định: USE_EMBEDDINGS=0 (TF-IDF, tránh timeout 524 FPT); eval dao
động ±8đ nên chạy ≥2 lần lấy số đại diện. Xem [[demo-numbers-measured]].
