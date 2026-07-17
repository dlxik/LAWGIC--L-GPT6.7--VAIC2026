# Kich ban demo (5 phut)

> [P4 chot noi dung, ca team dien tap 1 lan o gio thu 22]

| Phut | Man hinh | Loi thoai |
|---|---|---|
| 0:00 | Slide | Van de: nghi dinh moi co hieu luc, du luan hieu sai, khong ai phat hien kip |
| 0:30 | Neo4j Browser | Graph that: Dieu-Khoan-Diem + entity. Khong phai vector store |
| 1:30 | Dashboard tab 1 | Canh bao: "uong 1 lon bia bi tuoc bang vinh vien" lap 47 lan/24h |
| 2:30 | Click vao canh bao | He thong doi chieu Dieu 5 Khoan 2 Diem a -> thuc te chi tuoc CO THOI HAN |
| 3:15 | Dashboard diff | Van ban moi vs cu: SUPERSEDED_BY o muc Diem, ai doi gi ngay nao |
| 4:00 | Tab Q&A | Hoi bat ky -> tra loi kem citation. Hoi cai khong co luat -> tu choi tra loi |
| 4:30 | Slide eval | Accuracy tren 50 claim gan nhan tay. Con so, khong noi suong |

## Cau BGK se hoi — chuan bi truoc

1. **"Sao khong dung RAG vector cho nhanh?"**
   -> Vector khong tra loi duoc "luat noi gi ngay 1/7" va "dieu nay doi the nao".
      SUPERSEDED_BY o muc Diem lam duoc. Mo Neo4j Browser cho xem.
2. **"Lam sao biet phan loai dung/sai chinh xac?"**
   -> Mo eval/. Accuracy tren gold set 50 claim. (KHONG co so nay = mat diem nang)
3. **"LLM bia dieu luat thi sao?"**
   -> Moi cau tra loi trich node_id co that trong graph. Khong tim thay -> tu choi.
4. **"Du lieu comment lay the nao, co vi pham gi khong?"**
   -> Chi noi dung cong khai tren bao dien tu, hash author, khong luu danh tinh.
