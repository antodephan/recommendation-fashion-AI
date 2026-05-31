import os

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from collections import defaultdict
import hashlib
import random
import time
from flask import Flask, redirect, render_template, request, session, url_for
import csv
import numpy as np
import pickle
from PIL import Image
import torch
from flask import send_from_directory
from sklearn.neighbors import NearestNeighbors
from torchvision import models, transforms
from werkzeug.utils import secure_filename
from gpt_service import (
    clean_openai_text,
    gpt_chat_recommendation,
    gpt_hybrid_recommendation,
    is_openai_configured,
)


def display_chat_history(history):
    if not history:
        return []
    return [{**entry, "generated_output": clean_openai_text(entry.get("generated_output") or "")} for entry in history]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fashion-chatbot-dev-secret")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
FEATURE_DATA_PATH = os.path.join(MODEL_DIR, "feature_data.pkl")
FILE_NAMES_PATH = os.path.join(MODEL_DIR, "file_names.pkl")
IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")
STYLES_PATH = os.path.join(BASE_DIR, "data", "styles.csv")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
IMAGE_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


def _normalize(text: str) -> str:
    return text.strip().lower()


IMAGE_MODEL = None
IMAGE_FEATURES = None
IMAGE_FILES = None
IMAGE_NEIGHBORS = None
STYLE_ROWS = []
STYLE_BY_ID = {}


def load_style_metadata():
    if not os.path.exists(STYLES_PATH):
        return [], {}
    rows = []
    by_id = {}
    with open(STYLES_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            style_id = str(row.get("id", "")).strip()
            if not style_id:
                continue
            rows.append(row)
            by_id[style_id] = row
    return rows, by_id


def _style_id_from_filename(filename: str):
    return os.path.splitext(filename)[0]


def _get_style_row_from_filename(filename: str):
    style_id = _style_id_from_filename(filename)
    return STYLE_BY_ID.get(style_id)


def _season_to_dataset(season_vi: str) -> str:
    m = {
        "xuan": "spring",
        "ha": "summer",
        "thu": "fall",
        "dong": "winter",
    }
    return m.get(_normalize(season_vi), "")


def _activity_to_usage(activity_vi: str):
    """Tập `usage` trong styles.csv — càng rộng (theo hoạt động) thì outfit càng đa dạng."""
    key = _normalize(activity_vi)
    if key == "di lam":
        return {"formal", "smart casual"}
    if key == "tham gia tiec":
        return {"party", "ethnic", "formal"}
    if key == "di hoc":
        return {"casual", "sports", "smart casual"}
    # di choi và các trường hợp khác: phong cách đời thường / thể thao / bán trang trọng
    return {"casual", "sports", "smart casual"}


def _row_matches_demographics(row: dict, gender: str, age_group: str) -> bool:
    row_gender = _normalize(row.get("gender", ""))
    row_age = _normalize(row.get("ageGroup", ""))
    if not row_age:
        row_age = {"boys": "children", "girls": "children", "men": "adult", "women": "adult", "unisex": "all"}.get(
            row_gender,
            "",
        )
    if age_group and row_age and row_age not in {age_group, "all"}:
        return False
    if not gender:
        return True
    if row_gender in {gender, "unisex"}:
        return True
    if age_group == "children" and gender == "men" and row_gender == "boys":
        return True
    if age_group == "children" and gender == "women" and row_gender == "girls":
        return True
    return False


def _activity_outfit_title(activity_vi: str) -> str:
    key = _normalize(activity_vi)
    label = {
        "di lam": "công sở / họp",
        "di hoc": "đi học",
        "di choi": "đi chơi / thể thao nhẹ",
        "tham gia tiec": "dự tiệc / sự kiện",
    }.get(key, "theo hoạt động")
    return f"Outfit gợi ý — {label}"


def _outfit_rng(
    activity: str,
    anchor_id: str,
    season: str,
    weather: str,
    temperature: float,
    outfit_nonce: int = 0,
) -> random.Random:
    seed_src = f"{activity}|{anchor_id}|{season}|{weather}|{temperature:.1f}|{outfit_nonce}"
    seed_int = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed_int)


def _filter_rows_for_outfit(gender, age_group, target_season, allowed_usage, weather, temperature, require_season: bool):
    rows = []
    for row in STYLE_ROWS:
        if not _row_matches_demographics(row, gender, age_group):
            continue
        if require_season and target_season and _normalize(row.get("season", "")) != target_season:
            continue
        if _normalize(row.get("usage", "")) not in allowed_usage:
            continue
        if not _is_weather_compatible(row, weather, temperature):
            continue
        rows.append(row)
    return rows


def _pick_one_per_slot(candidates: list, rng: random.Random) -> dict:
    by_slot = defaultdict(list)
    for row in candidates:
        slot = _slot_for_row(row)
        if slot:
            by_slot[slot].append(row)
    outfit = {}
    for slot in ("top", "bottom", "shoes", "accessories"):
        pool = by_slot.get(slot) or []
        if pool:
            outfit[slot] = rng.choice(pool)
    return outfit


def _slot_for_row(row: dict):
    article = _normalize(row.get("articleType", ""))
    sub = _normalize(row.get("subCategory", ""))
    master = _normalize(row.get("masterCategory", ""))
    if master == "footwear" or "shoe" in article or "sandal" in article or "flip flop" in article or "boots" in article:
        return "shoes"
    if sub == "bottomwear" or any(k in article for k in ["jeans", "pants", "shorts", "trousers", "skirts", "leggings", "track pants"]):
        return "bottom"
    if master == "accessories" or sub in {"bags", "belts", "watches", "jewellery"}:
        return "accessories"
    if sub in {"topwear", "innerwear"} or master == "apparel":
        return "top"
    return None


def _is_weather_compatible(row: dict, weather_vi: str, temperature: float):
    article = _normalize(row.get("articleType", ""))
    weather = _normalize(weather_vi)
    if weather == "mua" and ("flip flop" in article or "slippers" in article):
        return False
    if weather == "tuyet" and ("sandals" in article or "flip flop" in article):
        return False
    if temperature >= 33 and any(k in article for k in ["sweatshirt", "jacket", "coat"]):
        return False
    if temperature <= 12 and any(k in article for k in ["shorts", "flip flop"]):
        return False
    return True


def build_smart_outfit(
    weather: str,
    temperature: float,
    season: str,
    activity: str,
    image_results: list,
    selected_gender: str,
    selected_age_group: str,
    outfit_nonce: int = 0,
):
    if not image_results:
        return None

    anchor = _get_style_row_from_filename(image_results[0]["filename"])
    if not anchor:
        return None

    gender = selected_gender or _normalize(anchor.get("gender", ""))
    age_group = selected_age_group or _normalize(anchor.get("ageGroup", "")) or "adult"
    target_season = _season_to_dataset(season)
    allowed_usage = _activity_to_usage(activity)
    anchor_color = _normalize(anchor.get("baseColour", ""))
    anchor_id = str(anchor.get("id", "")).strip()
    rng = _outfit_rng(activity, anchor_id, season, weather, temperature, outfit_nonce=outfit_nonce)

    filtered = _filter_rows_for_outfit(
        gender, age_group, target_season, allowed_usage, weather, temperature, require_season=True
    )
    if not filtered:
        filtered = _filter_rows_for_outfit(
            gender, age_group, target_season, allowed_usage, weather, temperature, require_season=False
        )
    if not filtered:
        return None

    rng.shuffle(filtered)
    outfit = _pick_one_per_slot(filtered, rng)

    def _fill_missing(require_season: bool, prefer_anchor_color: bool):
        pool = _filter_rows_for_outfit(
            gender, age_group, target_season, allowed_usage, weather, temperature, require_season=require_season
        )
        if not pool:
            return
        rng.shuffle(pool)
        for row in pool:
            slot = _slot_for_row(row)
            if not slot or slot in outfit:
                continue
            if prefer_anchor_color and anchor_color:
                row_color = _normalize(row.get("baseColour", ""))
                if row_color and row_color != anchor_color:
                    continue
            outfit[slot] = row
            if len(outfit) == 4:
                return

    if len(outfit) < 4:
        _fill_missing(require_season=True, prefer_anchor_color=True)
    if len(outfit) < 4:
        _fill_missing(require_season=True, prefer_anchor_color=False)
    if len(outfit) < 4:
        _fill_missing(require_season=False, prefer_anchor_color=False)

    if not outfit:
        return None

    slot_title = {
        "top": "Áo",
        "bottom": "Quần/Váy",
        "shoes": "Giày",
        "accessories": "Phụ kiện",
    }
    ordered_slots = ["top", "bottom", "shoes", "accessories"]
    items = []
    for slot in ordered_slots:
        row = outfit.get(slot)
        if not row:
            continue
        style_id = str(row.get("id", "")).strip()
        image_name = f"{style_id}.jpg"
        items.append(
            {
                "slot": slot_title[slot],
                "name": row.get("productDisplayName", "Không rõ sản phẩm"),
                "meta": f"{row.get('articleType', '')} | {row.get('baseColour', '')} | {row.get('usage', '')}",
                "url": url_for("image_file", filename=image_name),
            }
        )

    return {
        "title": _activity_outfit_title(activity),
        "anchor": anchor.get("productDisplayName", "Không rõ sản phẩm tham chiếu"),
        "items": items,
    }


def init_image_recommender():
    global IMAGE_MODEL, IMAGE_FEATURES, IMAGE_FILES, IMAGE_NEIGHBORS
    if not (os.path.exists(FEATURE_DATA_PATH) and os.path.exists(FILE_NAMES_PATH)):
        return

    IMAGE_FILES = pickle.load(open(FILE_NAMES_PATH, "rb"))
    IMAGE_FEATURES = np.array(pickle.load(open(FEATURE_DATA_PATH, "rb")))
    if IMAGE_FEATURES.ndim == 3:
        IMAGE_FEATURES = IMAGE_FEATURES.reshape(IMAGE_FEATURES.shape[0], -1)

    weights = models.ResNet50_Weights.DEFAULT
    backbone = models.resnet50(weights=weights)
    IMAGE_MODEL = torch.nn.Sequential(*list(backbone.children())[:-1]).to(DEVICE)
    IMAGE_MODEL.eval()

    IMAGE_NEIGHBORS = NearestNeighbors(n_neighbors=6, algorithm="brute", metric="cosine")
    IMAGE_NEIGHBORS.fit(IMAGE_FEATURES)


def extract_image_feature(image_path: str) -> np.ndarray:
    image = Image.open(image_path).convert("RGB")
    tensor = IMAGE_TRANSFORM(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        result = IMAGE_MODEL(tensor).squeeze().detach().cpu().numpy().astype(np.float32)
    norm = np.linalg.norm(result)
    if norm == 0:
        return result
    return result / norm


def recommend_similar_images(upload_path: str, selected_gender: str, selected_age_group: str):
    if IMAGE_MODEL is None or IMAGE_NEIGHBORS is None or IMAGE_FILES is None:
        return [], "Bộ gợi ý ảnh chưa sẵn sàng. Hãy chạy: python scripts/build_image_features.py"

    feature = extract_image_feature(upload_path).reshape(1, -1)
    neighbor_count = min(120, len(IMAGE_FILES))
    distances, indices = IMAGE_NEIGHBORS.kneighbors(feature, n_neighbors=neighbor_count)

    recommendations = []
    for idx, dist in zip(indices[0][1:], distances[0][1:]):
        filename = IMAGE_FILES[idx]
        row = None
        if selected_gender or selected_age_group:
            row = _get_style_row_from_filename(filename)
            if not row or not _row_matches_demographics(row, selected_gender, selected_age_group):
                continue
        # With cosine metric: distance = 1 - cosine_similarity, where cosine_similarity in [-1, 1].
        # Convert to readable percentage [0,100] to avoid near-zero misleading output.
        score = max(0.0, min(100.0, (1.0 - (float(dist) / 2.0)) * 100.0))
        recommendations.append(
            {
                "filename": filename,
                "score": int(round(score)),
                "url": url_for("image_file", filename=filename),
            }
        )
        if len(recommendations) == 5:
            break

    if not recommendations and (selected_gender or selected_age_group):
        return [], "Không tìm thấy ảnh khớp giới tính/nhóm tuổi đã chọn. Thử ảnh khác."
    return recommendations, None


def _summarize_similar_items_for_prompt(image_results: list) -> str:
    if not image_results:
        return "Chưa có mẫu quần áo phù hợp."
    lines = []
    for idx, item in enumerate(image_results, start=1):
        row = _get_style_row_from_filename(item.get("filename", ""))
        if row:
            title = row.get("productDisplayName", item.get("filename", ""))
            article = row.get("articleType", "")
            color = row.get("baseColour", "")
            usage = row.get("usage", "")
            lines.append(
                f"{idx}. {title} | articleType={article} | color={color} | usage={usage} | similarity={item.get('score', 0)}%"
            )
        else:
            lines.append(f"{idx}. {item.get('filename', 'unknown')} | similarity={item.get('score', 0)}%")
    return "\n".join(lines)


init_image_recommender()
STYLE_ROWS, STYLE_BY_ID = load_style_metadata()


@app.post("/new-chat")
def new_chat():
    session.pop("chat_history", None)
    session.modified = True
    return redirect(url_for("index"))


@app.route("/", methods=["GET", "POST"])
def index():
    chat_history = session.get("chat_history", [])
    image_error = None
    image_results = []
    uploaded_image_url = None
    smart_outfit = None

    if request.method == "POST":
        user_prompt = request.form.get("user_prompt", "").strip()

        upload = request.files.get("style_image")
        has_upload = bool(upload and upload.filename)
        has_text = bool(user_prompt)
        if not (has_text or has_upload):
            return render_template(
                "home.html",
                user_query=user_prompt,
                generated_output="Vui lòng nhập mô tả tự nhiên hoặc tải ảnh tham khảo để mình gợi ý trang phục.",
                image_results=[],
                image_error=None,
                uploaded_image_url=None,
                smart_outfit=None,
                context_note=None,
                recommendation_via_openai=False,
                openai_model_display=None,
                chat_history=display_chat_history(chat_history),
                composer_autofocus=True,
            )

        use_gpt = is_openai_configured()
        recommendation_via_openai = False
        openai_model_display = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
        generated_output = "OpenAI API key chưa được cấu hình. Hãy thêm OPENAI_API_KEY trong file .env."

        selected_gender = ""
        selected_age_group = "adult"
        outfit_weather = "nang"
        outfit_temperature = 25.0
        outfit_season = "ha"
        outfit_activity = "di choi"
        upload_path = None
        similar_items_summary = ""
        if upload and upload.filename:
            safe_name = secure_filename(upload.filename)
            upload_path = os.path.join(UPLOAD_DIR, safe_name)
            upload.save(upload_path)
            uploaded_image_url = url_for("uploaded_file", filename=safe_name)
            image_results, image_error = recommend_similar_images(
                upload_path,
                selected_gender=selected_gender,
                selected_age_group=selected_age_group,
            )
            if not image_error:
                smart_outfit = build_smart_outfit(
                    weather=outfit_weather,
                    temperature=outfit_temperature,
                    season=outfit_season,
                    activity=outfit_activity,
                    image_results=image_results,
                    selected_gender=selected_gender,
                    selected_age_group=selected_age_group,
                    outfit_nonce=time.time_ns() % (2**32),
                )
            similar_items_summary = _summarize_similar_items_for_prompt(image_results)

        if use_gpt:
            base_prompt = user_prompt or "Hãy gợi ý outfit phù hợp dựa trên ảnh tham khảo người dùng vừa tải."
            if upload_path:
                full_text = gpt_hybrid_recommendation(
                    user_prompt=base_prompt,
                    uploaded_image_path=upload_path,
                    similar_items_summary=similar_items_summary,
                )
            else:
                full_text = gpt_chat_recommendation(base_prompt, has_image_upload=False)
            if full_text:
                generated_output = full_text
                recommendation_via_openai = True
            else:
                generated_output = "Không thể lấy phản hồi từ OpenAI lúc này. Vui lòng thử lại sau."

        chat_history.append(
            {
                "user_prompt": user_prompt or "Mình muốn gợi ý theo ảnh đã tải lên.",
                "generated_output": generated_output,
                "uploaded_image_url": uploaded_image_url,
            }
        )
        # Keep recent messages to avoid oversized cookies.
        session["chat_history"] = chat_history[-10:]
        session.modified = True

        return render_template(
            "home.html",
            user_query=user_prompt,
            generated_output=generated_output,
            image_results=image_results,
            image_error=image_error,
            uploaded_image_url=uploaded_image_url,
            smart_outfit=smart_outfit,
            context_note=None,
            recommendation_via_openai=recommendation_via_openai,
            openai_model_display=openai_model_display if recommendation_via_openai else None,
            chat_history=display_chat_history(session.get("chat_history", [])),
            composer_autofocus=True,
        )

    return render_template(
        "home.html",
        user_query=None,
        generated_output=None,
        image_results=[],
        image_error=None,
        uploaded_image_url=None,
        smart_outfit=None,
        context_note=None,
        recommendation_via_openai=False,
        openai_model_display=None,
        chat_history=display_chat_history(chat_history),
        composer_autofocus=False,
    )


@app.route("/images/<path:filename>")
def image_file(filename):
    return send_from_directory(IMAGE_DIR, filename)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
