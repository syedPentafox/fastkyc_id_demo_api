import logging
import os

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'background_jobs.log')

file_handler = logging.FileHandler(LOG_FILE_PATH)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
file_handler.setFormatter(formatter)

# This function can be imported and used to attach the file handler to any logger

def add_background_jobs_file_handler(logger):
    # Prevent adding multiple handlers
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == file_handler.baseFilename for h in logger.handlers):
        logger.addHandler(file_handler)
