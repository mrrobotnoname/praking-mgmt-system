# src/services/network.py
import httpx
import cv2
import logging
import os
from config.settings import BACKEND_URL

class CloudNetworkDispatcher:
    def __init__(self):
        # Industrial persistent client connection pool
        self.client = httpx.AsyncClient(timeout=10.0,trust_env=False)

        self.debug_dir = "debug"
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

    async def send_to_backend(self, plate_text: str, direction: str, cropped_img):
        """Transmits the extracted plate data to the cloud FastAPI backend."""
        
        
        if cropped_img is None or cropped_img.size == 0:
            logging.error("❌ Network Dispatcher received an empty or invalid image crop. Skipping save.")
            return

        # ================================================================
        # 💾 NETWORK AUDIT: Save exactly what is being sent to the cloud
        # ================================================================
        try:
            # Save using a static filename so it constantly overwrites itself 
            # and doesn't accidentally fill up your laptop's hard drive.
            audit_path = os.path.join(self.debug_dir, "last_sent_to_network.jpg")
            cv2.imwrite(audit_path, cropped_img)
            logging.info(f"📸 [NETWORK AUDIT] Outbound image cached locally at: {audit_path}")
        except Exception as write_err:
            logging.error(f"Failed to write network audit image: {write_err}")
        # ================================================================


        _, buffer = cv2.imencode('.jpg', cropped_img)
        img_bytes = buffer.tobytes()

        payload = {
            "plate": plate_text,
            "direction": direction
        }
        files = {
            "image": ("plate.jpg", img_bytes, "image/jpeg")
        }

        logging.info(f"📡 Transmitting Event payload to Cloud Server -> Box: {plate_text} | Dir: {direction}")
        
        try:
            # This request holds the Edge Node execution process until the cloud backend responds
            response = await self.client.post(BACKEND_URL, data=payload, files=files)
            
            if response.status_code == 200:
                logging.info("✅ Cloud Verification Complete. Remote gate authorized.")
            else:
                logging.error(f"⚠️ Server returned error response status: {response.status_code}")
        except Exception as e:
            logging.critical(f"❌ Network unreachable connection timeout error: {e}")