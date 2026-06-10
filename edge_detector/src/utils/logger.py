# src/utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_format = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s', '%Y-%m-%d %H:%M:%S')
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Terminal output stream
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # Disk file rotating engine storage setup
    file_handler = RotatingFileHandler(os.path.join("logs", "edge_node.log"), 
                    maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    logging.info("=== System Logging Engine Operational ===")