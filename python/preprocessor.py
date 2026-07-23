import cv2
import numpy as np


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Pipeline preprocessing untuk meningkatkan akurasi Tesseract pada
    dokumen UMKM: nota tulisan tangan, struk thermal, foto remang.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Tidak dapat membaca gambar. Pastikan file valid.")

    # 1. Resize jika terlalu kecil (Tesseract optimal pada ~300 DPI)
    h, w = img.shape[:2]
    if max(h, w) < 1200:
        scale = 1200 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_CUBIC)

    # 2. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Deskew (koreksi kemiringan)
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) > 0.5:
            h2, w2 = gray.shape
            M = cv2.getRotationMatrix2D((w2 // 2, h2 // 2), angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w2, h2),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)

    # 4. Adaptive thresholding (tahan pencahayaan tidak merata)
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21, 10
    )

    # 5. Noise removal
    denoised = cv2.medianBlur(binary, 3)

    return denoised
