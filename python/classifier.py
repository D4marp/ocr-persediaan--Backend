import re
import json
import joblib
import numpy as np
from pathlib import Path
from sklearn.base import clone
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score, accuracy_score

from model_selector import MODEL_VERSION, select_best_model

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "classifier.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"
DATASET_PATH = Path("data/ground_truth.json")

KEYWORDS_MASUK = [
    "beli", "pembelian", "terima", "masuk", "stok masuk",
    "invoice", "faktur beli", "po", "purchase", "supplier",
    "nota beli", "tanda terima", "penerimaan"
]
KEYWORDS_KELUAR = [
    "jual", "penjualan", "keluar", "kirim", "nota jual",
    "faktur jual", "so", "sale", "customer", "pelanggan",
    "nota penjualan", "tanda kirim", "pengeluaran"
]


class TransaksiClassifier:
    def __init__(self):
        self.pipeline = None
        self.model_name = "untrained"
        self._load_or_init()

    def _load_or_init(self):
        if MODEL_PATH.exists():
            self.pipeline = joblib.load(MODEL_PATH)
            metrics = self.get_metrics()
            self.model_name = metrics.get("selected_model", metrics.get("model_version", "loaded"))
        else:
            self.pipeline = None
            self.model_name = "untrained"

    def is_loaded(self) -> bool:
        return MODEL_PATH.exists() and self.pipeline is not None

    def needs_retrain(self) -> bool:
        if not self.is_loaded():
            return True
        metrics = self.get_metrics()
        return metrics.get("model_version") != MODEL_VERSION

    def train(self, data: list[dict]) -> dict:
        """Auto-select model terbaik, lalu fit ulang pada seluruh data."""
        texts = [d["text"] for d in data]
        labels = [d["jenis"] for d in data]

        # 1. Pilih model terbaik via cross-validation
        self.pipeline, self.model_name, comparison = select_best_model(texts, labels)

        # 2. Evaluasi holdout untuk laporan
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
        holdout_pipe = clone(self.pipeline)
        holdout_pipe.fit(X_train, y_train)
        y_pred = holdout_pipe.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)

        # 3. Simpan model final (sudah fit pada full data dari select_best_model)
        joblib.dump(self.pipeline, MODEL_PATH)

        best_cv = next(c for c in comparison if c["model"] == self.model_name)
        metrics = {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "f1_score": round(float(f1_score(y_test, y_pred, average="weighted")), 4),
            "precision": round(float(report["weighted avg"]["precision"]), 4),
            "recall": round(float(report["weighted avg"]["recall"]), 4),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "total_samples": len(texts),
            "model_version": MODEL_VERSION,
            "selected_model": self.model_name,
            "cv_f1_mean": best_cv.get("cv_f1_mean"),
            "cv_f1_std": best_cv.get("cv_f1_std"),
            "model_comparison": comparison,
            "report": report,
        }
        METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
        return metrics

    def classify(self, text: str) -> dict:
        text_lower = text.lower()
        if not self.is_loaded():
            jenis = self._rule_based(text_lower)
            conf = 0.60
            model_used = "rule_based"
        else:
            jenis = self.pipeline.predict([text])[0]
            conf = self._confidence(text)
            model_used = self.model_name

        entities = self._extract_entities(text)
        return {
            "jenis": jenis,
            "nama_produk": entities.get("nama_produk", ""),
            "kode_barang": entities.get("kode_barang", ""),
            "jumlah": entities.get("jumlah"),
            "satuan": entities.get("satuan", ""),
            "harga_satuan": entities.get("harga_satuan"),
            "total": entities.get("total"),
            "tanggal": entities.get("tanggal", ""),
            "ml_confidence": conf,
            "model_used": model_used,
        }

    def _confidence(self, text: str) -> float:
        clf = self.pipeline.named_steps["clf"]
        vec = self.pipeline.named_steps["tfidf"]
        X = vec.transform([text])

        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(X)[0]
            return round(float(max(proba)), 4)

        if hasattr(clf, "decision_function"):
            score = clf.decision_function(X)[0]
            raw = abs(float(score)) if np.isscalar(score) else float(max(np.abs(score)))
            return round(1 / (1 + np.exp(-raw)), 4)

        return 0.80

    def _rule_based(self, text: str) -> str:
        score_masuk = sum(1 for kw in KEYWORDS_MASUK if kw in text)
        score_keluar = sum(1 for kw in KEYWORDS_KELUAR if kw in text)
        return "barang_masuk" if score_masuk >= score_keluar else "barang_keluar"

    def _extract_entities(self, text: str) -> dict:
        result = {}

        date_patterns = [
            r'\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b',
            r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agt|Sep|Okt|Nov|Des)\w*\s+(\d{4})\b',
        ]
        for pat in date_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["tanggal"] = m.group(0)
                break

        raw_nums = re.findall(r'\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\b', text)
        nums = []
        for a in raw_nums:
            try:
                nums.append(float(a.replace('.', '').replace(',', '.')))
            except ValueError:
                pass

        if nums:
            result["total"] = max(nums)
            small = [n for n in nums if n <= 9999]
            if small:
                result["jumlah"] = small[0]
            big = [n for n in nums if 1000 < n < max(nums)]
            if big:
                result["harga_satuan"] = min(big)

        satuan_match = re.search(
            r'\b(pcs|buah|kg|gram|gr|liter|lt|dus|karton|lusin|box|pack|botol|kantong|lembar|roll)\b',
            text, re.IGNORECASE
        )
        if satuan_match:
            result["satuan"] = satuan_match.group(1).lower()

        kode_match = re.search(r'\b([A-Z]{2,6}[-_]?\d{3,8})\b', text)
        if kode_match:
            result["kode_barang"] = kode_match.group(1)

        prod_match = re.search(
            r'(?:barang|produk|item|nama)[:\s]+([A-Za-z0-9\s]{3,40})',
            text, re.IGNORECASE
        )
        if prod_match:
            result["nama_produk"] = prod_match.group(1).strip()
        else:
            item_match = re.search(
                r'\n([A-Z][A-Za-z0-9\s]{2,35})\s+\d+\s*(?:kg|liter|lt|pcs|buah|dus|karton|pack|botol|sak|batang|cup|set|roll|lembar|slop|bungkus|box)\b',
                text, re.IGNORECASE
            )
            if item_match:
                result["nama_produk"] = item_match.group(1).strip()

        return result

    def get_metrics(self) -> dict:
        if METRICS_PATH.exists():
            return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        return {
            "model_version": "untrained",
            "note": "POST /train dengan data berlabel untuk memulai training.",
        }

    @staticmethod
    def load_dataset() -> list[dict]:
        if not DATASET_PATH.exists():
            return []
        raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        return raw.get("data", raw)

    @staticmethod
    def get_dataset_info() -> dict:
        if not DATASET_PATH.exists():
            return {"available": False, "path": str(DATASET_PATH)}
        raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        data = raw.get("data", [])
        masuk = sum(1 for d in data if d.get("jenis") == "barang_masuk")
        keluar = sum(1 for d in data if d.get("jenis") == "barang_keluar")
        return {
            "available": True,
            "version": raw.get("version", "unknown"),
            "description": raw.get("description", ""),
            "source": raw.get("source", ""),
            "total_samples": len(data),
            "label_distribution": {"barang_masuk": masuk, "barang_keluar": keluar},
            "umkm_count": raw.get("umkm_count", len({d.get("umkm_id") for d in data if d.get("umkm_id")})),
            "umkm_ids": raw.get("umkm_ids", sorted({d.get("umkm_id") for d in data if d.get("umkm_id")})),
        }

    def seed_from_dataset(self) -> dict | None:
        if not self.needs_retrain():
            return None
        data = self.load_dataset()
        if len(data) < 10:
            return None
        return self.train(data)
