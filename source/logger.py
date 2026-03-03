import logging
import sys
import os
from datetime import datetime

# Ensure the logs directory exists
log_dir = os.path.join("assets", "logs")
os.makedirs(log_dir, exist_ok=True)

# Generate a single timestamped filename for this run
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"log_{timestamp}.log")

def get_logger(name):
    """
    Creates and returns a configured logger.
    Normalizes output to include date, time, log level, and the originating file.
    """
    logger = logging.getLogger(name)
    
    # Only configure if it doesn't already have handlers to avoid duplicate logs
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [filename:line] Message
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Also log to a file
        file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
