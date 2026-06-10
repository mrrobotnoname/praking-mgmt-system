# src/utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "CRITICAL": "\x1b[1;31m",
        "ERROR": "\x1b[31m",
        "WARNING": "\x1b[33m",
        "INFO": "\x1b[32m",
        "DEBUG": "\x1b[36m",
    }
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        color = self.COLORS.get(original_levelname, "")
        if color:
            record.levelname = f"{color}{original_levelname}{self.RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    file_format = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
        '%Y-%m-%d %H:%M:%S',
    )
    console_format = ColoredFormatter(
        '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
        '%Y-%m-%d %H:%M:%S',
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Terminal output stream
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # Disk file rotating engine storage setup
    file_handler = RotatingFileHandler(
        os.path.join("logs", "edge_node.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    logging.info("=== System Logging Engine Operational ===")