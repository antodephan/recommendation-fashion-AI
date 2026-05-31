import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional

import joblib
import numpy as np
try:
    from vncorenlp import VnCoreNLP
except Exception:
    VnCoreNLP = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
NLP_CONTEXT_PATH = os.path.join(MODEL_DIR, "nlp_context.joblib")
VNCORE_DIR = os.path.join(BASE_DIR, "vncorenlp")
VNCORE_JAR_PATH = os.path.join(VNCORE_DIR, "VnCoreNLP-1.1.1.jar")

ALLOWED_WEATHER = {"nang", "mua", "tuyet"}
ALLOWED_SEASON = {"xuan", "ha", "thu", "dong"}
ALLOWED_ACTIVITY = {"di lam", "di hoc", "di choi", "tham gia tiec"}
ALLOWED_GENDER = {"men", "women"}
ALLOWED_AGE_GROUP = {"children", "adult", "all"}
ALLOWED_ARTICLE_TYPES = {
    "shirts",
    "tshirts",
    "tops",
    "jackets",
    "rain jacket",
    "sweaters",
    "sweatshirts",
    "trousers",
    "jeans",
    "shorts",
    "track pants",
    "dresses",
    "skirts",
    "jumpsuit",
    "suits",
    "blazers",
    "casual shoes",
    "sports shoes",
    "formal shoes",
    "sandals",
    "heels",
    "flats",
    "backpacks",
    "handbags",
}

# Giá trị mặc định chỉ dùng khi không có tín hiệu nào cho slot đó (mô hình trang phục cần đủ vector).
DEFAULT_WEATHER = "nang"
DEFAULT_SEASON = "ha"
DEFAULT_ACTIVITY = "di choi"
DEFAULT_AGE_GROUP = "adult"
DEFAULT_TEMPERATURE = 25.0
CONF_FORM = 1.0
CONF_RULE = 0.92
CONF_MODEL_UNKNOWN = 0.45
CONF_DEFAULT_SLOT = 0.22

WEATHER_SYNONYMS = {
    "nang": ["nang", "nang gat", "troi nang", "nong", "oi", "oi buc"],
    "mua": ["mua", "mua nhe", "mua phun", "mua to", "mua rao", "am uot"],
    "tuyet": ["tuyet", "co tuyet", "lanh buot", "gia ret", "ret dam"],
}

SEASON_SYNONYMS = {
    "xuan": ["xuan", "mua xuan", "spring"],
    "ha": ["ha", "mua ha", "summer", "he"],
    "thu": ["thu", "mua thu", "fall", "autumn"],
    "dong": ["dong", "mua dong", "winter"],
}

ACTIVITY_SYNONYMS = {
    "di lam": [
        "di lam",
        "di cong ty",
        "di van phong",
        "cong so",
        "di hop",
        "lam viec tai van phong",
        "phong van",
        "thuyet trinh",
        "gap doi tac",
        "cong tac",
        "meeting",
        "dress code cong so",
        "onsite",
        "coworking",
        "lam viec tu xa",
        "lam viec tai nha",
        "remote",
        "work from home",
    ],
    "di hoc": [
        "di hoc",
        "den truong",
        "den lop",
        "hoc o truong",
        "thi cu",
        "thi mon",
        "giang duong",
        "thu vien",
        "hoc nhom",
        "seminar",
        "workshop",
        "lab",
        "thuc tap tai truong",
    ],
    "di choi": [
        "di choi",
        "dao pho",
        "hen ho",
        "ra ngoai choi",
        "di cafe",
        "shopping",
        "mua sam",
        "du lich",
        "di bien",
        "picnic",
        "xem phim",
        "concert",
        "leo nui",
        "cam trai",
        "gym",
        "tap gym",
        "chay bo",
        "xe dap",
        "yoga",
        "di boi",
        "cong vien",
        "brunch",
        "nghi tai nha",
        "the thao",
    ],
    "tham gia tiec": [
        "di tiec",
        "tham gia tiec",
        "du tiec",
        "party",
        "su kien toi",
        "dam cuoi",
        "sinh nhat",
        "khai truong",
        "gala",
        "cocktail",
        "year end",
        "ra mat san pham",
        "le trao giai",
    ],
}

GENDER_SYNONYMS = {
    "men": ["nam", "con trai", "dan ong", "male", "men"],
    "women": ["nu", "con gai", "phu nu", "female", "women", "nữ"],
}

AGE_GROUP_SYNONYMS = {
    "children": ["tre em", "em be", "be trai", "be gai", "hoc sinh nho", "thieu nhi", "kids", "children"],
    "adult": ["nguoi lon", "truong thanh", "sinh vien", "di lam", "adult", "adults"],
}

ARTICLE_SYNONYMS = {
    "rain jacket": ["ao mua", "ao khoac di mua", "rain jacket"],
    "jackets": ["ao khoac", "ao jacket", "jacket"],
    "sweaters": ["ao len", "sweater"],
    "sweatshirts": ["ao ni", "ao hoodie", "hoodie", "sweatshirt"],
    "shirts": ["ao so mi", "so mi", "shirt"],
    "tshirts": ["ao thun", "ao phong", "t shirt", "tshirt"],
    "tops": ["ao kieu", "ao nu", "top"],
    "trousers": ["quan dai", "quan tay", "quan au", "quan"],
    "jeans": ["quan jean", "quan jeans", "jeans"],
    "shorts": ["quan short", "quan dui", "shorts"],
    "track pants": ["quan the thao", "track pants"],
    "dresses": ["vay lien", "dam", "vay", "dress"],
    "skirts": ["chan vay", "skirt"],
    "jumpsuit": ["jumpsuit", "do bay"],
    "suits": ["bo suit", "suit", "vest"],
    "blazers": ["blazer", "ao blazer"],
    "casual shoes": ["giay casual", "giay di choi"],
    "sports shoes": ["giay the thao", "sneaker", "sneakers"],
    "formal shoes": ["giay tay", "giay formal"],
    "sandals": ["sandal", "dep sandal"],
    "heels": ["giay cao got", "cao got"],
    "flats": ["giay bet", "giay bup be"],
    "backpacks": ["balo", "ba lo", "backpack"],
    "handbags": ["tui xach", "handbag"],
}

_VNCORE_SEGMENTER = None


@dataclass
class ContextResult:
    weather: Optional[str] = None
    season: Optional[str] = None
    activity: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    requested_article: Optional[str] = None
    temperature: Optional[float] = None
    confidence: float = 0.0
    source: str = "empty"
    # Độ tin cậy theo từng khóa (0–1): form > rule > model > mặc định giả định.
    field_confidence: Dict[str, float] = field(default_factory=dict)


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    base = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return base.replace("đ", "d").replace("Đ", "D")


def _init_vncore_segmenter():
    global _VNCORE_SEGMENTER
    if _VNCORE_SEGMENTER is not None:
        return _VNCORE_SEGMENTER
    if VnCoreNLP is None:
        return None
    if not os.path.exists(VNCORE_JAR_PATH):
        return None
    try:
        _VNCORE_SEGMENTER = VnCoreNLP(VNCORE_JAR_PATH, annotators="wseg", max_heap_size="-Xmx1g")
    except Exception:
        _VNCORE_SEGMENTER = None
    return _VNCORE_SEGMENTER


def _tokenize_with_vncore(text: str) -> str:
    segmenter = _init_vncore_segmenter()
    if segmenter is None:
        return text
    try:
        tokenized_sentences = segmenter.tokenize(text)
        tokens = []
        for sent in tokenized_sentences:
            for token in sent:
                tokens.append(token.replace("_", " "))
        if tokens:
            return " ".join(tokens)
    except Exception:
        pass
    return text


def normalize_text(text: str) -> str:
    text = (text or "").strip()
    text = _tokenize_with_vncore(text)
    text = text.lower()
    text = strip_accents(text)
    text = re.sub(r"[^a-z0-9\s°.,-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def preprocess_prompt_for_model(text: str) -> str:
    # Keep a single preprocessing entry-point for train/infer consistency.
    return normalize_text(text)


def _extract_temperature(prompt: str) -> Optional[float]:
    patterns = [
        r"(-?\d+(?:[\.,]\d+)?)\s*(?:do|độ|c|°c)",
        r"nhiet do\s*(-?\d+(?:[\.,]\d+)?)",
        r"khoang\s*(-?\d+(?:[\.,]\d+)?)\s*do",
        r"tam\s*(-?\d+(?:[\.,]\d+)?)\s*do",
        r"(-?\d+(?:[\.,]\d+)?)\s*do",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _extract_age_group(prompt: str) -> Optional[str]:
    for match in re.finditer(r"\b(\d{1,2})\s*(?:tuoi|t)\b", prompt):
        age = int(match.group(1))
        if age <= 15:
            return "children"
        return "adult"
    return _find_synonym_label(prompt, AGE_GROUP_SYNONYMS)


def _extract_requested_article(prompt: str) -> Optional[str]:
    return _find_synonym_label(prompt, ARTICLE_SYNONYMS)


def _find_synonym_label(prompt: str, synonym_map: Dict[str, list]) -> Optional[str]:
    ranked = []
    for label, variants in synonym_map.items():
        for token in variants:
            token_norm = normalize_text(token)
            token_regex = r"\b" + re.escape(token_norm).replace(r"\ ", r"\s+") + r"\b"
            if re.search(token_regex, prompt):
                ranked.append((len(token_norm), label))
    if ranked:
        ranked.sort(reverse=True)
        return ranked[0][1]
    return None


def rule_extract_context(prompt: str) -> ContextResult:
    norm = normalize_text(prompt)
    if not norm:
        return ContextResult()

    weather = _find_synonym_label(norm, WEATHER_SYNONYMS)
    season = _find_synonym_label(norm, SEASON_SYNONYMS)
    activity = _find_synonym_label(norm, ACTIVITY_SYNONYMS)
    gender = _find_synonym_label(norm, GENDER_SYNONYMS)
    age_group = _extract_age_group(norm)
    requested_article = _extract_requested_article(norm)
    temperature = _extract_temperature(norm)

    found = [weather, season, activity, gender, age_group, requested_article, temperature]
    confidence = sum(v is not None for v in found) / 7.0
    return ContextResult(
        weather=weather,
        season=season,
        activity=activity,
        gender=gender,
        age_group=age_group,
        requested_article=requested_article,
        temperature=temperature,
        confidence=confidence,
        source="rule",
    )


def load_nlp_model():
    if not os.path.exists(NLP_CONTEXT_PATH):
        return None
    return joblib.load(NLP_CONTEXT_PATH)


def model_predict_context(prompt: str, nlp_model) -> ContextResult:
    if not prompt or nlp_model is None:
        return ContextResult()

    text = preprocess_prompt_for_model(prompt)
    vectorizer = nlp_model["vectorizer"]
    models = nlp_model["models"]
    X = vectorizer.transform([text])

    values = {}
    field_confidence: Dict[str, float] = {}
    for field, clf in models.items():
        probs = clf.predict_proba(X)[0]
        best_idx = int(np.argmax(probs))
        values[field] = clf.classes_[best_idx]
        field_confidence[field] = float(probs[best_idx])

    # Không dùng mô hình hồi quy nhiệt độ nữa để tránh gợi ý phụ thuộc nhiệt độ suy diễn.
    temperature = None
    parts = list(field_confidence.values())
    confidence = float(np.mean(parts)) if parts else 0.0

    out = ContextResult(
        weather=values.get("weather"),
        season=values.get("season"),
        activity=values.get("activity"),
        gender=values.get("gender"),
        age_group=values.get("age_group"),
        requested_article=None,
        temperature=temperature,
        confidence=confidence,
        source="model",
        field_confidence=dict(field_confidence),
    )
    return out


def fuse_context(
    form_context: Dict[str, Optional[str]],
    rule_context: ContextResult,
    model_context: ContextResult,
) -> ContextResult:
    """Ưu tiên: form > luật từ câu > mô hình > giá trị mặc định (chỉ cho slot phục vụ vector trang phục).

    Giới tính không bắt buộc: nếu không có tín hiệu thì để None (lọc ảnh tùy chọn).
    """
    form_temperature = form_context.get("temperature")
    temperature_value = None
    if form_temperature not in ("", None):
        try:
            temperature_value = float(str(form_temperature).replace(",", "."))
        except ValueError:
            temperature_value = None

    form_gender = form_context.get("gender") or None
    if form_gender == "":
        form_gender = None

    fused = ContextResult(
        weather=form_context.get("weather") or None,
        season=form_context.get("season") or None,
        activity=form_context.get("activity") or None,
        gender=form_gender,
        age_group=form_context.get("age_group") or None,
        requested_article=form_context.get("requested_article") or None,
        temperature=temperature_value,
        source="fusion",
        field_confidence={},
    )
    if fused.weather not in ALLOWED_WEATHER:
        fused.weather = None
    if fused.season not in ALLOWED_SEASON:
        fused.season = None
    if fused.activity not in ALLOWED_ACTIVITY:
        fused.activity = None
    if fused.gender not in ALLOWED_GENDER:
        fused.gender = None
    if fused.age_group not in ALLOWED_AGE_GROUP:
        fused.age_group = None
    if fused.requested_article not in ALLOWED_ARTICLE_TYPES:
        fused.requested_article = None

    fc: Dict[str, float] = {}

    def set_fc(field: str, conf: float):
        fc[field] = conf

    for fname in ("weather", "season", "activity", "gender", "age_group", "requested_article"):
        v = getattr(fused, fname)
        if v:
            set_fc(fname, CONF_FORM)

    if fused.temperature is not None:
        set_fc("temperature", CONF_FORM)

    for fname in ("weather", "season", "activity", "gender", "age_group", "requested_article"):
        if getattr(fused, fname):
            continue
        rule_value = getattr(rule_context, fname)
        if rule_value:
            setattr(fused, fname, rule_value)
            set_fc(fname, CONF_RULE)

    if fused.temperature is None and rule_context.temperature is not None:
        fused.temperature = rule_context.temperature
        set_fc("temperature", CONF_RULE)

    model_fc = model_context.field_confidence or {}
    for fname in ("weather", "season", "activity", "gender", "age_group"):
        if getattr(fused, fname):
            continue
        mv = getattr(model_context, fname)
        if mv:
            setattr(fused, fname, mv)
            set_fc(fname, float(model_fc.get(fname, CONF_MODEL_UNKNOWN)))

    if not fused.requested_article and model_context.requested_article in ALLOWED_ARTICLE_TYPES:
        fused.requested_article = model_context.requested_article
        set_fc("requested_article", float(model_fc.get("requested_article", CONF_MODEL_UNKNOWN)))

    for fname, allowed in (
        ("weather", ALLOWED_WEATHER),
        ("season", ALLOWED_SEASON),
        ("activity", ALLOWED_ACTIVITY),
        ("gender", ALLOWED_GENDER),
        ("age_group", ALLOWED_AGE_GROUP),
        ("requested_article", ALLOWED_ARTICLE_TYPES),
    ):
        v = getattr(fused, fname)
        if v is not None and v not in allowed:
            setattr(fused, fname, None)
            fc.pop(fname, None)

    for fname in ("weather", "season", "activity"):
        if not getattr(fused, fname):
            default = {"weather": DEFAULT_WEATHER, "season": DEFAULT_SEASON, "activity": DEFAULT_ACTIVITY}[fname]
            setattr(fused, fname, default)
            set_fc(fname, CONF_DEFAULT_SLOT)

    if not fused.age_group:
        fused.age_group = DEFAULT_AGE_GROUP
        set_fc("age_group", CONF_DEFAULT_SLOT)

    if fused.temperature is None:
        fused.temperature = DEFAULT_TEMPERATURE
        set_fc("temperature", CONF_DEFAULT_SLOT)

    fused.field_confidence = fc
    keys_for_mean = ["weather", "season", "activity", "age_group", "temperature"]
    if fused.gender in ALLOWED_GENDER:
        keys_for_mean.append("gender")
    if fused.requested_article in ALLOWED_ARTICLE_TYPES:
        keys_for_mean.append("requested_article")
    fused.confidence = float(np.mean([fc.get(k, CONF_DEFAULT_SLOT) for k in keys_for_mean]))
    return fused

