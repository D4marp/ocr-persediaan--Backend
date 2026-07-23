"""
Evaluasi FA-OCR terhadap baseline pada 40 nota yang sama.

Format ditentukan dari prediksi leave-one-out classifier (data/format_pred_loo.json),
bukan dari label ground truth, sehingga hasil end-to-end mencerminkan sistem nyata
yang harus menebak formatnya sendiri (termasuk menanggung galat klasifikasi).

Ablation: menyapu radius dilasi r dan mode morfologi.
"""
import glob
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from fa_ocr import (FMT_DOT_MATRIX, multi_psm_fusion, preprocess_baseline,
                    preprocess_dot_matrix)

RAW = os.path.join(os.path.dirname(__file__), "data", "raw_notas")


def run_config(radius, mode, pred_fmt):
    results = {}
    files = sorted(glob.glob(os.path.join(RAW, "*.jpg")))
    for path in files:
        lid = os.path.basename(path).split("_")[0]
        fmt = pred_fmt.get(lid)
        if fmt is None:
            continue
        if fmt == FMT_DOT_MATRIX:
            img = preprocess_dot_matrix(path, radius=radius, mode=mode)
        else:
            img = preprocess_baseline(path)
        fused = multi_psm_fusion(img)
        results[lid] = {
            "file": os.path.basename(path),
            "format_pred": fmt,
            "text": fused["text"],
            "confidence": fused["mean_conf"],
            "ocr_mode": "fusion",
        }
    return results


def main():
    pred_fmt = json.load(open(os.path.join(os.path.dirname(__file__), "data", "format_pred_loo.json")))
    configs = []
    for r in (1, 2, 3):
        configs.append((r, "dilate"))
    configs.append((2, "close"))

    all_out = {}
    for radius, mode in configs:
        key = f"r{radius}_{mode}"
        print(f"--- running {key} ---", flush=True)
        all_out[key] = run_config(radius, mode, pred_fmt)
        out_path = os.path.join(os.path.dirname(__file__), "data", f"fa_ocr_results_{key}.json")
        json.dump(all_out[key], open(out_path, "w"), ensure_ascii=False, indent=2)
        print("saved", out_path, flush=True)


if __name__ == "__main__":
    main()
