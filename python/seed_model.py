"""Train model dari dataset ground truth bawaan."""
import json
from pathlib import Path

from classifier import TransaksiClassifier, DATASET_PATH

def load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {DATASET_PATH}")
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return raw.get("data", raw)


def seed():
    data = load_dataset()
    if len(data) < 10:
        raise ValueError(f"Dataset terlalu kecil: {len(data)} sampel (minimal 10)")

    clf = TransaksiClassifier()
    metrics = clf.train(data)
    print(f"Model terpilih: {metrics.get('selected_model')}")
    print(f"CV F1: {metrics.get('cv_f1_mean')} | Holdout accuracy: {metrics['accuracy']}")
    return metrics


if __name__ == "__main__":
    seed()
