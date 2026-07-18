# Deploy LAWGIC lên FPT Cloud + lấy link nộp BTC

Mục tiêu: một **URL công khai mở được** (có user/password bảo vệ) để điền vào form
nộp. Toàn hệ (Neo4j + API + frontend) chạy bằng `docker compose` trên 1 con VM.

> LLM vẫn gọi qua FPT AI Marketplace (không chạy trên VM này) → **VM không cần GPU**.
> Chọn VM thường (rẻ) nếu FPT Cloud cho; nếu credit ở AI Factory thì "GPU Virtual
> Machine" nhỏ nhất cũng chạy được (hơi phí GPU nhưng không sao).

---

## Bước 1 — Tạo VM trên FPT Cloud

Vào **ai.fptcloud.com** (hoặc factory.fpt.ai) → tạo **Virtual Machine**:
- OS: **Ubuntu 22.04**
- Cỡ: **2 vCPU / 4 GB RAM** trở lên (graph mình nhỏ, 4GB thừa sức cho Neo4j + API)
- Ổ đĩa: 20 GB
- **Mở cổng** trong Security Group / Firewall: `22` (SSH), `8000` (app). Nếu muốn
  https đẹp thì mở thêm `80`, `443`.
- Ghi lại **IP public** của VM.

## Bước 2 — SSH vào VM, cài Docker

```bash
ssh ubuntu@<IP-public>

curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker   # để chạy docker không cần sudo
```

## Bước 3 — Lấy code + cấu hình

```bash
git clone https://github.com/dlxik/LAWGIC--L-GPT6.7--VAIC2026.git
cd LAWGIC--L-GPT6.7--VAIC2026

# Tạo .env (dán key FPT của BTC cấp)
cat > .env <<'EOF'
LLM_API_KEY=sk-...KEY-FPT...
LLM_BASE_URL=https://mkp-api.fptcloud.com
LLM_MODEL=gemma-4-31B-it
NEO4J_PASSWORD=doi-mat-khau-manh-o-day
EOF
```

## Bước 4 — Dựng cả hệ + nạp graph

```bash
docker compose up -d                                   # neo4j + api
# chờ ~30s cho neo4j healthy, rồi:
docker compose exec api python -m backend.graph.loader --wipe   # nạp luật (~2-3 phút)
```

Kiểm: `curl http://localhost:8000/health` → phải thấy `graph_source: neo4j`.

→ App đã chạy tại **`http://<IP-public>:8000`** — mở thử trên trình duyệt.

## Bước 5 — (nộp dư luận, tuỳ chọn) chạy pipeline P3

```bash
docker compose exec api python scripts/run_pipeline.py --threads 20
```

Chỉ chạy khi bản linker của P3 đã fix xong. Chưa fix thì bỏ qua — dashboard vẫn
có nửa graph luật chạy tốt.

---

## Bước 6 — Bảo vệ bằng user/password (QUAN TRỌNG)

Form nộp cho nhập user/password → **nên bật**, vì:
1. Che **key FPT** (không thì ai vào hỏi-đáp cũng tiêu tiền của mình).
2. Che **bình luận người thật** trong `social_posts.json` (quyền riêng tư).

Cách gọn nhất — thêm **Caddy** làm cổng chắn (không sửa code app). Tạo file
`Caddyfile` cạnh `docker-compose.yml`:

```
:80 {
    basicauth {
        # tao hash: docker run caddy caddy hash-password --plaintext 'matkhau'
        giamkhao <HASH-BCRYPT-CUA-MATKHAU>
    }
    reverse_proxy api:8000
}
```

Rồi thêm service vào `docker-compose.yml`:

```yaml
  caddy:
    image: caddy:2
    ports: ["80:80"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
    depends_on: [api]
```

`docker compose up -d caddy` → giờ vào `http://<IP>` phải nhập user `giamkhao` +
mật khẩu. **Điền đúng user/password này vào form nộp.**

> Muốn **https + domain** (BTC không bắt buộc, "mở được là đủ") thì Caddy tự xin
> chứng chỉ Let's Encrypt khi mày đổi `:80` thành `tenmien.com`. Không có domain
> thì `http://IP` là đủ nộp.

---

## Bước 7 — Repo GitHub cho form

Form đòi URL repo. Vì repo có **bình luận người thật**:
1. Để repo **private** (GitHub → Settings → Danger Zone → Change visibility).
2. Thêm **`vaicgit-organisers`** làm collaborator (Settings → Collaborators),
   hoặc email `vaicgit_organisers@aiforvietnam.org`.

---

## Bước 8 — Cập nhật / cải tiến sau khi đã deploy

**Link KHÔNG đổi** — team cứ code tiếp bình thường, chỉ redeploy để link theo kịp.

Khi muốn link chạy bản mới, SSH vào VM chạy:

```bash
cd LAWGIC--L-GPT6.7--VAIC2026
git pull                          # kéo code mới từ GitHub
docker compose up -d --build      # build lại + restart, link tự chạy bản mới
# nếu đổi schema/data/loader:
docker compose exec api python -m backend.graph.loader --wipe
```

- `.env` (key) trên VM **giữ nguyên** — `git pull` không đụng (đã gitignore).
- Redeploy mất **~30s–1 phút downtime** (container build lại). Bình thường.

**Chiến thuật:**
1. Deploy sớm 1 bản chạy được → có link nộp form ngay.
2. Team cải tiến tiếp ở local + `main`, thỉnh thoảng redeploy cho link theo kịp.
3. **Trước hạn chấm ~vài tiếng: chốt 1 bản ổn định, redeploy lần cuối, rồi NGỪNG
   đụng vào VM** — kẻo lỡ đẩy bản lỗi đúng lúc giám khảo vào thì link chết.

> ⚠️ **ĐỪNG redeploy khi giám khảo đang chấm** (link tắt ~1 phút). Nếu BTC chấm
> trong khung giờ cố định, đóng băng bản ổn định trước đó.

**Để link tự sống lại sau khi VM reboot:** thêm `restart: unless-stopped` vào từng
service trong `docker-compose.yml` (neo4j, api, caddy). Không có dòng này thì VM
khởi động lại là container **không tự bật** → link chết.

---

## Tóm tắt điền form

| Ô | Điền gì |
|---|---|
| URL đã triển khai | `http://<IP-public-VM>` (hoặc `:8000` nếu không dùng Caddy) |
| ☑ URL cần đăng nhập | tick, điền user `giamkhao` + mật khẩu đã đặt ở Caddyfile |
| URL repository GitHub | link repo (private + đã add vaicgit-organisers) |

## Checklist trước khi nộp

- [ ] `curl http://<IP>:8000/health` → `graph_source: neo4j`
- [ ] Mở link trên trình duyệt máy khác (không phải VM) → thấy dashboard
- [ ] User/password Caddy hoạt động
- [ ] Repo private + đã add collaborator BTC
- [ ] `.env` chỉ nằm trên VM, **không** commit lên GitHub
- [ ] (nếu bật LLM) thử 1 câu hỏi-đáp trên link thật xem có trả lời
