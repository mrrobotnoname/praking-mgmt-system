# Edge Detector Service

This document describes the `edge_detector` service of the parking management system. It is the edge-node application that runs camera capture, license plate detection, OCR extraction, and then send the result to the guard.

## Overview

The edge detector pipeline has three main subsystems:

1. `camera_stream_loop` - captures frames from a camera or video file.
2. `PlateDetectorService` - detects the dominant vehicle plate region using an OpenVINO YOLO model.
3. `OcrService` - recognizes the plate text using RapidOCR OpenVINO.

The system is built around asynchronous loops and an application state shared between the stream and processing pipeline.

## Directory Structure

```
edge_detector/
  main.py
  requirements.txt
  config/settings.py
  model/best_openvino_model/best.xml
  src/
    state.py
    stream.py
    services/
      detector.py
      ocr.py
      pipeline.py
      network.py
      motion.py
    utils/logger.py
```

## Key Files

### `main.py`
- Starts logging and initializes the application state.
- Instantiates `PlateDetectorService` and `OcrService`.
- Runs `camera_stream_loop` and `processing_pipeline_loop` concurrently using `asyncio.gather()`.

### `config/settings.py`
- Contains runtime configuration for:
  - `VIDEO_SOURCE` and `IS_LIVE_STREAM`
  - `BACKEND_URL`
  - `ROI_X_MIN`, `ROI_Y_MIN`, `ROI_X_MAX`, `ROI_Y_MAX`
- Use the production section for a live RTSP camera or the dev section for local video playback.

### `src/stream.py`
- Reads frames from OpenCV `VideoCapture`.
- Supports video playback looping if `IS_LIVE_STREAM` is `False`.
- Writes the latest frame to `ApplicationState.current_frame`.
- Maintains `camera_online` state and logs camera dropout.

### `src/services/detector.py`
- Loads the OpenVINO YOLO model from `model/best_openvino_model/best.xml`.
- Preprocesses frames into `640x640` blob format.
- Filters detections by confidence and ROI.
- Returns the dominant vehicle crop and bounding box.

### `src/services/ocr.py`
- Wraps `RapidOCR` with a warmup step.
- Extracts OCR results and normalizes output to uppercase alphanumeric text.
- Aggregates all detected text fragments and falls back gracefully if needed.

### `src/services/pipeline.py`
- Coordinates motion checking, plate detection, OCR, and cloud dispatch.
- Uses `MotionShieldService` to skip empty frames.
- Requires the same vehicle to be observed across multiple frames before firing OCR.
- Preprocesses a plate crop with upscaling, CLAHE contrast enhancement, and sharpening.
- Sends recognized text plus image crop to cloud backend via `CloudNetworkDispatcher`.

### `src/services/network.py`
- Sends a `POST` request to `BACKEND_URL` with:
  - `plate`
  - `direction`
  - `image` crop
- Saves a local audit image to `debug/last_sent_to_network.jpg`.

### `src/state.py`
- Stores runtime status and simple vehicle tracking state.
- Implements ROI checking, same-vehicle detection, and direction calculation.
- Keeps a history of box areas to determine entry/exit direction.

### `src/utils/logger.py`
- Configures console and rotating file logging.
- Writes logs to `logs/edge_node.log`.

## Configuration Notes
- `VIDEO_SOURCE`: set to a local MP4 for development or a live RTSP stream for deployment.
- `IS_LIVE_STREAM`: `True` for camera feed, `False` for offline video replay.
- `BACKEND_URL`: cloud API endpoint for verifying plate events.
- `ROI_*`: defined as normalized percentages relative to frame dimensions.

## Running the Edge Detector

1. Activate the edge virtual environment:
   ```bash
   source edge_detector/.edge-venv/bin/activate
   ```
2. Run the edge node:
   ```bash
   python edge_detector/main.py
   ```

## Improvements and Extensions

Recommended future enhancements:

- Add support for plate deskewing / perspective correction.
- Add OCR confidence logging and fallback strategies.
- Move thresholds and tuning parameters into `config/settings.py`.
- Add unit tests for preprocessing and OCR output normalization.
- Add a more specific plate detector model if the current YOLO model is not plate-focused.

## Requirements

The current edge detector dependencies are defined in `edge_detector/requirements.txt`:

- `openvino==2024.1.0`
- `opencv-python-headless`
- `rapidocr-openvino`
- `httpx`
- `numpy`

## Notes
- The edge node is designed to run at the camera edge and send only validated plate events to the cloud.
- The current pipeline uses a simple blocked/unblocked state machine to avoid repeated OCR on the same vehicle.
- For production, ensure network connectivity and a stable RTSP stream.
