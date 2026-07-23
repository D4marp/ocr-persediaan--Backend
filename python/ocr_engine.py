import pytesseract
import numpy as np
from PIL import Image

# PSM modes yang umum untuk dokumen UMKM
PSM_CANDIDATES = [
    (6, "block"),      # nota/faktur blok teks
    (4, "column"),     # struk thermal satu kolom
    (3, "auto"),       # layout otomatis
    (11, "sparse"),    # teks tersebar
]
OEM = 3
LANG = "ind+eng"


def _run_ocr(pil_image: Image.Image, psm: int) -> dict:
    config = f"--oem {OEM} --psm {psm} -l {LANG}"

    data = pytesseract.image_to_data(
        pil_image, config=config, output_type=pytesseract.Output.DICT
    )

    confidences = [int(c) for c in data["conf"] if int(c) > 0]
    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    words = []
    for i, word in enumerate(data["text"]):
        if word.strip() and int(data["conf"][i]) > 0:
            words.append({
                "word": word,
                "conf": int(data["conf"][i]),
                "left": data["left"][i],
                "top": data["top"][i],
            })

    full_text = pytesseract.image_to_string(pil_image, config=config).strip()

    # Skor gabungan: confidence + bonus panjang teks valid
    score = avg_confidence + min(len(full_text) / 50, 10) + len(words) * 0.5

    return {
        "text": full_text,
        "confidence": avg_confidence,
        "words": words,
        "word_count": len(words),
        "psm": psm,
        "score": score,
    }


def extract_text(image: np.ndarray) -> dict:
    """Coba beberapa mode Tesseract, pilih hasil terbaik."""
    pil_image = Image.fromarray(image)

    results = []
    for psm, _label in PSM_CANDIDATES:
        try:
            results.append(_run_ocr(pil_image, psm))
        except Exception:
            continue

    if not results:
        return {"text": "", "confidence": 0.0, "words": [], "word_count": 0, "ocr_mode": "failed"}

    best = max(results, key=lambda r: r["score"])
    return {
        "text": best["text"],
        "confidence": best["confidence"],
        "words": best["words"],
        "word_count": best["word_count"],
        "ocr_mode": f"psm-{best['psm']}",
    }
