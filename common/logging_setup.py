"""Structured logging: stdout + rotating file, shared by all engines."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from common.paths import LOGS_DIR, ensure_dirs


def get_logger(name: str) -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "automation.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    logger.addHandler(stream)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
