"""
FA-OCR: Format-Aware adaptive OCR pipeline.

Implementasi empat komponen yang diusulkan:
  Stage I   : classify_format()      - klasifikasi jenis cetak nota
  Stage II  : preprocess_for()       - preprocessing adaptif per format
  Stage III : multi_psm_fusion()     - fusi hipotesis multi-PSM berbobot confidence
  Stage IV  : route_decision()       - ambang confidence adaptif per format

Catatan implementasi: memakai PIL + numpy murni (tanpa OpenCV) karena instalasi
OpenCV pada environment ini korup (linking error protobuf Homebrew). Operasi
morfologi memakai PIL.ImageFilter.MaxFilter/MinFilter yang setara dilasi/erosi
grayscale dengan structuring element persegi.
"""
import os

import numpy as np
import pytesseract
from PIL import Image, ImageFilter, ImageOps

LANG = "ind+eng"
OEM = 3
PSM_CANDIDATES = (3, 4, 6, 11)

FMT_DOT_MATRIX = "dot_matrix"
FMT_THERMAL = "thermal_clean"
FMT_HANDWRITTEN = "handwritten"


# ----------------------------------------------------------------------
# Stage I - document format classifier
# ----------------------------------------------------------------------

def _text_mask(gray: np.ndarray) -> np.ndarray:
    """Binarisasi Otsu; True = piksel tinta."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0.0
    best_var, best_t = -1.0, 128
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return gray <= best_t


def _crop_to_ink(gray: np.ndarray, mask: np.ndarray):
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return gray, mask
    r0, r1 = rows[0], rows[-1] + 1
    c0, c1 = cols[0], cols[-1] + 1
    return gray[r0:r1, c0:c1], mask[r0:r1, c0:c1]


def stroke_run_stats(mask: np.ndarray) -> dict:
    """
    Statistik panjang run horizontal piksel tinta.

    Font dot-matrix tersusun dari titik diskret -> banyak run sangat pendek
    (1-3 px) dan rasio run pendek tinggi. Cetak solid -> run lebih panjang dan
    konsisten. Tulisan tangan -> run bervariasi lebar (CV tinggi).
    """
    runs = []
    for row in mask:
        if not row.any():
            continue
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        starts, ends = idx[0::2], idx[1::2]
        runs.append(ends - starts)
    if not runs:
        return {"mean_run": 0.0, "cv_run": 0.0, "short_run_ratio": 0.0}
    r = np.concatenate(runs).astype(float)
    mean_run = float(r.mean())
    cv_run = float(r.std() / mean_run) if mean_run > 0 else 0.0
    short_run_ratio = float((r <= 3).sum() / r.size)
    return {"mean_run": mean_run, "cv_run": cv_run, "short_run_ratio": short_run_ratio}


def dot_periodicity(mask: np.ndarray) -> float:
    """
    Skor periodisitas pola titik lewat autokorelasi spektrum baris.

    Karakter dot-matrix punya jarak antar-titik hampir konstan, sehingga profil
    proyeksi horizontal mengandung komponen periodik kuat pada frekuensi tinggi.
    Skor = energi puncak non-DC ternormalisasi terhadap energi rata-rata.
    """
    ink_rows = np.flatnonzero(mask.any(axis=1))
    if ink_rows.size < 8:
        return 0.0
    band = mask[ink_rows[0]:ink_rows[-1] + 1]
    profile = band.sum(axis=0).astype(float)
    profile -= profile.mean()
    if profile.size < 32 or np.allclose(profile, 0):
        return 0.0
    spec = np.abs(np.fft.rfft(profile)) ** 2
    if spec.size < 8:
        return 0.0
    spec = spec[1:]
    n = spec.size
    lo = max(1, int(0.05 * n))
    band_spec = spec[lo:]
    if band_spec.size == 0 or band_spec.mean() <= 0:
        return 0.0
    return float(band_spec.max() / band_spec.mean())


def extract_features(path: str) -> dict:
    img = Image.open(path).convert("L")
    gray = np.asarray(img, dtype=np.uint8)
    mask = _text_mask(gray)
    gray, mask = _crop_to_ink(gray, mask)
    feats = stroke_run_stats(mask)
    feats["periodicity"] = dot_periodicity(mask)
    feats["ink_ratio"] = float(mask.mean())
    feats.update(morph_response(path))
    return feats


def morph_response(path: str) -> dict:
    """
    Fitur respons morfologi: perubahan tutupan tinta dan panjang run setelah
    citra diprobe dengan dilasi 3x3.

    Melebarkan bidang titik yang TERPISAH akan menutup celah antar-titik dan
    menambah tinta secara tidak proporsional; melebarkan goresan SOLID hanya
    menebalkan tepinya. Rasio ini memisahkan dot-matrix dari cetak solid jauh
    lebih baik (Cohen d = 1.78) daripada fitur statis terbaik (d = 0.87).
    """
    img = ImageOps.autocontrast(Image.open(path).convert("L"))
    g0 = np.asarray(img, np.uint8)
    m0 = _text_mask(g0)
    _, m0c = _crop_to_ink(g0, m0)
    r0 = stroke_run_stats(m0c)["mean_run"]
    ink0 = m0c.mean()

    d = np.asarray(img.filter(ImageFilter.MinFilter(3)), np.uint8)
    m1 = _text_mask(d)
    _, m1c = _crop_to_ink(d, m1)
    r1 = stroke_run_stats(m1c)["mean_run"]
    ink1 = m1c.mean()

    return {
        "run_gain": float(r1 / r0) if r0 > 0 else 0.0,
        "ink_gain": float(ink1 / ink0) if ink0 > 0 else 0.0,
    }


_MODEL_CACHE = None


def _load_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        import pickle
        path = os.path.join(os.path.dirname(__file__), "models", "format_classifier.pkl")
        with open(path, "rb") as f:
            _MODEL_CACHE = pickle.load(f)
    return _MODEL_CACHE


def classify_format(path: str) -> tuple:
    """
    Stage I: klasifikasi jenis cetak nota.

    Regresi logistik multinomial atas vektor fitur 6 dimensi
    phi = [cv_run, ink_gain, run_gain, short_run_ratio, periodicity, mean_run].
    Model dilatih oleh calibrate_classifier.py, yang juga melaporkan akurasi
    leave-one-out (87.8% pada n=41). Mengembalikan (label, fitur).
    """
    f = extract_features(path)
    bundle = _load_model()
    x = np.array([[f[k] for k in bundle["features"]]])
    label = str(bundle["model"].predict(x)[0])
    return label, f


# ----------------------------------------------------------------------
# Stage II - adaptive preprocessing
# ----------------------------------------------------------------------

def _upscale(img: Image.Image, min_side: int = 1200) -> Image.Image:
    w, h = img.size
    if max(w, h) < min_side:
        s = min_side / max(w, h)
        img = img.resize((int(w * s), int(h * s)), Image.BICUBIC)
    return img


def preprocess_baseline(path: str) -> Image.Image:
    """Pipeline baseline: grayscale -> upscale -> autocontrast."""
    img = Image.open(path).convert("L")
    img = _upscale(img)
    return ImageOps.autocontrast(img)


def preprocess_dot_matrix(path: str, radius: int = 2, mode: str = "dilate") -> Image.Image:
    """
    Morphological dot merging.

    MinFilter melebarkan area gelap, yaitu dilasi pada tinta, sehingga titik-titik
    diskret yang berdekatan menyatu menjadi goresan kontinu dan Tesseract dapat
    mencocokkan bentuk karakter.

    mode='dilate' : dilasi saja (default).
    mode='close'  : dilasi lalu erosi. Uji pendahuluan menunjukkan erosi justru
                    memisahkan kembali titik yang baru menyatu, sehingga closing
                    lebih buruk daripada dilasi saja pada font dot-matrix.
    """
    img = Image.open(path).convert("L")
    img = _upscale(img)
    img = ImageOps.autocontrast(img)
    size = 2 * radius + 1
    img = img.filter(ImageFilter.MinFilter(size))
    if mode == "close":
        img = img.filter(ImageFilter.MaxFilter(size))
    return img


def preprocess_for(path: str, fmt: str, radius: int = 2, mode: str = "dilate") -> Image.Image:
    if fmt == FMT_DOT_MATRIX:
        return preprocess_dot_matrix(path, radius=radius, mode=mode)
    return preprocess_baseline(path)


# ----------------------------------------------------------------------
# Stage III - confidence-weighted multi-PSM fusion
# ----------------------------------------------------------------------

def _psm_tokens(img: Image.Image, psm: int) -> dict:
    cfg = f"--oem {OEM} --psm {psm} -l {LANG}"
    data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
    tokens = []
    for i, w in enumerate(data["text"]):
        c = int(data["conf"][i])
        if w.strip() and c > 0:
            tokens.append({"text": w.strip(), "conf": c})
    confs = [t["conf"] for t in tokens]
    return {
        "psm": psm,
        "tokens": tokens,
        "text": " ".join(t["text"] for t in tokens),
        "mean_conf": float(np.mean(confs)) if confs else 0.0,
    }


def multi_psm_fusion(img: Image.Image) -> dict:
    """
    Fusi hipotesis lintas mode PSM pada level token.

    Baseline memilih SATU mode PSM pemenang dan membuang sisanya. Di sini setiap
    mode menyumbang token, dan token yang sama (setelah normalisasi) mengakumulasi
    bobot w = sum(conf) sehingga token yang disepakati banyak mode dengan
    confidence tinggi bertahan. Ambang bobot menekan token hasil derau.
    """
    runs = [_psm_tokens(img, p) for p in PSM_CANDIDATES]
    runs = [r for r in runs if r["tokens"]]
    if not runs:
        return {"text": "", "mean_conf": 0.0, "fusion_tokens": 0, "psm_used": []}

    weights = {}
    for r in runs:
        for t in r["tokens"]:
            key = t["text"].upper()
            e = weights.setdefault(key, {"w": 0.0, "n": 0, "text": t["text"]})
            e["w"] += t["conf"] / 100.0
            e["n"] += 1

    # token dipertahankan bila didukung >1 mode ATAU bobot tunggalnya tinggi
    kept = [e for e in weights.values() if e["n"] >= 2 or e["w"] >= 0.80]
    if not kept:
        kept = list(weights.values())

    best = max(runs, key=lambda r: r["mean_conf"])
    order = {t["text"].upper(): i for i, t in enumerate(best["tokens"])}
    kept.sort(key=lambda e: order.get(e["text"].upper(), 10_000))

    fused_text = " ".join(e["text"] for e in kept)
    mean_conf = float(np.mean([r["mean_conf"] for r in runs]))
    return {
        "text": fused_text,
        "mean_conf": mean_conf,
        "fusion_tokens": len(kept),
        "psm_used": [r["psm"] for r in runs],
        "per_psm_conf": {r["psm"]: round(r["mean_conf"], 2) for r in runs},
    }


# ----------------------------------------------------------------------
# Stage IV - per-format adaptive thresholding
# ----------------------------------------------------------------------

def route_decision(fmt: str, conf: float, thresholds: dict) -> str:
    """Kembalikan 'auto_accept' atau 'verify' berdasarkan ambang per format."""
    if fmt == FMT_HANDWRITTEN:
        return "verify"
    return "auto_accept" if conf >= thresholds.get(fmt, 100.0) else "verify"


# ----------------------------------------------------------------------
# End-to-end
# ----------------------------------------------------------------------

def run(path: str, thresholds: dict = None) -> dict:
    thresholds = thresholds or {}
    fmt, feats = classify_format(path)
    img = preprocess_for(path, fmt)
    fused = multi_psm_fusion(img)
    decision = route_decision(fmt, fused["mean_conf"], thresholds)
    return {
        "format": fmt,
        "features": feats,
        "text": fused["text"],
        "confidence": fused["mean_conf"],
        "per_psm_conf": fused.get("per_psm_conf", {}),
        "decision": decision,
    }
