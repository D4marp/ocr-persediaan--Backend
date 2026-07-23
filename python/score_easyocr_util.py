"""Bungkus fungsi penilaian dari score_fa_ocr agar dapat dipakai ulang."""
import importlib.util, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from score_fa_ocr import score as score_map  # noqa
