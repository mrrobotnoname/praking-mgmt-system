import logging
import numpy as np
import cv2
import re

log = logging.getLogger(__name__)

# ~~~~~~~Initialize the RapidOCR
def init_ocr():
    try:
        from rapidocr_openvino import RapidOCR
        log.info("starting the RapidOCR")

        # For low-end PCs, you can optionally pass parameters here if needed
        ocr = RapidOCR()
        log.info("RapidOCR initialized")
        return ocr

    except Exception as e:
        log.warning(f"RapidOCR initialized failed {e}")
        return None


def warmup_ocr(ocr) -> bool:
    try:
        log.info("Warming up RapidOCR...")

        # ── Create dummy plate image ───────
        dummy = np.ones((64, 200, 3), dtype=np.uint8) * 255

        # ── Run dummy inference ────────────
        _ = ocr(dummy)

        log.info("RapidOCR warm up complete ✓")
        return True

    except Exception as e:
        log.warning(f"RapidOCR warm up failed: {e}")
        return False


# ─────────────────────────────────────────
# Preprocess plate image before OCR
# ─────────────────────────────────────────
def preprocess_plate(image: np.ndarray) -> np.ndarray:
    try:
        if image is None or image.size == 0:
            log.warning("Empty Image passed to preprocess")
            return image

        h, w = image.shape[:2]

        # ── Resize if too small ────────────
        if h < 64:
            scale = 64 / h
            new_w = int(w * scale)
            image = cv2.resize(image, (new_w, 64), interpolation=cv2.INTER_CUBIC)
            
        # ── Resize if too large ────────────
        if h > 400:
            scale = 400 / h
            new_w = int(w * scale)
            image = cv2.resize(image, (new_w, 400), interpolation=cv2.INTER_AREA)

        # ── Convert to grayscale ───────────
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # ── Denoise ────────────────────────
        denoised = cv2.fastNlMeansDenoising(
            gray, h=3, templateWindowSize=7, searchWindowSize=21
        )

        # ── Contrast enhancement (CLAHE) ───
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(denoised)

        # ── CRITICAL FIX: Removed Otsu Thresholding ───
        # Deep learning models handle raw gradients and textures much better 
        # than strict binary black-and-white cuts.

        # ── Convert back to BGR ────────────
        # RapidOCR expects a 3-channel image
        result = cv2.cvtColor(contrasted, cv2.COLOR_GRAY2BGR)
        return result

    except Exception as e:
        log.error(f"Preprocessing error: {e}")
        return image


# ─────────────────────────────────────────
# Clean raw OCR output
# ─────────────────────────────────────────
def clean_plate_text(raw: str) -> str:
    if not raw:
        return ""

    # ── Uppercase ──────────────────────────
    text = raw.upper().strip()

    # ── Remove unwanted characters ─────────
    text = re.sub(r"[^A-Z0-9\s\-]", "", text)

    # ── Collapse multiple spaces ───────────
    text = re.sub(r"\s+", " ", text).strip()

    # ── Replace spaces with hyphen ─────────
    text = text.replace(" ", "-")

    # ── Remove duplicate hyphens ───────────
    text = re.sub(r"-+", "-", text)

    # ── Strip leading trailing hyphens ─────
    text = text.strip("-")

    # ── Validate minimum length ────────────
    if len(text) < 4:
        log.debug(f"Plate text too short after cleaning: '{text}'")
        return ""

    return text


def extract_plate_text(ocr, cropped_plate: np.ndarray) -> str:
    try:
        if cropped_plate is None or cropped_plate.size == 0:
            log.warning("Empty cropped plate passed to OCR")
            return ""

        # ── Preprocess ─────────────────────
        processed = preprocess_plate(cropped_plate)

        # ── Run RapidOCR ───────────────────
        result, elapse = ocr(processed)
        print(result,elapse)

        # ── FIX: Safe calculation of elapse time if returned as a list ──
        total_elapse = sum(elapse) if isinstance(elapse, list) else elapse
        log.debug(f"RapidOCR inference time: {total_elapse:.3f}s")

        if not result:
            log.debug("RapidOCR returned no result")
            return ""

        # ── FIX: Robust parser handling different RapidOCR output layouts ──
        raw_text = ""
        if isinstance(result, list) and len(result) > 0:
            # Check if it has internal bbox coordinate tracking arrays
            if isinstance(result[0], list) and len(result[0]) == 3 and isinstance(result[0][0], list):
                # Standard format with layout detection active
                result_sorted = sorted(
                    result, key=lambda r: r[0][0][1] if (r[0] and len(r[0]) > 0) else 0
                )
                raw_text = " ".join([str(line[1]) for line in result_sorted if line[1]])
            else:
                # Flat format (e.g. if text detection is skipped)
                text_segments = []
                for item in result:
                    if isinstance(item, (list, tuple)) and len(item) > 0:
                        text_segments.append(str(item[0]))
                    elif isinstance(item, str):
                        text_segments.append(item)
                raw_text = " ".join(text_segments)

        log.debug(f"RapidOCR raw text: '{raw_text}'")

        # ── Clean and return ───────────────
        cleaned = clean_plate_text(raw_text)

        if cleaned:
            log.info(f"OCR: '{raw_text}' → '{cleaned}'")
        else:
            log.debug(f"OCR cleaning returned empty from raw: '{raw_text}'")

        return cleaned

    except Exception as e:
        log.error(f"OCR extraction error: {e}", exc_info=True)
        return ""