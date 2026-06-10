# src/stream.py
import cv2
import asyncio
import logging
from src.state import ApplicationState
from config.settings import VIDEO_SOURCE, IS_LIVE_STREAM

async def camera_stream_loop(state: ApplicationState):
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Force direct flush
    
    frame_delay = 0.01
    if not IS_LIVE_STREAM:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            frame_delay = 1.0 / fps

    logging.info(f"Stream subsystem launched. Source target: {VIDEO_SOURCE}")

    try:
        while True:
            if not IS_LIVE_STREAM and state.system_mode == "BLOCKED":
                await asyncio.sleep(0.2)
                continue

            ret, frame = await asyncio.to_thread(cap.read)
            
            if not ret:
                if not IS_LIVE_STREAM:
                    logging.info("Playback file complete. Automatically looping back to frame 0.")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    await asyncio.sleep(0.1)
                    continue
                else:
                    if state.camera_online:
                        logging.error("CCTV feed dropped! Edge node active in cloud manual recovery fallback.")
                        state.camera_online = False
                    state.current_frame = None
                    await asyncio.sleep(2.0)
                    continue

            state.camera_online = True
            state.current_frame = frame
            await asyncio.sleep(frame_delay)
            
    except Exception as e:
        logging.critical(f"Fatal crash inside streaming subsystem thread: {e}", exc_info=True)
        state.camera_online = False
    finally:
        cap.release()