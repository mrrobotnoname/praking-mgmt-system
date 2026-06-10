# config/settings.py

# === STREAM CONFIGURATION ===
# Dev Mode (Video File):
VIDEO_SOURCE = "/home/dilshan/Desktop/praking-mgmt-system/tests/test_videos/test2.mp4"
IS_LIVE_STREAM = False

# Production Mode (Uncomment when deploying to physical gate):
# VIDEO_SOURCE = "rtsp://admin:Password123@192.168.1.150:554/h264/ch1/main/av_stream"
# IS_LIVE_STREAM = True

# === CLOUD BACKEND CONFIGURATION ===
BACKEND_URL = "http://localhost:8000/api/v1/parking/verify"

# === REGION OF INTEREST (ROI) FILTERS ===
# Normalized percentages (0.0 to 1.0) relative to any camera resolution
ROI_X_MIN = 0.15
ROI_Y_MIN = 0.20
ROI_X_MAX = 0.85
ROI_Y_MAX = 0.90