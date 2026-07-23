"""Worker internal: OCR + ML dalam satu proses Python.

Jalur /extract memakai pipeline FA-OCR (format-aware): klasifikasi jenis cetak
nota -> preprocessing adaptif -> fusi multi-PSM -> routing confidence per format.
"""
import logging
import os
import tempfile
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

import fa_ocr
from classifier import TransaksiClassifier

logger = logging.getLogger("processing-worker")
classifier = TransaksiClassifier()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Ambang confidence per format untuk routing verifikasi manusia (Stage IV).
# Nilai diturunkan dari distribusi confidence terukur per format: rata-rata
# 75.6 (thermal) vs 42.0 (dot-matrix), sehingga ambang tunggal akan menolak
# hampir semua nota dot-matrix terlepas dari benar/tidaknya hasil.
# Nota tulisan tangan selalu diverifikasi manusia (lihat fa_ocr.route_decision).
CONF_THRESHOLDS = {
    fa_ocr.FMT_THERMAL: 70.0,
    fa_ocr.FMT_DOT_MATRIX: 50.0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if classifier.needs_retrain():
        metrics = classifier.seed_from_dataset()
        if metrics:
            logger.info(
                "Model terpilih: %s | CV F1=%.4f | holdout acc=%.4f",
                metrics.get("selected_model"),
                metrics.get("cv_f1_mean", 0),
                metrics.get("accuracy", 0),
            )
        else:
            logger.warning("Model belum trained — dataset tidak tersedia")
    yield


app = FastAPI(title="Processing Worker", version="1.0.0", lifespan=lifespan)


# ── OCR ──────────────────────────────────────────────────

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Format tidak didukung: {file.content_type}. Gunakan JPG/PNG/WEBP.",
        )

    start = time.time()
    tmp_path = None
    try:
        image_bytes = await file.read()
        suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        fa = fa_ocr.run(tmp_path, thresholds=CONF_THRESHOLDS)
        result = {
            "text": fa["text"],
            "confidence": fa["confidence"],
            "ocr_mode": "fa-ocr-fusion",
            "format_detected": fa["format"],
            "routing_decision": fa["decision"],
            "per_psm_confidence": fa["per_psm_conf"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR gagal: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    result["processing_time_ms"] = round((time.time() - start) * 1000, 2)
    result["filename"] = file.filename
    return result


# ── ML ───────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    text: str
    dokumen_id: str = ""


class TrainItem(BaseModel):
    text: str
    jenis: str


class TrainRequest(BaseModel):
    data: list[TrainItem]


@app.post("/classify")
def classify(req: ClassifyRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Teks kosong")
    return classifier.classify(req.text)


@app.post("/train")
def train(req: TrainRequest):
    if len(req.data) < 10:
        raise HTTPException(status_code=400, detail="Minimal 10 sampel untuk training")

    valid_jenis = {"barang_masuk", "barang_keluar"}
    for item in req.data:
        if item.jenis not in valid_jenis:
            raise HTTPException(
                status_code=400,
                detail=f"Jenis '{item.jenis}' tidak valid. Gunakan barang_masuk atau barang_keluar.",
            )

    data = [{"text": d.text, "jenis": d.jenis} for d in req.data]
    return classifier.train(data)


@app.get("/metrics")
def metrics():
    return classifier.get_metrics()


@app.get("/dataset")
def dataset_info():
    return classifier.get_dataset_info()


@app.post("/seed")
def seed():
    data = classifier.load_dataset()
    if len(data) < 10:
        raise HTTPException(status_code=404, detail="Dataset bawaan tidak ditemukan atau terlalu kecil")
    result = classifier.train(data)
    return {"message": "Model berhasil ditraining dari dataset bawaan", "metrics": result}


@app.get("/models")
def models_comparison():
    metrics = classifier.get_metrics()
    return {
        "selected_model": metrics.get("selected_model"),
        "model_version": metrics.get("model_version"),
        "comparison": metrics.get("model_comparison", []),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ocr": True,
        "ml": {"model_loaded": classifier.is_loaded()},
    }
