"""
Evaluasi akurasi OCR terhadap ground truth nota UMKM.

Preprocessing memakai PIL murni (bukan cv2) karena instalasi OpenCV di
lingkungan ini korup (linking error protobuf Homebrew) - di luar kendali
proyek ini. Pipeline: grayscale -> upscale jika < 1200px -> autocontrast.
"""
import glob
import json
import os
import sys

import numpy as np
import pytesseract
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(__file__))
from ocr_engine import PSM_CANDIDATES, OEM, LANG, _run_ocr  # noqa: E402

RAW_DIR = os.path.join(os.path.dirname(__file__), "data", "raw_notas")
OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "ocr_results.json")


def preprocess(path: str) -> np.ndarray:
    img = Image.open(path).convert("L")
    w, h = img.size
    if max(w, h) < 1200:
        scale = 1200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.BICUBIC)
    img = ImageOps.autocontrast(img)
    return np.array(img)


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*.jpg")))
    results = {}
    for i, path in enumerate(files):
        name = os.path.basename(path)
        link_id = name.split("_", 1)[0]
        print(f"[{i+1}/{len(files)}] OCR {name} ...", flush=True)
        try:
            arr = preprocess(path)
            pil_image = Image.fromarray(arr)
            runs = []
            for psm, _label in PSM_CANDIDATES:
                try:
                    runs.append(_run_ocr(pil_image, psm))
                except Exception as e:
                    print("   psm", psm, "failed:", e)
            if not runs:
                results[link_id] = {"file": name, "text": "", "confidence": 0, "ocr_mode": "failed"}
                continue
            best = max(runs, key=lambda r: r["score"])
            results[link_id] = {
                "file": name,
                "text": best["text"],
                "confidence": best["confidence"],
                "word_count": best["word_count"],
                "ocr_mode": f"psm-{best['psm']}",
            }
        except Exception as e:
            print("   FAILED:", e)
            results[link_id] = {"file": name, "text": "", "confidence": 0, "ocr_mode": "error", "error": str(e)}

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Saved", OUT_PATH, "-", len(results), "results")


if __name__ == "__main__":
    main()
