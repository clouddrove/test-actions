import logging
from sys import stderr


def make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        log_handler = logging.StreamHandler(stderr)
        log_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(filename)s:%(funcName)s %(message)s"))
        logger.addHandler(log_handler)

    return logger
