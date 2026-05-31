import os
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "data", "styles.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "deep_outfit_model.pt")
PREPROCESS_PATH = os.path.join(MODEL_DIR, "deep_preprocess.joblib")

FEATURE_COLUMNS = ["gender", "ageGroup", "weather", "season", "activity"]
BASE_REQUIRED_COLUMNS = ["gender", "season", "usage", "articleType", "productDisplayName"]


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


class OutfitNet(nn.Module):
    def __init__(self, input_dim: int, num_classes: int):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        return self.layers(x)


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in FEATURE_COLUMNS + ["articleType"]:
        work[col] = work[col].astype(str).str.strip().str.lower()
    work["productDisplayName"] = work["productDisplayName"].astype(str).str.strip()
    return work[FEATURE_COLUMNS + ["articleType", "productDisplayName"]]


def main() -> None:
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Khong tim thay dataset: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH, on_bad_lines="skip", engine="python")
    missing = [c for c in BASE_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset thieu cot bat buoc: {missing}")

    df = enrich_fashion_context(df).dropna(subset=BASE_REQUIRED_COLUMNS).drop_duplicates().reset_index(drop=True)
    train_df = build_training_frame(df)

    X_raw = train_df[FEATURE_COLUMNS].astype(str).values
    y_raw = train_df["articleType"].astype(str).values

    onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    label_encoder = LabelEncoder()

    X = onehot.fit_transform(X_raw).astype(np.float32)
    y = label_encoder.fit_transform(y_raw).astype(np.int64)

    class_counts = np.bincount(y)
    can_stratify = np.all(class_counts[class_counts > 0] >= 2)
    stratify_target = y if can_stratify else None

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=stratify_target)

    model = OutfitNet(input_dim=X.shape[1], num_classes=len(label_encoder.classes_))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    X_train_t = torch.tensor(X_train)
    y_train_t = torch.tensor(y_train)
    X_val_t = torch.tensor(X_val)
    y_val_t = torch.tensor(y_val)

    batch_size = 512
    epochs = 12

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(X_train_t.size(0))
        epoch_loss = 0.0
        for i in range(0, X_train_t.size(0), batch_size):
            idx = perm[i : i + batch_size]
            xb = X_train_t[idx]
            yb = y_train_t[idx]

            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        model.eval()
        with torch.no_grad():
            val_logits = model(X_val_t)
            val_pred = torch.argmax(val_logits, dim=1)
            val_acc = (val_pred == y_val_t).float().mean().item()

        print(f"Epoch {epoch + 1}/{epochs} - loss: {epoch_loss:.4f} - val_acc: {val_acc:.4f}")

    article_examples = train_df.groupby("articleType")["productDisplayName"].apply(lambda s: list(s.head(5))).to_dict()

    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "input_dim": X.shape[1],
            "num_classes": len(label_encoder.classes_),
            "feature_columns": FEATURE_COLUMNS,
        },
        MODEL_PATH,
    )

    joblib.dump(
        {
            "onehot": onehot,
            "label_encoder": label_encoder,
            "article_examples": article_examples,
            "feature_columns": FEATURE_COLUMNS,
        },
        PREPROCESS_PATH,
    )

    print("Da train xong deep model.")
    print(f"Model luu tai: {MODEL_PATH}")
    print(f"Preprocess luu tai: {PREPROCESS_PATH}")
    print(f"So lop articleType: {len(label_encoder.classes_)}")


if __name__ == "__main__":
    main()
