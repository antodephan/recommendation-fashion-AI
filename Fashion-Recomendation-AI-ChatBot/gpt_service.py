"""OpenAI chat helpers for natural-language fashion recommendations."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from typing import Optional


def _scrub_local_meta_leaks(text: str) -> str:
    """Gỡ cụm meta kỹ thuật (local/khối/retrieval) nếu model lỡ lặp lại trong câu trả lời user."""
    if not text:
        return text
    t = text
    phrases = (
        r"từ\s+khối\s+local",
        r"theo\s+khối\s+local",
        r"trong\s+khối\s+local",
        r"khối\s+local",
        r"từ\s+local\b",
        r"theo\s+local\b",
        r"hệ\s+thống\s+local",
        r"dữ\s+liệu\s+local",
        r"item\s+local",
        r"local\s+retrieval",
        r"retrieval\s+local",
        r"catalogue\s+nội\s+bộ",
        r"metadata\s+cho\s+model",
    )
    for p in phrases:
        t = re.sub(p, "", t, flags=re.IGNORECASE)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", t)
    return t.strip()


def clean_openai_text(text: Optional[str]) -> str:
    """Gỡ markdown thường gặp để hiển thị plain text trong chat."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    t = re.sub(r"`+([^`]*)`+", r"\1", t)
    for _ in range(5):
        prev = t
        t = re.sub(r"\*\*(.+?)\*\*", r"\1", t, flags=re.DOTALL)
        t = re.sub(r"__(.+?)__", r"\1", t, flags=re.DOTALL)
        if t == prev:
            break
    t = re.sub(r"(?m)^\s*\*\s+", "", t)
    t = t.replace("*", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return _scrub_local_meta_leaks(t.strip())

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

# Persona + nhiệm vụ theo bối cảnh (đích, hoạt động, thời gian, thời tiết) + app local. Đầu ra không dùng markdown.
_SYSTEM_STYLIST_BASE = (
    "Bạn là stylist thời trang, am hiểu đa dạng phong cách và bối cảnh mặc đồ. "
    "Trả lời bằng tiếng Việt tự nhiên, rõ ràng, thân thiện, tích cực. "
    "Nếu câu hỏi lệch chủ đề, lịch sự chuyển lại về gợi ý phối đồ. "
    "Ứng dụng có thể hiển thị ảnh sản phẩm từ kho nội bộ ngoài vùng chat; trong tin nhắn bạn không chèn link hay mã hình ảnh."
)

_FACTOR_CONTEXT_TASK = (
    "PHÂN TÍCH THEO TỪNG YẾU TỐ sau (nếu không có trong lời nhắn thì suy ra hợp lý từ ngữ cảnh/ảnh và LUÔN nêu giả định):\n"
    "- Nơi đến\n"
    "- Việc làm / hoạt động dự kiến\n"
    "- Thời gian (trong ngày, buổi trong ngày hoặc mùa)\n"
    "- Thời tiết\n"
    "\n"
    "Nếu thiếu một phần thông tin: vẫn đưa gợi ý tốt nhất có thể dựa trên phần đã biết. "
    "Nếu có sở thích hoặc manh mối phong cách trong lời người dùng hoặc trong ảnh tham khảo, đưa vào phần lý do. "
    "Giải thích rõ và suy luận từng bước trong phần Lý do chọn lựa TRƯỚC phần đề xuất cụ thể — đừng liệt kê đồ ngay từ đầu. "
    "Khi phù hợp, đưa nhiều hướng phối khác nhau (đa phong cách) miễn là bám ngữ cảnh."
)

_NO_FABRICATION = (
    "QUY TẮC KHÔNG ĐƯỢC BỊA: "
    "Không đưa URL, link ảnh, shop, giá, mã giảm giá hay SKU. "
    "Không bịa thương hiệu ngoài đời và không bịa thêm tên sản phẩm chi tiết không có trong dữ liệu bạn được cấp. "
    "Nếu tin nhắn kèm danh sách mẫu quần áo đánh số (chỉ model đọc), bạn chỉ được mô tả sản phẩm cụ thể khi trùng "
    "hoặc suy ra đúng từ các dòng đó; không thêm món không nằm trong danh sách. "
    "Nếu không có danh sách mẫu: dùng tên loại chung (áo phông, quần âu…) và có thể nhắc lại ý người dùng, không tạo tên mẫu giả. "
    "Không giả vờ đã tìm ảnh trên internet. Không liệt kê nguồn ảnh giả. "
    "Minh họa ảnh trong văn bản chỉ bằng: mô tả ngắn bằng lời, hoặc dòng trong ngoặc như "
    '[ảnh minh hoạ: mô tả ngắn gồm loại đồ, màu, form dáng] — không dùng mã/markdown/link.'
)

_VOICE_NO_TECH = (
    "GIỌNG TRẢ LỜI: viết như stylist tư vấn trực tiếp cho khách. "
    "Tuyệt đối không nhắc tới local, retrieval, khối dữ liệu, hệ thống, metadata, catalogue nội bộ, app hay "
    "cơ chế kỹ thuật. Không mở đầu kiểu 'từ danh sách…' hay 'theo dữ liệu…'. "
    "Có thể nói tự nhiên kiểu 'với quần short xám như trong ảnh', 'ưu tiên làm nổi phần trên', 'phối sáng tông biển' "
    "— luôn nói về đồ và phối, không nói về nguồn tin."
)

_INPUT_GAP = (
    "Nếu thiếu giới tính, độ tuổi hoặc mục đích rõ trong lời dẫn: gợi ý kiểu trung lập, phù hợp đại chúng; "
    "có thể hỏi lại ngắn ở cuối nếu cần — nhưng vẫn phải có đầy đủ phần Lý do và phần Đề xuất với ít nhất 3 lựa chọn."
)

_OUTPUT_STRUCTURE_VI = (
    "ĐỊNH DẠNG TRẢ LỜI (tiếng Việt trôi chảy; chỉ xuống dòng và dấu đầu dòng thông thường; không dùng markdown: "
    "không #, không **, không bôi đen bằng dấu sao).\n\n"
    "Đặt hai mục theo đúng thứ tự sau (dòng tiêu đề không cần ký tự đặc biệt):\n\n"
    "Lý do chọn lựa:\n"
    "- Liệt kê các bước suy luận: đã có và chưa có yếu tố nào trong bốn mục (nơi đến, việc làm, thời gian, thời tiết); "
    "mỗi yếu tố có tác động thế nào tới đồ mang; nếu có ảnh tham khảo hoặc các mẫu quần áo được phép chọn thì "
    "giải thích cách phối (ví dụ làm nổi phần trên, tông sáng, hợp biển) mà không nhắc meta kỹ thuật.\n\n"
    "Đề xuất trang phục:\n"
    "- Ít nhất 3 lựa chọn đánh số 1. 2. 3. (thêm các lựa chọn khác nếu hợp lý). "
    "Mỗi lựa chọn: món cụ thể, màu sắc, phong cách; có thể thêm chất liệu, phụ kiện và lưu ý mang theo. "
    "Nếu cần minh họa ảnh trong chữ thì chỉ dùng mô tả lời hoặc một dòng dạng [ảnh minh hoạ: mô tả ngắn] — không link.\n\n"
    "Có thể kết thúc bằng 1–3 câu hỏi ngắn để làm rõ chỗ đang mơ hồ (không được thay thế phần đề xuất đã có)."
)

_HYBRID_CATALOG_RULE = (
    "Khi tin nhắn kèm danh sách mẫu quần áo đánh số (chỉ model đọc): đó là toàn bộ món được phép chọn. "
    "Chỉ được mô tả cụ thể các sản phẩm trùng hoặc suy ra đúng từ các dòng đó; có thể ghép nhiều món trong danh sách "
    "thành nhiều bộ khác nhau. Không thêm món ngoài danh sách, không gán link ảnh. "
    "Nếu ảnh tham khảo là quần short xám (hoặc tương đương trong danh sách), ưu tiên các phối làm nổi phần trên, "
    "tổng thể sáng và hợp không khí biển khi ngữ cảnh gợi ý biển/du lịch. "
    "Nếu danh sách trống hoặc báo chưa có mẫu: ba bộ chỉ mô tả chung và placeholder như đã quy định."
)

_TEXT_ONLY_RULE = (
    "Phiên không kèm danh sách mẫu quần áo: ba lựa chọn trở lên chỉ với các loại trang phục mô tả chung, không nhãn giả; "
    "bám lời người dùng và ảnh (nếu có)."
)


def _build_system(*, hybrid_mode: bool) -> str:
    parts = [
        _SYSTEM_STYLIST_BASE,
        _FACTOR_CONTEXT_TASK,
        _NO_FABRICATION,
        _VOICE_NO_TECH,
        _INPUT_GAP,
        _OUTPUT_STRUCTURE_VI,
        _HYBRID_CATALOG_RULE if hybrid_mode else _TEXT_ONLY_RULE,
        "Tuân thủ đầy đủ định dạng, thứ tự 'Lý do chọn lựa' trước rồi 'Đề xuất trang phục' sau, và quy tắc không bịa.",
    ]
    return "\n\n".join(parts)


def is_openai_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _client():
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())


def gpt_chat_recommendation(user_prompt: str, has_image_upload: bool) -> Optional[str]:
    """
    Send natural-language user input directly to OpenAI and return final styling advice.
    Returns None if API call fails.
    """
    if not is_openai_configured():
        return None

    prompt = (user_prompt or "").strip()
    if not prompt:
        prompt = "Hãy gợi ý một outfit đa dụng, dễ mặc hằng ngày cho người lớn, kèm 2 lựa chọn thay thế."

    system = _build_system(hybrid_mode=False)
    user_msg = (
        "Mô tả của người dùng:\n"
        + prompt
        + "\n\n"
        + ("Người dùng có tải ảnh tham khảo trong ứng dụng." if has_image_upload else "Người dùng không tải ảnh.")
        + (
            "\nChú ý: phần gợi ý chỉ được dựa trên text có trên và ảnh (nếu có), "
            'không bịa link; có thể nói "phối cùng tông như trong ảnh tham khảo" nếu có ảnh.'
            if has_image_upload
            else ""
        )
    )

    try:
        client = _client()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.55,
            max_completion_tokens=1400,
        )
        out = clean_openai_text(resp.choices[0].message.content or "")
        return out or None
    except Exception:
        return None


def _image_path_to_data_url(image_path: str) -> Optional[str]:
    if not image_path or not os.path.exists(image_path):
        return None
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def gpt_hybrid_recommendation(
    *,
    user_prompt: str,
    uploaded_image_path: Optional[str],
    similar_items_summary: str,
) -> Optional[str]:
    """
    Hybrid mode: dùng ảnh người dùng + kết quả similar local để viết khuyến nghị cuối cùng.
    Fallback sang text-only nếu không có ảnh.
    """
    if not is_openai_configured():
        return None

    prompt = (user_prompt or "").strip()
    if not prompt:
        prompt = "Hãy gợi ý trang phục gần với phong cách trong ảnh tham khảo."

    system = _build_system(hybrid_mode=True)
    summary_block = similar_items_summary or "Chưa có mẫu quần áo phù hợp để chọn."
    user_text = (
        f"Mô tả người dùng:\n{prompt}\n\n"
        f"Danh sách mẫu được phép dùng (chỉ chọn trong các dòng sau, không thêm món khác):\n{summary_block}\n\n"
        "Ảnh tham khảo của người dùng được đính kèm trong tin nhắn (nếu có). "
        "Kết hợp mô tả, ảnh và các mẫu trên; không bịa link; không đề cập cơ chế kỹ thuật trong câu trả lời cho người dùng."
    )

    try:
        client = _client()
        data_url = _image_path_to_data_url(uploaded_image_path) if uploaded_image_path else None
        content = [{"type": "text", "text": user_text}]
        if data_url:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            temperature=0.55,
            max_completion_tokens=1400,
        )
        out = clean_openai_text(resp.choices[0].message.content or "")
        return out or None
    except Exception:
        return None
