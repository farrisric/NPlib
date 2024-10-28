# npl/logging_config.py
import logging


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("npl.log"),
            logging.StreamHandler()
        ]
    )
