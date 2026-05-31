import os
import random
from itertools import product

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from nlp_context import MODEL_DIR, NLP_CONTEXT_PATH, preprocess_prompt_for_model

random.seed(42)
np.random.seed(42)

WEATHER_VARIANTS = {
    "nang": ["trời nắng", "nắng nhẹ", "hôm nay khá nóng", "nắng to", "thời tiết oi bức"],
    "mua": ["trời mưa", "mưa nhẹ", "mưa phùn", "hôm nay ẩm ướt", "mưa rào"],
    "tuyet": ["trời có tuyết", "rất lạnh và có tuyết", "thời tiết tuyết rơi", "lạnh buốt"],
}

SEASON_VARIANTS = {
    "xuan": ["mùa xuân", "đầu xuân", "spring"],
    "ha": ["mùa hạ", "mùa hè", "summer"],
    "thu": ["mùa thu", "cuối thu", "fall"],
    "dong": ["mùa đông", "giữa đông", "winter"],
}

ACTIVITY_VARIANTS = {
    "di lam": [
        "đi làm",
        "đi công ty",
        "đi văn phòng",
        "đi làm cả ngày",
        "họp với khách hàng",
        "họp team nội bộ",
        "làm việc hybrid",
        "đi phỏng vấn xin việc",
        "thuyết trình trước sếp",
        "đi công tác ngắn ngày",
        "làm việc tại coworking",
        "dress code công sở",
        "đi gặp đối tác buổi sáng",
        "làm việc client onsite",
        "đi training nội bộ công ty",
        "làm việc remote tại nhà",
        "họp online nhưng vẫn mặc chỉnh",
    ],
    "di hoc": [
        "đi học",
        "đến lớp",
        "đi học cả ngày",
        "hôm nay lên giảng đường",
        "ôn thi cuối kỳ",
        "học nhóm ở thư viện",
        "đi thi môn chính",
        "tham gia seminar trường",
        "làm báo cáo lab",
        "đi học thêm buổi tối",
        "đi dự workshop kỹ năng",
        "đi học online nhưng vẫn ra quán",
        "đi thực tập có mặt tại trường",
    ],
    "di choi": [
        "đi chơi",
        "đi dạo phố",
        "đi cafe với bạn",
        "đi hẹn hò",
        "đi shopping cuối tuần",
        "đi du lịch ngắn ngày",
        "đi biển nghỉ mát",
        "đi picnic ngoài trời",
        "đi xem phim rạp",
        "đi concert ngoài trời",
        "đi leo núi nhẹ",
        "đi cắm trại",
        "đi gym buổi chiều",
        "đi chạy bộ sáng",
        "đi xe đạp thể thao",
        "tập yoga ở studio",
        "đi bơi hồ bơi",
        "ở nhà nghỉ nhưng vẫn muốn mặc đẹp",
        "đi dạo công viên",
        "đi chợ cuối tuần",
        "đi brunch cuối tuần",
    ],
    "tham gia tiec": [
        "đi tiệc",
        "tham gia tiệc tối",
        "dự sự kiện",
        "party buổi tối",
        "đi đám cưới bạn",
        "dự tiệc sinh nhật",
        "tiệc cocktail công ty",
        "year end party",
        "dự gala từ thiện",
        "tiệc khai trương cửa hàng",
        "tiệc tối semi formal",
        "dự lễ trao giải",
        "tiệc ra mắt sản phẩm",
    ],
}

GENDER_VARIANTS = {
    "men": ["tôi là nam", "đồ cho nam", "phong cách nam", "mặc cho con trai"],
    "women": ["tôi là nữ", "đồ cho nữ", "phong cách nữ", "mặc cho con gái"],
}

AGE_GROUP_VARIANTS = {
    "children": ["cho trẻ em", "cho bé 8 tuổi", "cho học sinh nhỏ", "đồ trẻ con", "cho thiếu nhi"],
    "adult": ["cho người lớn", "tôi 25 tuổi", "phong cách trưởng thành", "cho sinh viên", "cho người đi làm"],
}

TEMPERATURE_BY_SEASON = {
    "xuan": (20, 30),
    "ha": (29, 38),
    "thu": (18, 27),
    "dong": (8, 20),
}

TEMPLATES = [
    "Hôm nay {weather}, {season}, tôi {activity}, {gender}, {age_group}, nhiệt độ khoảng {temp} độ C.",
    "{gender}, {age_group}, thời tiết {weather}, hiện tại là {season}, tôi chuẩn bị {activity}, tầm {temp} độ.",
    "Bạn gợi ý giúp tôi vì {weather}, đang {season}, tôi cần đồ để {activity}, {age_group}, mức {temp} độ C, {gender}.",
    "Mình muốn mặc đẹp khi {activity}; bối cảnh là {weather}, {season}, {age_group}, nhiệt độ {temp}°C, {gender}.",
]


def make_sample(weather, season, activity, gender, age_group):
    temp_min, temp_max = TEMPERATURE_BY_SEASON[season]
    temp = round(random.uniform(temp_min, temp_max), 1)
    sentence = random.choice(TEMPLATES).format(
        weather=random.choice(WEATHER_VARIANTS[weather]),
        season=random.choice(SEASON_VARIANTS[season]),
        activity=random.choice(ACTIVITY_VARIANTS[activity]),
        gender=random.choice(GENDER_VARIANTS[gender]),
        age_group=random.choice(AGE_GROUP_VARIANTS[age_group]),
        temp=temp,
    )
    return {
        "text": sentence,
        "weather": weather,
        "season": season,
        "activity": activity,
        "gender": gender,
        "age_group": age_group,
        "temperature": temp,
    }


def build_dataset(multiplier=14):
    rows = []
    for weather, season, activity, gender, age_group in product(
        WEATHER_VARIANTS.keys(),
        SEASON_VARIANTS.keys(),
        ACTIVITY_VARIANTS.keys(),
        GENDER_VARIANTS.keys(),
        AGE_GROUP_VARIANTS.keys(),
    ):
        for _ in range(multiplier):
            rows.append(make_sample(weather, season, activity, gender, age_group))
    random.shuffle(rows)
    return rows


def main():
    rows = build_dataset()
    texts = [preprocess_prompt_for_model(r["text"]) for r in rows]

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=18000)
    X = vectorizer.fit_transform(texts)

    y_weather = np.array([r["weather"] for r in rows])
    y_season = np.array([r["season"] for r in rows])
    y_activity = np.array([r["activity"] for r in rows])
    y_gender = np.array([r["gender"] for r in rows])
    y_age_group = np.array([r["age_group"] for r in rows])

    idx = np.arange(len(rows))
    train_idx, val_idx = train_test_split(idx, test_size=0.2, random_state=42, shuffle=True)

    X_train, X_val = X[train_idx], X[val_idx]

    models = {}
    for name, y in [
        ("weather", y_weather),
        ("season", y_season),
        ("activity", y_activity),
        ("gender", y_gender),
        ("age_group", y_age_group),
    ]:
        model = LogisticRegression(max_iter=1200, n_jobs=None)
        model.fit(X_train, y[train_idx])
        pred = model.predict(X_val)
        acc = accuracy_score(y[val_idx], pred)
        print(f"{name} accuracy: {acc:.4f}")
        models[name] = model

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"vectorizer": vectorizer, "models": models, "training_size": len(rows)}, NLP_CONTEXT_PATH)
    print(f"Saved NLP context model: {NLP_CONTEXT_PATH}")


if __name__ == "__main__":
    main()
