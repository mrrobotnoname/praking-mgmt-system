import sys
import logging
import time
import multiprocessing
import uvicorn
from app.main import create_app

from app.detector.detector import detector_process
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(processName)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("backend/backend.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

CAMERA_MAX_RESTARTS = int(os.getenv("CAMERA_MAX_RESTARTS", 5))
DETECTOR_MAX_RESTARTS = int(os.getenv("DETECTOR_MAX_RESTARTS", 5))
RESTART_DELAY = os.getenv("RESTART_DELAY", 5.0)


def api_process(result_queue, control_queue, status_queue, command_queue):

    app = create_app(
        result_queue=result_queue,
        control_queue=control_queue,
        status_queue=status_queue,
        command_queue=command_queue
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"

    )


def camera_process_fn(frame_queue, status_queue):
    from app.camara.capture import camera_process
    camera_process(frame_queue, status_queue)


def detector_process_fn(frame_queue,status_queue, control_queue, result_queue):
    from app.detector.detector import detector_process
    detector_process(frame_queue,status_queue, control_queue, result_queue)


def spawn(target, args: tuple, name: str):
    p = multiprocessing.Process(
        target=target,
        args=args,
        name=name,
        daemon=True
    )
    p.start()
    log.info(f"{name} started (PID: {p.pid})")
    return p


def stop_process(p, name: str):
    if p and p.is_alive():
        log.info(f"Stopping {name}...")
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join()        # ← final cleanup after kill
        log.info(f"{name} stopped")
    elif p and not p.is_alive():
        # process is dead but not joined yet
        # clean up the zombie
        p.join()            # ← release dead process resources
        log.info(f"{name} zombie cleaned up")


if __name__ == "__main__":
    log.info("Starting Parking Management System... ")

    # _____________Create the Queues________________
    #
    # frame_queue : Camara --> Detector
    #    max_len 1: Keep the last frame
    #               discard other
    #
    # result_queue : Detector --> FastAPI
    #   maxsize=5  : small buffer in case
    #                FastAPI is briefly busy
    #
    # control_queue: FastAPI --> Detector
    #   no limit   : only carries small
    #                RESUME signals

    # status_queue: Keep the status about
    #               camara process and
    #               detector process

    # ___________________________________________
    #

    frame_queue = multiprocessing.Queue(maxsize=1)
    result_queue = multiprocessing.Queue(maxsize=5)
    control_queue = multiprocessing.Queue()
    status_queue = multiprocessing.Queue()
    command_queue = multiprocessing.Queue()

    api_p = spawn(
        target=api_process,
        args=(result_queue, control_queue, status_queue, command_queue),
        name="APIProcess"
    )

    camera_p = spawn(
        target=camera_process_fn,
        args=(frame_queue, status_queue),
        name="CamaraProcess"
    )
    detector_p = spawn(
        target=detector_process_fn,
        args=(frame_queue,status_queue, control_queue, result_queue),
        name="DetectorProcess"
    )

    log.info("All processes running.")
    log.info("Frontend: run 'npm run dev' in /frontend")
    log.info("API:      http://localhost:8000")
    log.info("API Docs: http://localhost:8000/docs")

    camera_restarts = 0
    detector_restarts = 0

    try:
        while True:
            time.sleep(5)

            # ── Check admin commands ───────
            # admin can retry camera/detector
            # from dashboard
            try:
                while True:
                    cmd = command_queue.get_nowait()

                    if cmd == "RETRY_CAMERA":
                        if not camera_p or not camera_p.is_alive():
                            log.info("Admin retrying camera...")
                            stop_process(camera_p, "CameraProcess")
                            camera_p = spawn(
                                camera_process_fn,
                                (frame_queue, status_queue,),
                                "CameraProcess"
                            )
                        else:
                            log.info(
                                "Camera already running"
                            )

                    elif cmd == "RETRY_DETECTOR":
                        if not detector_p or not detector_p.is_alive():
                            log.info("Admin retrying detector...")

                            stop_process(detector_p, "DetectroProcess")
                            detector_p = spawn(
                                detector_process_fn,
                                (frame_queue, result_queue,
                                 control_queue, status_queue,),
                                "DetectorProcess"
                            )
                        else:
                            log.info("Detector already running")

            except:
                pass  # command_queue empty

            # ── API died → shutdown all ────
            if not api_p.is_alive():
                log.error(
                    f"API died "
                    f"(exit: {api_p.exitcode}) "
                    f"— shutting down"
                )
                break

            # ── Camera died ────────────────
            if camera_p and not camera_p.is_alive():
                exit_code = camera_p.exitcode

                if exit_code == 2:
                    # unrecoverable — stop it
                    log.error("Camera unrecoverable — stopped")
                    status_queue.put({
                        "source": "CameraProcess",
                        "status": "OFFLINE",
                        "message": "Camera offline. "
                                   "Fix issue then retry "
                                   "from dashboard."
                    })
                    camera_p = None

                else:
                    # recoverable — retry forever
                    log.warning("Camera crashed — retrying...")
                    status_queue.put({
                        "source": "CameraProcess",
                        "status": "RESTARTING",
                        "message": "Camera restarting..."
                    })
                    stop_process(camera_p,"CameraProcess")
                    camera_p = spawn(
                        camera_process_fn,
                        (frame_queue, status_queue,),
                        "CameraProcess"
                    )

            # ── Detector died ──────────────
            if detector_p and not detector_p.is_alive():
                exit_code = detector_p.exitcode

                if exit_code == 2:
                    # unrecoverable — stop it
                    log.error("Detector unrecoverable — stopped")
                    status_queue.put({
                        "source": "DetectorProcess",
                        "status": "OFFLINE",
                        "message": "Detector offline. "
                                   "Fix issue then retry "
                                   "from dashboard."
                    })
                    detector_p = None

                else:
                    # recoverable — retry forever
                    log.warning("Detector crashed — retrying...")
                    status_queue.put({
                        "source": "DetectorProcess",
                        "status": "RESTARTING",
                        "message": "Detector restarting..."
                    })
                    stop_process(detector_p,"DetectorProcess")
                    detector_p = spawn(
                        detector_process_fn,
                        (frame_queue, status_queue,
                         control_queue, result_queue,),
                        "DetectorProcess"
                    )

    except KeyboardInterrupt:
        log.info("Shutdown signal received (Ctrl+C)")

    finally:
        log.info("Shutting down...")
        stop_process(camera_p,   "CameraProcess")
        stop_process(detector_p, "DetectorProcess")
        stop_process(api_p,      "APIProcess")
        log.info("System shut down")
        sys.exit(0)
