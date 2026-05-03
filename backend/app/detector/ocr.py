import cv2
import re
import logging
import numpy as np
import os

log = logging.getLogger(__name__)

OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr")

# ─────────────────────────────────────────
# EasyOCR reader
# initialized once — expensive to reload
# ─────────────────────────────────────────
_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        log.info("Initializing EasyOCR (CPU mode)...")
        _easyocr_reader = easyocr.Reader(
            ["en"],
            gpu=False,
        )
        log.info("EasyOCR ready")
    return _easyocr_reader


# ─────────────────────────────────────────
# Preprocess plate image before OCR
# ─────────────────────────────────────────
def preprocess_plate(image: np.ndarray) -> np.ndarray:

    # ── Resize if too small ────────────────
    h, w = image.shape[:2]
    if h < 100:
        scale = 100 / h
        image = cv2.resize(
            image,
            (int(w * scale), 100),
            interpolation=cv2.INTER_CUBIC
        )

    # ── Grayscale ──────────────────────────
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # ── Denoise ────────────────────────────
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # ── Contrast ───────────────────────────
    clahe      = cv2.createCLAHE(
                     clipLimit=2.0,
                     tileGridSize=(8, 8)
                 )
    contrasted = clahe.apply(denoised)

    # ── Threshold ──────────────────────────
    _, thresh = cv2.threshold(
        contrasted, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return thresh


# ─────────────────────────────────────────
# Clean raw OCR output
# normalizes to Sri Lankan plate format
# ─────────────────────────────────────────
def clean_plate_text(raw: str) -> str:
    if not raw:
        return ""

    text = raw.upper().strip()
    text = re.sub(r"[^A-Z0-9\s\-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "-")
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    return text


# ─────────────────────────────────────────
# EasyOCR
# ─────────────────────────────────────────
def extract_with_easyocr(image: np.ndarray) -> str:
    reader  = get_easyocr_reader()
    results = reader.readtext(image)

    if not results:
        log.warning("No text detected")
        return ""

    results_sorted = sorted(
        results,
        key=lambda r: r[0][0][1]
    )
    return " ".join([r[1] for r in results_sorted])


def extract_with_tesseract(image: np.ndarray) -> str:
    import pytesseract
    config = (
        "--psm 8 -c tessedit_char_whitelist="
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )
    return pytesseract.image_to_string(image, config=config)

# ─────────────────────────────────────────
# Main OCR entry point
# called by detect.py
# ─────────────────────────────────────────
def extract_plate_text(cropped_plate: np.ndarray) -> str:
    try:
        processed = preprocess_plate(cropped_plate)
        
        if OCR_ENGINE == "tesseract":
            raw = extract_with_tesseract(cropped_plate)
        else:
            raw = extract_with_easyocr(processed)


        cleaned = clean_plate_text(raw)

        if cleaned:
            log.debug(f"OCR: '{raw}' → '{cleaned}'")
        else:
            log.debug(f"OCR no result from: '{raw}'")

        return cleaned

    except Exception as e:
        log.error(f"OCR error: {e}")
        return ""