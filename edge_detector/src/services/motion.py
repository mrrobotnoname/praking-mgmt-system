# src/services/motion.py
import cv2
import numpy as np

class MotionShieldService:
    def __init__(self, pixel_threshold=25, area_percentage=0.015):
        self.prev_gray = None
        self.pixel_threshold = pixel_threshold
        self.area_percentage = area_percentage

    def has_movement(self, frame: np.ndarray) -> bool:
        """Extremely lightweight frame difference check to wake up YOLO."""
        # Downscale image to 320px width to decrease CPU computation time
        scale = 320 / frame.shape[1]
        small_frame = cv2.resize(frame, (320, int(frame.shape[0] * scale)))
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return False

        frame_delta = cv2.absdiff(self.prev_gray, gray)
        thresh = cv2.threshold(frame_delta, self.pixel_threshold, 255, cv2.THRESH_BINARY)[1]
        self.prev_gray = gray

        # Check total white pixels (moving pixels)
        motion_pixels = np.sum(thresh == 255)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        
        return (motion_pixels / total_pixels) > self.area_percentage