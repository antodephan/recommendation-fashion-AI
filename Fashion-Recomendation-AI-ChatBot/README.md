# Fashion Recommendation AI Chatbot

Ứng dụng Flask gợi ý phối đồ bằng mô tả tự nhiên + ảnh tham khảo.

## Cấu trúc project

- `app.py`: Flask app chính.
- `gpt_service.py`: tích hợp OpenAI để sinh tư vấn tự nhiên.
- `nlp_context.py`: tiện ích NLP context dùng cho huấn luyện.
- `templates/home.html`: giao diện web chính.
- `scripts/`: nhóm script kỹ thuật (không chạy khi khởi động app).
  - `scripts/build_image_features.py`
  - `scripts/train_fashion_model.py`
  - `scripts/train_deep_fashion_model.py`
  - `scripts/train_nlp_context_model.py`
- `data/`: dữ liệu và ảnh sản phẩm.
- `model/`: artifact model đã build/train.
- `uploads/`: ảnh người dùng upload khi chạy app.

## Chạy ứng dụng

```bash
python app.py
```

## Build/train model

```bash
python scripts/build_image_features.py
python scripts/train_fashion_model.py
python scripts/train_deep_fashion_model.py
python scripts/train_nlp_context_model.py
```
