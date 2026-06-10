# main.py
import asyncio
import sys
import logging
from pathlib import Path
from src.utils.logger import setup_logger
from src.state import ApplicationState
from src.stream import camera_stream_loop
from src.services.detector import PlateDetectorService
from src.services.ocr import OcrService
from src.services.pipeline import processing_pipeline_loop

async def main():
    setup_logger()
    logging.info("Bootloader initialization process starting up...")

    state = ApplicationState()
    
    BASE_DIR = Path(__file__).resolve().parent
    MODEL_PATH = str(BASE_DIR / "model" / "best_openvino_model" / "best.xml")

    try:
        # Preload and compile models outside running execution layers
        detector = PlateDetectorService(MODEL_PATH)
        ocr = OcrService()
        
        logging.info("=== Boot sequence validation success. Spinning up engines. ===")
    except Exception as e:
        logging.critical(f"Engine compilation initialization error aborted: {e}", exc_info=True)
        return

    try:
        await asyncio.gather(
            camera_stream_loop(state),
            processing_pipeline_loop(state, detector, ocr)
        )
    except asyncio.CancelledError:
        logging.info("Async cancellation request accepted.")
    except Exception as e:
        logging.critical(f"Unhandled pipeline failure exception crash: {e}", exc_info=True)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Application shutdown triggered by operator input code control keys.")