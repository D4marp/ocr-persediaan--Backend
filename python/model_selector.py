"""Auto-select model klasifikasi terbaik via cross-validation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

MODEL_VERSION = "auto-select-v2"
CV_FOLDS = 5
RANDOM_STATE = 42


@dataclass
class ModelCandidate:
    name: str
    pipeline: Pipeline
    vectorizer: str


def _vectorizer(kind: str) -> TfidfVectorizer:
    if kind == "word_12":
        return TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            min_df=1,
            max_df=0.95,
        )
    return TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 3),
        max_features=8000,
        sublinear_tf=True,
        min_df=1,
        max_df=0.95,
    )


def build_candidates() -> list[ModelCandidate]:
    classifiers = {
        "LinearSVC": LinearSVC(C=0.5, max_iter=3000, class_weight="balanced", random_state=RANDOM_STATE),
        "LogisticRegression": LogisticRegression(
            C=1.0, max_iter=2000, class_weight="balanced", solver="liblinear", random_state=RANDOM_STATE
        ),
        "SGDClassifier": SGDClassifier(
            loss="log_loss", alpha=1e-4, max_iter=2500, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "RidgeClassifier": RidgeClassifier(alpha=1.0, class_weight="balanced", random_state=RANDOM_STATE),
        "ComplementNB": ComplementNB(alpha=0.1),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=12, class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
        ),
    }

    candidates: list[ModelCandidate] = []
    for vec_kind in ("word_12", "word_13"):
        for clf_name, clf in classifiers.items():
            pipe = Pipeline([
                ("tfidf", _vectorizer(vec_kind)),
                ("clf", clf),
            ])
            candidates.append(ModelCandidate(
                name=f"{clf_name}+{vec_kind}",
                pipeline=pipe,
                vectorizer=vec_kind,
            ))
    return candidates


def select_best_model(texts: list[str], labels: list[str]) -> tuple[Pipeline, str, list[dict]]:
    """Pilih pipeline dengan F1 tertinggi (5-fold stratified CV)."""
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    comparison: list[dict] = []

    for cand in build_candidates():
        pipe = cand.pipeline
        try:
            scores = cross_val_score(
                pipe, texts, labels, cv=cv, scoring="f1_weighted", n_jobs=-1
            )
            mean_f1 = float(np.mean(scores))
            std_f1 = float(np.std(scores))
        except Exception as exc:
            comparison.append({
                "model": cand.name,
                "cv_f1_mean": 0.0,
                "cv_f1_std": 0.0,
                "error": str(exc),
            })
            continue

        comparison.append({
            "model": cand.name,
            "vectorizer": cand.vectorizer,
            "cv_f1_mean": round(mean_f1, 4),
            "cv_f1_std": round(std_f1, 4),
        })

    valid = [c for c in comparison if "error" not in c]
    if not valid:
        raise RuntimeError("Semua kandidat model gagal dievaluasi")

    valid.sort(key=lambda x: (x["cv_f1_mean"], -x["cv_f1_std"]), reverse=True)
    best_name = valid[0]["model"]

    best_cand = next(c for c in build_candidates() if c.name == best_name)
    best_pipe = clone(best_cand.pipeline)
    best_pipe.fit(texts, labels)

    return best_pipe, best_name, comparison
