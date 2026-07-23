"""
Jalankan EasyOCR (engine modern berbasis deep learning) pada strata dot-matrix,
untuk menjawab pertanyaan reviewer: apakah kegagalan dot-matrix khas Tesseract
atau bersifat lintas-engine?

EasyOCR dijalankan pada citra dot-matrix APA ADANYA (tanpa dot-merging), setara
dengan kondisi baseline, sehingga perbandingannya adil.
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(__file__))

RAW = os.path.join(os.path.dirname(__file__), "data", "raw_notas")
LABELS = json.load(open(os.path.join(os.path.dirname(__file__), "data", "format_labels.json")))


def main():
    import easyocr
    reader = easyocr.Reader(["en", "id"], gpu=False, verbose=False)

    dot_ids = {k for k, v in LABELS.items() if v["format"] == "dot_matrix"}
    files = sorted(glob.glob(os.path.join(RAW, "*.jpg")))
    out = os.path.join(os.path.dirname(__file__), "data", "easyocr_dotmatrix.json")
    results = json.load(open(out)) if os.path.exists(out) else {}
    for path in files:
        lid = os.path.basename(path).split("_")[0]
        if lid not in dot_ids or lid in results:
            continue
        try:
            img = Image.open(path).convert("L")
            w, h = img.size
            # cap the long side to bound EasyOCR memory
            target = 1400
            sc = target / max(w, h)
            img = img.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.BICUBIC)
            img = ImageOps.autocontrast(img)
            arr = np.array(img)
            lines = reader.readtext(arr, detail=0, paragraph=True)
            text = " ".join(lines)
            results[lid] = {"file": os.path.basename(path), "text": text, "format_pred": "dot_matrix"}
            print(f"{lid}: {text[:80]}", flush=True)
        except Exception as e:
            print(f"{lid}: FAILED {e}", flush=True)
        json.dump(results, open(out, "w"), ensure_ascii=False, indent=2)
    print("saved", out, len(results), "images")


if __name__ == "__main__":
    main()
