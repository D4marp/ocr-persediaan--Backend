"""
Evaluasi Stage I (document format classifier) dengan leave-one-out CV.

Ambang/parameter TIDAK disetel manual pada data uji. Model dilatih ulang pada
n-1 sampel dan diuji pada sampel yang ditahan, sehingga akurasi yang dilaporkan
adalah akurasi out-of-sample. Ini penting karena n=41 terlalu kecil untuk split
train/test yang stabil.
"""
import json
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.tree import DecisionTreeClassifier

FEATURES = ["cv_run", "ink_gain", "run_gain", "short_run_ratio", "periodicity", "mean_run"]
CLASSES = ["thermal_clean", "handwritten", "dot_matrix"]


def load():
    base = json.load(open("data/format_features.json"))
    morph = json.load(open("data/morph_features.json"))
    labels = {k: v["format"] for k, v in json.load(open("data/format_labels.json")).items()}
    keys = sorted(set(base) & set(morph) & set(labels))
    X, y = [], []
    for k in keys:
        row = {**base[k], **morph[k]}
        X.append([row[f] for f in FEATURES])
        y.append(labels[k])
    return np.array(X), np.array(y), keys


def main():
    X, y, keys = load()
    print(f"n = {len(y)}  features = {FEATURES}")
    print("class counts:", {c: int((y == c).sum()) for c in CLASSES})

    for name, clf in [
        ("LogisticRegression", make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1.0))),
        ("DecisionTree(d=3)", DecisionTreeClassifier(max_depth=3, random_state=0)),
    ]:
        pred = cross_val_predict(clf, X, y, cv=LeaveOneOut())
        acc = (pred == y).mean()
        print(f"\n=== {name} — leave-one-out CV ===")
        print(f"accuracy = {acc*100:.1f}%  ({int((pred==y).sum())}/{len(y)})")
        cm = confusion_matrix(y, pred, labels=CLASSES)
        print("confusion matrix (rows=true, cols=pred):", CLASSES)
        for c, row in zip(CLASSES, cm):
            print(f"  {c:15s} {row}")
        print(classification_report(y, pred, labels=CLASSES, digits=3, zero_division=0))
        for k, t, p in zip(keys, y, pred):
            if t != p:
                print(f"  misclassified: {k}  true={t}  pred={p}")

    # model final untuk pipeline (dilatih pada seluruh data)
    final = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
    final.fit(X, y)
    import pickle
    with open("models/format_classifier.pkl", "wb") as f:
        pickle.dump({"model": final, "features": FEATURES}, f)
    print("\nsaved models/format_classifier.pkl")


if __name__ == "__main__":
    main()
