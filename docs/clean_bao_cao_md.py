"""Clean BAO_CAO markdown: remove MUC LUC, HTML tags, expand abbreviations."""
from __future__ import annotations

import re
from pathlib import Path

MD = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v2.md"
SRC = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP.md"

ABBREVIATIONS = """## DANH SÁCH TỪ VIẾT TẮT

| Viết tắt | Tiếng Anh | Tiếng Việt |
|----------|-----------|------------|
| AI | Artificial Intelligence | Trí tuệ nhân tạo |
| ANN | Approximate Nearest Neighbor | Tìm kiếm láng giềng gần đúng |
| API | Application Programming Interface | Giao diện lập trình ứng dụng |
| ASGI | Asynchronous Server Gateway Interface | Giao diện cổng máy chủ bất đồng bộ |
| CBF | Content-based Filtering | Lọc theo nội dung |
| CF | Collaborative Filtering | Lọc cộng tác |
| CORS | Cross-Origin Resource Sharing | Chia sẻ tài nguyên đa nguồn |
| CRUD | Create, Read, Update, Delete | Tạo, đọc, cập nhật, xóa |
| CTR | Click-Through Rate | Tỷ lệ nhấp chuột |
| DL | Deep Learning | Học sâu |
| DTO | Data Transfer Object | Đối tượng truyền dữ liệu |
| ERD | Entity Relationship Diagram | Sơ đồ thực thể liên kết |
| ETL | Extract, Transform, Load | Trích xuất, biến đổi, nạp dữ liệu |
| GPU | Graphics Processing Unit | Đơn vị xử lý đồ họa |
| HNSW | Hierarchical Navigable Small World | Thuật toán index vector HNSW |
| HTTP | HyperText Transfer Protocol | Giao thức truyền siêu văn bản |
| HTTPS | HTTP Secure | HTTP bảo mật |
| i18n | Internationalization | Quốc tế hóa (đa ngôn ngữ) |
| JWT | JSON Web Token | Mã thông báo web JSON |
| KB | Knowledge Base | Cơ sở tri thức |
| KPI | Key Performance Indicator | Chỉ số hiệu suất chính |
| LLM | Large Language Model | Mô hình ngôn ngữ lớn |
| ML | Machine Learning | Học máy |
| MVP | Minimum Viable Product | Sản phẩm khả dụng tối thiểu |
| NLP | Natural Language Processing | Xử lý ngôn ngữ tự nhiên |
| OAuth | Open Authorization | Ủy quyền mở |
| ORM | Object-Relational Mapping | Ánh xạ đối tượng-quan hệ |
| RAG | Retrieval-Augmented Generation | Sinh văn bản tăng cường truy xuất |
| RBAC | Role-Based Access Control | Kiểm soát truy cập theo vai trò |
| REST | Representational State Transfer | Kiến trúc chuyển trạng thái biểu diễn |
| RS | Recommendation System | Hệ thống gợi ý |
| RDBMS | Relational Database Management System | Hệ quản trị CSDL quan hệ |
| SDK | Software Development Kit | Bộ công cụ phát triển phần mềm |
| SMTP | Simple Mail Transfer Protocol | Giao thức chuyển thư điện tử |
| SQL | Structured Query Language | Ngôn ngữ truy vấn có cấu trúc |
| SSE | Server-Sent Events | Sự kiện gửi từ máy chủ |
| UI | User Interface | Giao diện người dùng |
| UX | User Experience | Trải nghiệm người dùng |
| UUID | Universally Unique Identifier | Định danh duy nhất toàn cục |
| WS | WebSocket | Giao thức WebSocket |
| XML | eXtensible Markup Language | Ngôn ngữ đánh dấu mở rộng |
"""


def main() -> None:
    text = SRC.read_text(encoding="utf-8")

    text = re.sub(r"<div style=\"page-break-after: always;\"></div>\s*", "", text)
    text = re.sub(r"<br\s*/?\s*>\s*", "\n", text)

    # Remove MUC LUC block
    text = re.sub(
        r"## MỤC LỤC\s*\n\n\| STT \|.*?(?=\n---\s*\n## DANH SÁCH HÌNH)",
        "",
        text,
        flags=re.S,
    )

    # Replace abbreviations section
    text = re.sub(
        r"## DANH SÁCH TỪ VIẾT TẮT\s*\n\n\| Viết tắt \|.*?(?=\n---\s*\n## TÓM TẮT|\n---\s*\n## TÓM TẮT)",
        ABBREVIATIONS + "\n",
        text,
        flags=re.S,
    )

    MD.write_text(text, encoding="utf-8")
    print(f"Updated {MD}")


if __name__ == "__main__":
    main()
