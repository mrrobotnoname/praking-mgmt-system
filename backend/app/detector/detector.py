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
    PAUSED = "PAUSED"


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
        "model_path": os.getenv(
            "MODEL_PATH"
        ),
        "device": os.getenv(
            "DETECTOR_DEVICE",
            "AUTO:GPU,CPU"
        ),
        "confidence_thresh": float(os.getenv(
            "DETECTOR_CONFIDENCE_THRESH",
            "0.75"
        )),
        "iou_thresh": float(os.getenv(
            "DETECTOR_IOU_THRESH",
            "0.45"
        )),
        "post_confirm_cooldown": int(os.getenv(
            "POST_CONFIRM_COOLDOWN",
            "30"
        )),
    }


# ─────────────────────────────────────────
# Report status to FastAPI
# via status_queue
# never raises — status reporting must
# never crash the detector
# ─────────────────────────────────────────
def report_status(status_queue, status, message):
    try:
        status_queue.put_nowait({
            "source": "DetectorProcess",
            "status": status,
            "message": message
        })
    except Exception:
        pass


# ─────────────────────────────────────────
# Load YOLO OpenVINO model
# exit(2) for unrecoverable errors
# exit(1) for recoverable errors
# ─────────────────────────────────────────
def load_model(config: dict, status_queue):
    try:
        # ── Check model path exists ────────
        if not os.path.exists(config["model_path"]):
            log.error(
                f"Model not found: {config['model_path']}"
            )
            report_status(
                status_queue,
                "OFFLINE",
                f"Model not found at "
                f"{config['model_path']}. "
                f"Manual entry required."
            )
            sys.exit(2)     # unrecoverable

        from ultralytics import YOLO

        log.info(f"Loading model: {config['model_path']}")
        log.info(f"Device      : {config['device']}")

        model = YOLO(config["model_path"])

        log.info("YOLO OpenVINO model loaded successfully")
        report_status(
            status_queue,
            "ONLINE",
            "Detector online and ready"
        )
        return model

    except ImportError:
        log.error(
            "ultralytics not installed — unrecoverable"
        )
        report_status(
            status_queue,
            "OFFLINE",
            "ultralytics package missing. "
            "Manual entry required."
        )
        sys.exit(2)         # unrecoverable

    except Exception as e:
        log.error(f"Failed to load model: {e}")
        report_status(
            status_queue,
            "OFFLINE",
            f"Model load failed: {e}"
        )
        sys.exit(1)         # recoverable — run.py will retry


# ─────────────────────────────────────────
# Plate detection using YOLO
# returns cropped plate + confidence
# returns None, 0.0 if no plate found
# ─────────────────────────────────────────
def detect_plate(model, frame: np.ndarray, config: dict):
    try:
        results = model(
            frame,
            device=config["device"],
            conf=config["confidence_thresh"],
            iou=config["iou_thresh"],
            verbose=False     # suppress YOLO console spam
        )

        if not results or len(results[0].boxes) == 0:
            return None, 0.0

        # ── Get highest confidence box ─────
        boxes = results[0].boxes
        confidences = boxes.conf.tolist()
        best_idx = confidences.index(max(confidences))
        best_conf = confidences[best_idx]
        best_box = boxes.xyxy[best_idx].tolist()

        x1, y1, x2, y2 = [int(c) for c in best_box]

        # ── Small padding around plate ─────
        pad = 5
        h, w = frame.shape[:2]
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        cropped_plate = frame[y1:y2, x1:x2]
        return cropped_plate, best_conf

    except Exception as e:
        log.error(f"YOLO inference error: {e}")
        return None, 0.0


# ─────────────────────────────────────────
# Encode cropped plate to base64 JPEG
# for sending over WebSocket to dashboard
# ─────────────────────────────────────────
def encode_frame(frame: np.ndarray) -> str:
    import base64
    try:
        _, buffer = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, 60]
        )
        return base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        log.error(f"Frame encode error: {e}")
        return ""


# ─────────────────────────────────────────
# Check control_queue for signals
# non blocking — returns None if empty
# ─────────────────────────────────────────
def check_control_queue(control_queue) -> str | None:
    try:
        return control_queue.get_nowait()
    except queue.Empty:
        return None
    except (OSError, EOFError, BrokenPipeError) as e:
        log.error(f"Control queue pipe error: {e}")
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
        level=logging.INFO,
        format="%(asctime)s [DetectorProcess] "
        "%(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler("backend/backend.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    log.info("Detector process started")

    # ── Load config ────────────────────────
    config = get_detector_config()

    # ── Load model ─────────────────────────
    # exits with code 1 or 2 on failure
    # run.py handles restart or stop
    model = load_model(config, status_queue)

    # ── State ──────────────────────────────
    state = DetectorState.DETECTING

    # ── Post confirm cooldown tracking ─────
    # after guard confirms a plate we ignore
    # the same plate for N seconds so the
    # vehicle has time to clear the gate
    last_confirmed_plate = None
    last_confirmed_time = 0.0
    cooldown = config["post_confirm_cooldown"]

    # ── Report initial state ───────────────
    report_status(
        status_queue,
        "DETECTING",
        "Detector active — waiting for vehicle"
    )

    log.info(
        f"Detector ready | "
        f"state: {state} | "
        f"cooldown: {cooldown}s"
    )

    try:
        while True:

            # ──────────────────────────────
            # Check control_queue first
            # on every loop iteration
            # regardless of state
            # ──────────────────────────────
            signal = check_control_queue(control_queue)

            if signal == ControlSignal.RESUME:
                log.info(
                    f"RESUME received — "
                    f"resuming detection | "
                    f"confirmed plate: {last_confirmed_plate}"
                )

                # ── Start cooldown for
                # confirmed plate ──────────
                last_confirmed_time = time.time()

                # ── Resume detecting ───────
                state = DetectorState.DETECTING

                # ── Drain stale frames ─────
                # frames that built up
                # while detector was paused
                drain_frame_queue(frame_queue)

                report_status(
                    status_queue,
                    "DETECTING",
                    "Guard confirmed — detector resumed"
                )

            # ──────────────────────────────
            # PAUSED
            # drain frames — wait for RESUME
            # ──────────────────────────────
            if state == DetectorState.PAUSED:
                drain_frame_queue(frame_queue)
                time.sleep(0.1)     # avoid busy loop
                continue

            # ──────────────────────────────
            # DETECTING
            # get frame and process it
            # ──────────────────────────────
            try:
                frame = frame_queue.get(timeout=1.0)

            except queue.Empty:
                continue    # no frame yet — keep waiting

            except (OSError, EOFError, BrokenPipeError) as e:
                # camera process may have died mid put()
                log.error(f"Frame queue pipe error: {e}")
                time.sleep(1.0)
                continue

            except Exception as e:
                log.error(f"Frame queue error: {e}")
                time.sleep(1.0)
                continue

            # ── Run YOLO plate detection ───
            cropped_plate, confidence = detect_plate(
                model, frame, config
            )

            # ── No plate found ─────────────
            if cropped_plate is None:
                continue

            oi = encode_frame(cropped_plate)

            log.info(
                f"Plate region detected — "
                f"confidence: {confidence:.2f}"
            )
            print("oi")

            # ── Run OCR ────────────────────
            from app.detector.ocr import extract_plate_text
            plate_text = extract_plate_text(cropped_plate)

            # ── Empty OCR result ───────────
            if not plate_text:
                log.warning(
                    "OCR returned empty text — "
                    "skipping frame"
                )
                continue

            log.info(
                f"OCR result : {plate_text} | "
                f"confidence : {confidence:.2f}"
            )

            # ──────────────────────────────
            # Post confirm cooldown check
            #
            # after guard confirms plate
            # ignore same plate for N seconds
            # gives vehicle time to
            # fully clear the gate
            # ──────────────────────────────
            if plate_text == last_confirmed_plate:
                elapsed = time.time() - last_confirmed_time
                if elapsed < cooldown:
                    log.debug(
                        f"Cooldown active — "
                        f"ignoring {plate_text} | "
                        f"elapsed: {elapsed:.1f}s / "
                        f"{cooldown}s"
                    )
                    continue    # skip — same vehicle
                    # still clearing gate
                else:
                    # cooldown expired
                    # same plate is a new vehicle
                    log.info(
                        f"Cooldown expired for "
                        f"{plate_text} — "
                        f"treating as new detection"
                    )
                    last_confirmed_plate = None

            # ── Determine confidence flag ──
            low_confidence = (
                confidence < config["confidence_thresh"]
            )

            # ── Encode plate image ─────────
            # base64 JPEG for WebSocket
            plate_image_b64 = encode_frame(cropped_plate)

            # ── Build result payload ───────
            result = {
                "plate": plate_text,
                "confidence": round(confidence, 4),
                "low_confidence": low_confidence,
                "plate_image": plate_image_b64,
                "timestamp": time.time(),
            }

            # ── Send to FastAPI ────────────
            try:
                result_queue.put(result, timeout=1.0)
                log.info(
                    f"Result sent — "
                    f"plate: {plate_text} | "
                    f"low_confidence: {low_confidence}"
                )

            except queue.Full:
                log.warning(
                    "Result queue full — "
                    "FastAPI may be busy — "
                    "dropping result"
                )
                continue

            except (OSError, EOFError, BrokenPipeError) as e:
                # FastAPI process may have died mid get()
                log.error(
                    f"Result queue pipe error: {e}"
                )
                time.sleep(1.0)
                continue

            except Exception as e:
                log.error(
                    f"Result queue put error: {e}"
                )
                time.sleep(1.0)
                continue

            # ──────────────────────────────
            # Store confirmed plate for
            # cooldown tracking
            # ──────────────────────────────
            last_confirmed_plate = plate_text

            # ──────────────────────────────
            # Switch to PAUSED
            # wait for guard to confirm
            # before detecting again
            # ──────────────────────────────
            state = DetectorState.PAUSED
            report_status(
                status_queue,
                "PAUSED",
                f"Plate detected: {plate_text} — "
                f"waiting for guard confirmation"
            )
            log.info(
                f"State → PAUSED | "
                f"plate: {plate_text} | "
                f"waiting for guard..."
            )

    except KeyboardInterrupt:
        log.info("Detector interrupted — shutting down")

    except Exception as e:
        # unexpected crash
        # exit(1) so run.py retries
        log.error(f"Detector unexpected error: {e}")
        report_status(
            status_queue,
            "OFFLINE",
            f"Detector crashed unexpectedly: {e}"
        )
        sys.exit(1)

    finally:
        log.info("Detector process stopped")
