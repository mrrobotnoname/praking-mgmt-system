# src/services/ocr.py
from rapidocr_openvino import RapidOCR
import numpy as np
import logging

class OcrService:
    def __init__(self):
        logging.info("Initializing RapidOCR OpenVINO Engine wrapper...")
        # RapidOCR loads its internal text detection/recognition layers directly
        self.engine = RapidOCR()
        self._warmup()

    def _warmup(self):
        logging.info("Warming up OCR engine with blank matrix...")
        dummy_crop = np.zeros((60, 180, 3), dtype=np.uint8)
        self.engine(dummy_crop)
        logging.info("RapidOCR Engine hot.")

    def extract_text(self, cropped_img: np.ndarray) -> str:
        if cropped_img is None or cropped_img.size == 0:
            return "UNKNOWN"
        try:
            result, _ = self.engine(cropped_img)
            if result:
                extracted_parts = []
                for entry in result:
                    if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                        continue
                    text_candidate = entry[1] if isinstance(entry[1], str) else entry[0] if isinstance(entry[0], str) else ""
                    if text_candidate:
                        extracted_parts.append(text_candidate)

                if not extracted_parts and result:
                    fallback = ""
                    if len(result[0]) > 1 and isinstance(result[0][1], str):
                        fallback = result[0][1]
                    elif isinstance(result[0][0], str):
                        fallback = result[0][0]
                    if fallback:
                        extracted_parts.append(fallback)

                extracted_text = "".join(extracted_parts)
                cleaned = "".join(c for c in extracted_text if c.isalnum()).upper()
                return cleaned if cleaned else "UNKNOWN"
        except Exception as e:
            logging.error(f"OCR Exception error: {e}")
        return "UNKNOWN"