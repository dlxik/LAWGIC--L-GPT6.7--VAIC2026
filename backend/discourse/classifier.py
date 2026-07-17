"""[P3] Phân loại chủ đề pháp lý + tách claim từ bình luận.

Prompt: prompts/classify_topic.txt
Dùng Batches API (rẻ 50%) vì chạy hàng nghìn post.
Output: {post_id: {topic, is_legal_claim, claims: [...]}}

THIẾT KẾ: GỬI CẢ LUỒNG, KHÔNG GỬI POST LẺ. (crawl_docs.md §7.2)

  322/1.875 reply (17%) đọc riêng là vô nghĩa:
      REPLY [74 like] "Rất chính xác"
         gốc: "Cái vấn đề ở đây là không rõ ràng giữa doanh thu và thu nhập..."
  classify("Rất chính xác") -> "không có khẳng định pháp lý", và LLM ĐÚNG.
  74 like bốc hơi, im lặng.

  Gộp luồng: 3.321 call -> 1.446 (-56%), ~1.205k token -> ~642k (-47%), và LLM
  thấy được dư luận tự sửa nhau.

  JSON lồng KHÔNG cứu được chuyện này: ngữ cảnh mất ở tầng PROMPT, không phải
  tầng lưu trữ. Lồng hay phẳng, truyền post["content"] một mình vào LLM là mất.

custom_id = thread_id, KHÔNG phải post_id: 1 luồng lỗi = mất tới 90 post, retry
phải theo đúng đơn vị đã gửi.

KHÔNG lọc từ khoá trước bước này (crawl_docs.md §7.3): bỏ 24% post tiết kiệm 10%
token = 3 xu, mà vứt mất "Người tiêu dùng lại là người gánh thêm" (32 like, claim
kinh tế, không có chữ "thuế"). Phân loại là việc của classifier — đừng đặt một
regex ngu hơn đứng trước nó.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from backend.core import llm
from backend.discourse.threads import build_threads

MAX_RETRY_ROUNDS = 2
MAX_THREAD_POSTS = 15  # luồng dài hơn thì cắt khúc (tool-calling nghẹn với output lớn)


class Topic(str, Enum):
    """Enum ĐÓNG. Để LLM tự đặt tên chủ đề thì /trends vỡ vì 50 biến thể đồng nghĩa.

    Bám 3 văn bản demo (qlt2019 / qlt2025 / tncn2025) + chủ đề thật của dư luận
    trong data/raw/social_posts.json.
    """

    NGUONG_DOANH_THU = "nguong_doanh_thu"
    CACH_TINH_THUE = "cach_tinh_thue"
    THUE_KHOAN = "thue_khoan"
    HOA_DON_CHUNG_TU = "hoa_don_chung_tu"
    KE_KHAI_NOP_THUE = "ke_khai_nop_thue"
    CHE_TAI_THUE = "che_tai_thue"
    KHAC = "khac"


class PostClassification(BaseModel):
    post_id: str
    topic: Topic = Topic.KHAC
    is_legal_claim: bool = False
    claims: list[str] = Field(default_factory=list)  # PHẲNG: list chuỗi, không lồng object


class ThreadClassification(BaseModel):
    """Kết quả cho MỘT luồng. Model nội bộ của P3 — không đụng schemas.py.

    Schema càng phẳng càng tốt: backend tool-calling của P4 nghẹn với schema lồng
    sâu -> trả rỗng. claims là list[str] (không phải list[{text}]) chính vì vậy.
    """

    posts: list[PostClassification] = Field(default_factory=list)


def render_thread_for_llm(thread: list[dict]) -> str:
    """Luồng -> text gửi LLM. Gốc trước, reply thụt vào sau.

    KHÁC show_thread.render_thread(): chỗ đó cho người đọc (có like, thời gian),
    chỗ này cho LLM (chỉ post_id + nội dung — like/thời gian chỉ tốn token mà
    không giúp phân loại claim).
    """
    blocks = []
    for post in thread:
        if post.get("parent_id") is None:
            blocks.append(f"[GỐC] post_id={post['post_id']}\n{post['content']}")
        else:
            blocks.append(f"  [TRẢ LỜI] post_id={post['post_id']}\n  {post['content']}")
    return "\n\n".join(blocks)


def _build_prompt(thread: list[dict], instructions: str) -> str:
    """Hướng dẫn TRƯỚC (ổn định -> cache prefix), luồng SAU (thay đổi mỗi lần)."""
    return f"{instructions}\n\n---\n\nLUỒNG CẦN PHÂN TÍCH:\n\n{render_thread_for_llm(thread)}"


def _missing_post_ids(thread: list[dict], result: dict | None) -> set[str]:
    """post_id đã gửi nhưng LLM không trả về.

    Rủi ro thật, không phải phòng xa: luồng dài nhất là 90 post (~5.400 token) và
    LLM bỏ sót giữa chừng mà không báo lỗi. Không kiểm là mất post trong im lặng.
    """
    sent = {p["post_id"] for p in thread}
    if not result:
        return sent
    return sent - {p.get("post_id") for p in result.get("posts", [])}


def _finalize(post_id: str, data: dict) -> dict:
    """Gắn claim_id deterministic. claims đến ở dạng list[str] (đã làm phẳng)."""
    claims = [
        {"claim_id": f"{post_id}-c{i}", "text": text}
        for i, text in enumerate(data.get("claims", []))
    ]
    topic = data.get("topic", Topic.KHAC.value)
    if isinstance(topic, Topic):  # model_dump có thể giữ enum -> lấy chuỗi
        topic = topic.value
    return {
        "post_id": post_id,
        "topic": topic,
        "is_legal_claim": data.get("is_legal_claim", False),
        "claims": claims,
    }


def _chunk_threads(threads: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Cắt luồng dài thành khúc <= MAX_THREAD_POSTS. custom_id = thread_id#c{i}.

    Luồng 90 post gửi một lần -> tool-calling của backend trả rỗng (output quá lớn).
    Cắt khúc giữ được phần lớn ngữ cảnh (hiểu nhầm + đính chính thường nằm sát nhau),
    và mỗi call nhẹ đủ để model trả đúng. Khúc đầu giữ comment gốc.
    """
    units: dict[str, list[dict]] = {}
    for tid, thread in threads.items():
        if len(thread) <= MAX_THREAD_POSTS:
            units[tid] = thread
            continue
        for i in range(0, len(thread), MAX_THREAD_POSTS):
            units[f"{tid}#c{i // MAX_THREAD_POSTS}"] = thread[i:i + MAX_THREAD_POSTS]
    return units


def classify_posts(posts: list[dict]) -> dict[str, dict]:
    """Phân loại toàn bộ post. Trả {post_id: {topic, is_legal_claim, claims}}.

    claims[i].claim_id sinh deterministic: f"{post_id}-c{i}" — chạy lại phải ra
    cùng id, nếu không eval lệch.
    """
    threads = build_threads(posts)
    instructions = llm.load_prompt("classify_topic")

    pending = _chunk_threads(threads)
    collected: dict[str, dict] = {}

    for round_no in range(MAX_RETRY_ROUNDS + 1):
        if not pending:
            break

        items = [(tid, _build_prompt(thread, instructions)) for tid, thread in pending.items()]
        results = llm.extract_batch(items, ThreadClassification)

        retry: dict[str, list[dict]] = {}
        for thread_id, thread in pending.items():
            # Batches trả về KHÔNG theo thứ tự gửi -> luôn key theo custom_id.
            result = results.get(thread_id)
            if result:
                for post in result.get("posts", []):
                    if post.get("post_id"):
                        collected[post["post_id"]] = post

            missing = _missing_post_ids(thread, result)
            if missing:
                # Gọi lại CHỈ phần thiếu, giữ nguyên thread_id làm custom_id.
                retry[thread_id] = [p for p in thread if p["post_id"] in missing]

        if retry and round_no < MAX_RETRY_ROUNDS:
            n_posts = sum(len(t) for t in retry.values())
            print(f"  vòng {round_no + 1}: {len(retry)} luồng thiếu {n_posts} post -> gọi lại")
        pending = retry

    if pending:
        lost = sum(len(t) for t in pending.values())
        print(f"  ! {lost} post không phân loại được sau {MAX_RETRY_ROUNDS + 1} vòng")

    return {post_id: _finalize(post_id, data) for post_id, data in collected.items()}
