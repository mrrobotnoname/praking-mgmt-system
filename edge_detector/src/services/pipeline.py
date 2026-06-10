# src/services/pipeline.py
import asyncio
import logging
import cv2
import numpy as np
from src.state import ApplicationState
from src.services.motion import MotionShieldService
from src.services.detector import PlateDetectorService
from src.services.ocr import OcrService
from src.services.network import CloudNetworkDispatcher


async def processing_pipeline_loop(
    state: ApplicationState,
    detector: PlateDetectorService,
    ocr: OcrService
):
    motion_shield = MotionShieldService()
    network = CloudNetworkDispatcher()

    logging.info("Detection is started. Chekcking the frame.")

    def preprocess_plate_for_ocr(crop_img):
        """Enhances license plate crops for OCR by upscaling, contrast boosting, and sharpening."""
        if crop_img is None or crop_img.size == 0:
            return crop_img

        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        scale = max(1.0, min(4.0, 300.0 / max(height, width)))
        scaled = cv2.resize(
            gray,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_CUBIC,
        )

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(scaled)

        sharpen_kernel = np.array(
            [[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32
        )
        processed = cv2.filter2D(enhanced, -1, sharpen_kernel)
        return processed

    while True:
        # State Gatekeeper check
        if state.system_mode == "BLOCKED":
            await asyncio.sleep(0.5)
            continue

        frame = state.current_frame
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        # 1. Light Motion Shield Check
        if not motion_shield.has_movement(frame):
            # No changes on camera feed, sleep loop to preserve 13 CPU
            await asyncio.sleep(0.1)
            continue

        # 2. Physical motion confirmed, run OpenVINO plate identification layers
        plate_spotted, box, crop = detector.detect_dominant_vehicle(
            frame, state)

        if plate_spotted:
            if state.is_same_vehicle(box):
                # Update box center coordinate metrics, capture area frame size
                state.add_box_to_history(box)
                state.update_vehicle_location(box)

                # 3. If tracking history window reaches 3 frames, lock gate and fire OCR
                if len(state.box_area_history) >= 3:
                    direction = state.calculate_direction()
                    optimize_plate = preprocess_plate_for_ocr(crop)
                    text = ocr.extract_text(optimize_plate)

                    logging.warning(
                        f"🚨 GATE ALERT: [{text}] Verified driving: {direction}. Freezing system.")
                    state.system_mode = "BLOCKED"

                    # Network execution holds this loop until guard confirms or denies via UI
                    await network.send_to_backend(text, direction, crop)

                    # Reset edge system state variables back to normal processing parameters
                    state.system_mode = "MONITORING"
                    state.reset_tracking()
                else:
                    await asyncio.sleep(0.05)
            else:
                # First frame identifying this car
                state.add_box_to_history(box)
                state.update_vehicle_location(box)
                await asyncio.sleep(0.05)
        else:
            # Camera lane is completely clear, flush memory tracking cache
            if state.last_plate_location is not None:
                state.reset_tracking()
            await asyncio.sleep(0.3)
