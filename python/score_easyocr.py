"""Nilai hasil EasyOCR pada strata dot-matrix dengan metrik identik (score_fa_ocr)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from score_easyocr_util import score_map  # noqa

BASE = os.path.dirname(__file__)
ocr = json.load(open(os.path.join(BASE, "data", "easyocr_dotmatrix.json")))
per = score_map(ocr)
dm = [p for p in per if p["format_true"] == "dot_matrix"]
fa = [p["field_accuracy"] for p in dm if p["field_accuracy"] is not None]
ca = [p["char_accuracy"] for p in dm if p["char_accuracy"] is not None]
print(f"EasyOCR on dot-matrix (n={len(dm)}):")
print(f"  field detection = {100*sum(fa)/len(fa):.1f}%")
print(f"  char accuracy   = {100*sum(ca)/len(ca):.1f}%")
