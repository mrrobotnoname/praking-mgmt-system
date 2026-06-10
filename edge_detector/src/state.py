# src/state.py
import numpy as np
import time
import logging
from config.settings import ROI_X_MIN, ROI_Y_MIN, ROI_X_MAX, ROI_Y_MAX

class ApplicationState:
    def __init__(self):
        self.current_frame: np.ndarray = None
        self.system_mode: str = "MONITORING"  # MONITORING or BLOCKED
        self.camera_online: bool = True       # Monitored by Stream Loop
        
        # Vehicle tracking states
        self.last_plate_location = None       # Coordinates (x_center, y_center)
        self.box_area_history = []            # To track coming vs leaving trends
        self.detected_direction = "UNKNOWN"

    def is_inside_roi(self, yolo_box, frame_width, frame_height) -> bool:
        """Checks if the center of a detected license plate falls within the scaled ROI."""
        x1, y1, x2, y2 = yolo_box
        c_x = (x1 + x2) / 2
        c_y = (y1 + y2) / 2
        
        if (ROI_X_MIN * frame_width <= c_x <= ROI_X_MAX * frame_width) and \
           (ROI_Y_MIN * frame_height <= c_y <= ROI_Y_MAX * frame_height):
            return True
        return False

    def is_same_vehicle(self, current_box, threshold_pixels=200) -> bool:
        """Shields system against repeating OCR on a stationary vehicle."""
        if self.last_plate_location is None:
            return False
            
        c_x = (current_box[0] + current_box[2]) / 2
        c_y = (current_box[1] + current_box[3]) / 2
        last_x, last_y = self.last_plate_location
        
        distance = ((c_x - last_x) ** 2 + (c_y - last_y) ** 2) ** 0.5
        return distance < threshold_pixels

    def add_box_to_history(self, box):
        """Accumulates box surface area over a few frames to run trends."""
        area = (box[2] - box[0]) * (box[3] - box[1])
        self.box_area_history.append(area)
        if len(self.box_area_history) > 5:
            self.box_area_history.pop(0)

    def calculate_direction(self) -> str:
        """Analyzes size history to compute direction."""
        if len(self.box_area_history) < 2:
            return "ENTRY"
            
        deltas = np.diff(self.box_area_history)
        positive_growth = np.sum(deltas > 0)
        negative_growth = np.sum(deltas < 0)
        
        self.detected_direction = "ENTRY" if positive_growth > negative_growth else "EXIT"
        return self.detected_direction

    def update_vehicle_location(self, box):
        if box is None:
            self.last_plate_location = None
        else:
            self.last_plate_location = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

    def reset_tracking(self):
        logging.info("Clearing edge vehicle tracking tracking memory.")
        self.last_plate_location = None
        self.box_area_history.clear()
        self.detected_direction = "UNKNOWN"