# src/services/detector.py
import openvino as ov
import numpy as np
import cv2
import logging

class PlateDetectorService:
    def __init__(self, model_path: str):
        self.core = ov.Core()
        logging.info(f"Compiling YOLO11n to CPU Kernels ({model_path})...")
        self.model = self.core.read_model(model_path)
        self.compiled_model = self.core.compile_model(self.model, "CPU")
        self.output_layer = self.compiled_model.output(0)
        self._warmup()

    def _warmup(self):
        logging.info("Warming up OpenVINO inference memory kernels...")
        dummy_input = np.zeros((1, 3, 640, 640), dtype=np.float32)
        self.compiled_model([dummy_input])
        logging.info("YOLO11 OpenVINO core hot and ready.")

    def detect_dominant_vehicle(self, frame: np.ndarray, state_ref):
        """Runs inference and handles multi-car extraction via Dominant Vehicle Rule."""
        h, w = frame.shape[:2]
        
        # 1. Preprocess frame to YOLO 640x640 format
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        
        # 2. OpenVINO Execution
        results = self.compiled_model([blob])[self.output_layer]
        
        # 3. Parse Predictions (Boxes shape structure: [1, 84, 8400] for YOLO11)
        predictions = np.squeeze(results).T
        
        valid_detections = []
        for pred in predictions:
            confidence = pred[4]
            if confidence > 0.48:
                # Convert normalized box center coordinates to absolute frame pixels
                x_c, y_c, box_w, box_h = pred[0]*w/640, pred[1]*h/640, pred[2]*w/640, pred[3]*h/640
                x1, y1 = int(x_c - box_w/2), int(y_c - box_h/2)
                x2, y2 = int(x_c + box_w/2), int(y_c + box_h/2)
                box = [x1, y1, x2, y2]
                
                # Check dynamic Region Of Interest Masking
                if state_ref.is_inside_roi(box, w, h):
                    valid_detections.append({'box': box, 'area': box_w * box_h})

        if not valid_detections:
            return False, None, None

        # DOMINANT VEHICLE RULE: Select the largest bounding box closest to the camera lens
        dominant = max(valid_detections, key=lambda d: d['area'])
        dbox = dominant['box']
        
        # Guard array padding boundaries before cropping
        crop = frame[max(0, dbox[1]):min(h, dbox[3]), max(0, dbox[0]):min(w, dbox[2])]
        return True, dbox, crop