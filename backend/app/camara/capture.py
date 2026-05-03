
import cv2
import os
import time
from dotenv import load_dotenv
import queue
import os
import sys
import logging


load_dotenv()
log = logging.getLogger(__name__)
class SourceType:
    IP_CAM    = "ip_cam"
    RTSP      = "rtsp"      
    VIDEO     = "video"      
    WEBCAM    = "webcam" 
    
    
    
def get_camera_config()->dir:
    return {
        "source_type"    : os.getenv("CAMERA_SOURCE_TYPE", SourceType.VIDEO),
        "ip_cam_url"     : os.getenv("CAMERA_IP_URL", "http://192.168.1.5:8080/video"),
        "rtsp_url"       : os.getenv("CAMERA_RTSP_URL", "rtsp://admin:admin@192.168.1.5/stream"),
        "video_path"     : os.getenv("CAMERA_VIDEO_PATH", "tests/test_videos/test.mp4"),
        "webcam_index"   : int(os.getenv("CAMERA_WEBCAM_INDEX", 0)),
        "frame_interval" : float(os.getenv("CAMERA_FRAME_INTERVAL", 0.5)), 
        "retry_delay"    : float(os.getenv("CAMERA_RETRY_DELAY", 5.0)),  
        "max_retries"    : int(os.getenv("CAMERA_MAX_RETRIES", 10)),
    }

def report_status(status_queue, status, message):
    try:
        status_queue.put_nowait({
            "source" : "CamaraProcess",
            "status" : status,
            "message": message
        })
    except Exception:
        pass

def resolve_source(config: dir):
    source_type = config["source_type"]

    if source_type == SourceType.IP_CAM:
        return config["ip_cam_url"]

    elif source_type == SourceType.RTSP:
        return config["rtsp_url"]

    elif source_type == SourceType.VIDEO:
        path = config["video_path"]
        if not os.path.exists(path):
            log.error(f"Video file not found: {path}")
            sys.exit(1)
        return path

    elif source_type == SourceType.WEBCAM:
        return config["webcam_index"]

    else:
        log.error(f"Unknown source type: {source_type}")
        sys.exit(1)


def open_capture(source, config: dict) -> cv2.VideoCapture:
    retries = 0
    max_retries = config["max_retries"]

    while True:
        log.info(f"Connecting to camera source: {source}")
        cap = cv2.VideoCapture(source)

        if cap.isOpened():
            log.info("Camera connected successfully")

            # ── Optimize buffer for low latency ───
            # Keep only the latest frame in buffer
            # prevents reading stale frames on
            # low-end hardware
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            return cap

        retries += 1
        log.warning(
            f"Failed to connect to camera. "
            f"Retry {retries}/{max_retries} "
            f"in {config['retry_delay']}s..."
        )

        if max_retries != -1 and retries >= max_retries:
            log.error("Max retries reached. Camera process exiting.")
            sys.exit(1)

        time.sleep(config["retry_delay"])
        
def camera_process(frame_queue, status_queue):
    # ── Setup logging for this process ────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [CameraProcess] %(levelname)s: %(message)s"
    )

    log.info("Camera process started")

    config  = get_camera_config()
    source  = resolve_source(config)
    cap     = open_capture(source, config)

    frame_interval  = config["frame_interval"]
    is_video_file   = config["source_type"] == SourceType.VIDEO
    last_frame_time = 0

    log.info(
        f"Source type   : {config['source_type']}\n"
        f"Frame interval: {frame_interval}s "
        f"(~{int(1/frame_interval)} frames checked/sec)"
    )

    try:
        while True:
            ret, frame = cap.read()

            # ── Handle end of video file ───────
            # Loop back to start for testing
            if not ret:
                if is_video_file:
                    log.info("Video file ended — looping back to start")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    # Live camera dropped — try reconnect
                    log.warning("Frame read failed — attempting reconnect...")
                    cap.release()
                    time.sleep(config["retry_delay"])
                    cap = open_capture(source, config)
                    continue

            # ── Throttle to frame_interval ─────
            now = time.time()
            if now - last_frame_time < frame_interval:
                continue

            last_frame_time = now

            ###put the frame in the queue.
            
            try:
                frame_queue.put_nowait(frame)

            except queue.Full:
                try:
                    frame_queue.get_nowait()
                    frame_queue.put_nowait(frame)
                except Exception:
                    log.info("frame skiped")

    except KeyboardInterrupt:
        log.info("Camera process interrupted")

    finally:
        cap.release()
        log.info("Camera released. Camera process stopped.")
