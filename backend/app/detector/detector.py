import time
import logging
import queue
import sys
import os
import numpy as np
import cv2

log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Detector states
# ─────────────────────────────────────────
class DetectorState:
    DETECTING = "DETECTING"
    PAUSED    = "PAUSED"


# ─────────────────────────────────────────
# Control signals
# received from FastAPI via control_queue
# ─────────────────────────────────────────
class ControlSignal:
    RESUME = "RESUME"


# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
def get_detector_config():
    return {
        "model_path"           : os.getenv(
                                    "DETECTOR_MODEL_PATH",
                                    "ml/yolo11n_openvino_model"
                                  ),
        "device"               : os.getenv(
                                    "DETECTOR_DEVICE",
                                    "AUTO:GPU,CPU"
                                  ),
        "confidence_thresh"    : float(os.getenv(
                                    "DETECTOR_CONFIDENCE_THRESH",
                                    "0.75"
                                  )),
        "iou_thresh"           : float(os.getenv(
                                    "DETECTOR_IOU_THRESH",
                                    "0.45"
                                  )),
        "post_confirm_cooldown": int(os.getenv(
                                    "POST_CONFIRM_COOLDOWN",
                                    "10"
                                  )),
    }


# ─────────────────────────────────────────
# Report status to FastAPI via status_queue
# never raises — must never crash detector
# ─────────────────────────────────────────
def report_status(status_queue, status, message):
    try:
        status_queue.put_nowait({
            "source" : "DetectorProcess",
            "status" : status,
            "message": message
        })
    except Exception:
        pass


# ─────────────────────────────────────────
# Load YOLO OpenVINO model
#
# exit codes:
#   exit(2) → unrecoverable
#             model missing
#             package missing
#             run.py will NOT retry
#
#   exit(1) → recoverable
#             unexpected error
#             run.py will retry forever
# ─────────────────────────────────────────
def load_yolo_model(config: dict, status_queue):
    try:
        # ── Check model path exists ────────
        if not os.path.exists(config["model_path"]):
            log.error(
                f"YOLO model not found: "
                f"{config['model_path']}"
            )
            report_status(
                status_queue,
                "OFFLINE",
                f"YOLO model not found at "
                f"{config['model_path']}. "
                f"Manual entry required."
            )
            sys.exit(2)     # unrecoverable

        from ultralytics import YOLO

        log.info(
            f"Loading YOLO model: "
            f"{config['model_path']}"
        )
        log.info(f"Device: {config['device']}")

        model = YOLO(config["model_path"])

        log.info("YOLO model loaded ✓")
        return model

    except ImportError:
        log.error(
            "ultralytics not installed — "
            "unrecoverable"
        )
        report_status(
            status_queue,
            "OFFLINE",
            "ultralytics package missing. "
            "Manual entry required."
        )
        sys.exit(2)         # unrecoverable

    except Exception as e:
        log.error(f"YOLO load failed: {e}")
        report_status(
            status_queue,
            "OFFLINE",
            f"YOLO load failed: {e}"
        )
        sys.exit(1)         # recoverable


# ─────────────────────────────────────────
# Plate detection using YOLO
# returns cropped plate + confidence
# returns None, 0.0 if no plate found
# ─────────────────────────────────────────
def detect_plate(
    model,
    frame: np.ndarray,
    config: dict
):
    try:
        results = model(
            frame,
            device  = config["device"],
            conf    = config["confidence_thresh"],
            iou     = config["iou_thresh"],
            verbose = False
        )

        if not results or \
           len(results[0].boxes) == 0:
            return None, 0.0

        # ── Get highest confidence box ─────
        boxes       = results[0].boxes
        confidences = boxes.conf.tolist()
        best_idx    = confidences.index(
                          max(confidences)
                      )
        best_conf   = confidences[best_idx]
        best_box    = boxes.xyxy[best_idx].tolist()

        x1, y1, x2, y2 = [int(c) for c in best_box]

        # ── Small padding around plate ─────
        pad  = 5
        h, w = frame.shape[:2]
        x1   = max(0, x1 - pad)
        y1   = max(0, y1 - pad)
        x2   = min(w, x2 + pad)
        y2   = min(h, y2 + pad)

        cropped_plate = frame[y1:y2, x1:x2]
        return cropped_plate, best_conf

    except Exception as e:
        log.error(f"YOLO inference error: {e}")
        return None, 0.0


# ─────────────────────────────────────────
# Encode cropped plate to base64 JPEG
# always sent to dashboard
# guard sees image even if OCR fails
# ─────────────────────────────────────────
def encode_frame(frame: np.ndarray) -> str:
    import base64
    try:
        _, buffer = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, 60]
        )
        return base64.b64encode(
            buffer
        ).decode("utf-8")
    except Exception as e:
        log.error(f"Frame encode error: {e}")
        return ""


# ─────────────────────────────────────────
# Check control_queue for signals
# non blocking — returns None if empty
# ─────────────────────────────────────────
def check_control_queue(
    control_queue
) -> str | None:
    try:
        return control_queue.get_nowait()
    except queue.Empty:
        return None
    except (
        OSError,
        EOFError,
        BrokenPipeError
    ) as e:
        log.error(f"Control queue error: {e}")
        return None
    except Exception:
        return None


# ─────────────────────────────────────────
# Drain frame_queue without processing
# used when detector is PAUSED
# prevents memory buildup on 4GB RAM
# ─────────────────────────────────────────
def drain_frame_queue(frame_queue):
    try:
        while True:
            frame_queue.get_nowait()
    except Exception:
        pass


# ─────────────────────────────────────────
# Main detector process
# called by run.py
# ─────────────────────────────────────────
def detector_process(
    frame_queue,
    result_queue,
    control_queue,
    status_queue
):
    # ── Setup logging ──────────────────────
    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s [DetectorProcess] "
                 "%(levelname)s: %(message)s"
    )

    log.info("Detector process started")

    # ── Load config ────────────────────────
    config = get_detector_config()

    # ─────────────────────────────────────
    # STEP 1 — Load YOLO model
    #
    # exit(2) if model missing or
    # package not installed
    # exit(1) if unexpected error
    # detector is useless without YOLO
    # ─────────────────────────────────────
    log.info("Step 1: Loading YOLO model...")

    yolo_model = load_yolo_model(
        config,
        status_queue
    )

    log.info("Step 1: YOLO ready ✓")

    # ─────────────────────────────────────
    # STEP 2 — Load RapidOCR
    #
    # init_ocr() defined in ocr.py
    # handles all RapidOCR internals
    # returns None if fails — no exit
    # guard enters plate manually if
    # OCR unavailable
    # ─────────────────────────────────────
    log.info("Step 2: Loading RapidOCR...")

    from app.detector.ocr import (
        init_ocr,
        warmup_ocr,
        extract_plate_text
    )

    ocr_model = init_ocr()

    if ocr_model is not None:
        # ── Warm up before loop starts ─────
        warmup_ocr(ocr_model)
        ocr_available = True
        log.info("Step 2: RapidOCR ready ✓")
    else:
        ocr_available = False
        log.warning(
            "Step 2: RapidOCR unavailable — "
            "guard manual entry only"
        )
        report_status(
            status_queue,
            "WARNING",
            "OCR unavailable. "
            "Guard must enter plate manually."
        )

    # ─────────────────────────────────────
    # STEP 3 — Report ready
    # both models loaded
    # ready to start detection loop
    # ─────────────────────────────────────
    report_status(
        status_queue,
        "ONLINE",
        "Detector ready — "
        f"OCR: "
        f"{'available' if ocr_available else 'unavailable'}"
    )

    # ── Initial state ──────────────────────
    state = DetectorState.DETECTING


    report_status(
        status_queue,
        "DETECTING",
        "Detector active — waiting for vehicle"
    )

    log.info(
        f"Detection loop started | "
        f"OCR: {'on' if ocr_available else 'off'}  "
    )

    try:
        while True:

            # ──────────────────────────────
            # Check control_queue first
            # every loop iteration
            # regardless of state
            # ──────────────────────────────
            signal = check_control_queue(
                control_queue
            )

            if signal == ControlSignal.RESUME:
                log.info(
                    "RESUME received — "
                    "resuming detection"
                )
                # ── Start cooldown for
                # last confirmed plate ──────
                last_confirmed_time = time.time()

                state = DetectorState.DETECTING
                drain_frame_queue(frame_queue)

                report_status(
                    status_queue,
                    "DETECTING",
                    "Guard confirmed — "
                    "detector resumed"
                )

            # ──────────────────────────────
            # PAUSED
            # drain frames
            # wait for RESUME signal
            # ──────────────────────────────
            if state == DetectorState.PAUSED:
                drain_frame_queue(frame_queue)
                time.sleep(0.1)
                continue

            # ──────────────────────────────
            # DETECTING
            # get frame and process it
            # ──────────────────────────────
            try:
                frame = frame_queue.get(timeout=1.0)

            except queue.Empty:
                continue

            except (
                OSError,
                EOFError,
                BrokenPipeError
            ) as e:
                log.error(
                    f"Frame queue pipe error: {e}"
                )
                time.sleep(1.0)
                continue

            except Exception as e:
                log.error(
                    f"Frame queue error: {e}"
                )
                time.sleep(1.0)
                continue

            # ──────────────────────────────
            # Run YOLO plate detection
            # ──────────────────────────────
            cropped_plate, confidence = detect_plate(
                yolo_model,
                frame,
                config
            )

            # ── No plate found ─────────────
            # keep detecting
            if cropped_plate is None:
                continue

            log.info(
                f"Plate region detected — "
                f"confidence: {confidence:.2f}"
            )

            # ──────────────────────────────
            # Confidence flag
            # ──────────────────────────────
            low_confidence = (
                confidence < config["confidence_thresh"]
            )

            # ──────────────────────────────
            # Encode plate image
            # always encoded and sent
            # guard sees image even if
            # OCR fails
            # ──────────────────────────────
            plate_image_b64 = encode_frame(
                cropped_plate
            )

            # ──────────────────────────────
            # Run OCR via ocr.py
            #
            # extract_plate_text() handles:
            #   preprocess
            #   RapidOCR inference
            #   text cleaning
            #   error handling
            #
            # returns empty string if fails
            # ──────────────────────────────
            plate_text  = ""
            ocr_failed  = False

            if ocr_available:
                plate_text = extract_plate_text(
                    ocr_model,
                    cropped_plate
                )
                # empty string means OCR
                # could not read the plate
                ocr_failed = (plate_text == "")

                if ocr_failed:
                    log.warning(
                        "OCR could not extract text — "
                        "guard will enter manually"
                    )
            else:
                # OCR never loaded
                # guard always enters manually
                ocr_failed = True
                log.debug(
                    "OCR unavailable — "
                    "sending image only"
                )
            # ──────────────────────────────
            # Build result payload
            #
            # always sent to FastAPI
            # regardless of OCR success
            # guard handles manually
            # if ocr_failed = True
            # ──────────────────────────────
            result = {
                "plate"          : plate_text,
                "confidence"     : round(confidence, 4),
                "low_confidence" : low_confidence,
                "ocr_failed"     : ocr_failed,
                "ocr_unavailable": not ocr_available,
                "plate_image"    : plate_image_b64,
                "timestamp"      : time.time(),
            }

            # ──────────────────────────────
            # Send result to FastAPI
            # via result_queue
            # ──────────────────────────────
            try:
                result_queue.put(
                    result,
                    timeout=1.0
                )
                log.info(
                    f"Result sent — "
                    f"plate: '{plate_text}' | "
                    f"ocr_failed: {ocr_failed} | "
                    f"low_conf: {low_confidence}"
                )

            except queue.Full:
                log.warning(
                    "Result queue full — "
                    "FastAPI may be busy — "
                    "dropping result"
                )
                continue

            except (
                OSError,
                EOFError,
                BrokenPipeError
            ) as e:
                log.error(
                    f"Result queue pipe error: {e}"
                )
                time.sleep(1.0)
                continue

            except Exception as e:
                log.error(
                    f"Result queue error: {e}"
                )
                time.sleep(1.0)
                continue


            # ──────────────────────────────
            # Switch to PAUSED
            # wait for guard to confirm
            # before detecting again
            # ──────────────────────────────
            state = DetectorState.PAUSED
            report_status(
                status_queue,
                "PAUSED",
                "Plate detected — "
                "waiting for guard confirmation"
            )
            log.info(
                "State → PAUSED | "
                "waiting for guard..."
            )
            
            #########Resuming the signal.
            time.sleep(5.0)
            state = DetectorState.DETECTING
            control_queue.put_nowait(ControlSignal.RESUME)
            

    except KeyboardInterrupt:
        log.info("Detector interrupted")

    except Exception as e:
        log.error(
            f"Detector unexpected error: {e}"
        )
        report_status(
            status_queue,
            "OFFLINE",
            f"Detector crashed: {e}"
        )
        sys.exit(1)         # recoverable
                            # run.py will retry

    finally:
        log.info("Detector process stopped")