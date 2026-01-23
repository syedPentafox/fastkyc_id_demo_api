import logging
import sys
from logging.handlers import RotatingFileHandler

# LOG_FORMAT = (
#     "%(asctime)s | %(levelname)s | %(name)s | "
#     "%(filename)s:%(lineno)d | %(message)s"
# )

LOG_FORMAT = (
    # "%(asctime)s | %(levelname)s | %(name)s | "
    "%(lineno)d | %(message)s"
)

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)


    if not logger.handlers:
        # Console logs
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

        # File logs (auto-rotating)
        file_handler = RotatingFileHandler(
            "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
