import os
import joblib
import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.neighbors import NearestNeighbors

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "data", "styles.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "fashion_knn.joblib")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "feature_vectorizer.joblib")
ITEMS_PATH = os.path.join(MODEL_DIR, "fashion_items.joblib")

FEATURE_COLUMNS = [
    "gender",
    "ageGroup",
    "weather",
    "activity",
    "masterCategory",
    "subCategory",
    "articleType",
    "baseColour",
    "season",
    "usage",
]
REQUIRED_COLUMNS = FEATURE_COLUMNS + ["productDisplayName"]
BASE_REQUIRED_COLUMNS = [
    "gender",
    "masterCategory",
    "subCategory",
    "articleType",
    "baseColour",
    "season",
    "usage",
    "productDisplayName",
]


def enrich_fashion_context(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in ["gender", "season", "usage"]:
        work[col] = work[col].astype(str).str.strip().str.lower()
    if "ageGroup" not in work.columns:
        work["ageGroup"] = work["gender"].map(
            {"boys": "children", "girls": "children", "men": "adult", "women": "adult", "unisex": "all"}
        ).fillna("all")
    if "weather" not in work.columns:
        work["weather"] = work["season"].map({"summer": "nang", "spring": "nang", "fall": "mua", "winter": "tuyet"}).fillna(
            "nang"
        )
    if "activity" not in work.columns:
        work["activity"] = work["usage"].map(
            {
                "formal": "di lam",
                "smart casual": "di lam",
                "casual": "di choi",
                "sports": "di choi",
                "travel": "di choi",
                "home": "di choi",
                "ethnic": "tham gia tiec",
                "party": "tham gia tiec",
            }
        ).fillna("di choi")
    return work


def main() -> None:
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Khong tim thay dataset: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH, on_bad_lines="skip", engine="python")
    missing_columns = [col for col in BASE_REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Dataset thieu cot bat buoc: {missing_columns}")

    df = enrich_fashion_context(df)
    df = df[REQUIRED_COLUMNS].dropna().drop_duplicates().reset_index(drop=True)
    if df.empty:
        raise ValueError("Dataset rong sau khi lam sach.")

    feature_dicts = df[FEATURE_COLUMNS].astype(str).to_dict(orient="records")
    vectorizer = DictVectorizer(sparse=True)
    X = vectorizer.fit_transform(feature_dicts)

    model = NearestNeighbors(metric="cosine", algorithm="brute")
    model.fit(X)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(df.to_dict(orient="records"), ITEMS_PATH)

    print("Train thanh cong.")
    print(f"So mau huan luyen: {len(df)}")
    print(f"Model: {MODEL_PATH}")
    print(f"Vectorizer: {VECTORIZER_PATH}")
    print(f"Items: {ITEMS_PATH}")


if __name__ == "__main__":
    main()
