import os
import pickle
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")
MODEL_DIR = os.path.join(BASE_DIR, "model")
FEATURE_DATA_PATH = os.path.join(MODEL_DIR, "feature_data.pkl")
FILE_NAMES_PATH = os.path.join(MODEL_DIR, "file_names.pkl")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

IMAGE_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


def build_feature_model():
    weights = models.ResNet50_Weights.DEFAULT
    backbone = models.resnet50(weights=weights)
    feature_model = torch.nn.Sequential(*list(backbone.children())[:-1]).to(DEVICE)
    feature_model.eval()
    return feature_model


def extract_feature(image_path: str, model) -> np.ndarray:
    image = Image.open(image_path).convert("RGB")
    tensor = IMAGE_TRANSFORM(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        embedding = model(tensor).squeeze().detach().cpu().numpy().astype(np.float32)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm


def main() -> None:
    if not os.path.exists(IMAGE_DIR):
        raise FileNotFoundError(f"Khong tim thay thu muc anh: {IMAGE_DIR}")

    files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not files:
        raise ValueError("Khong co anh nao trong data/images")

    print(f"Dang trich xuat bang PyTorch tren: {DEVICE}")
    model = build_feature_model()

    features = []
    for idx, file in enumerate(files, start=1):
        image_path = os.path.join(IMAGE_DIR, file)
        features.append(extract_feature(image_path, model))
        if idx % 500 == 0:
            print(f"Da xu ly {idx}/{len(files)} anh...")

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(FILE_NAMES_PATH, "wb") as f:
        pickle.dump(files, f)
    with open(FEATURE_DATA_PATH, "wb") as f:
        pickle.dump(np.array(features), f)

    print("Da tao xong feature image.")
    print(f"So anh: {len(files)}")
    print(f"Luu file names: {FILE_NAMES_PATH}")
    print(f"Luu features: {FEATURE_DATA_PATH}")


if __name__ == "__main__":
    main()
