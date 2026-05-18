"""Logging setup for the API layer."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_api_logging(log_path: Path | str = "logs/api.log") -> logging.Logger:
    """Configure API file logging."""
    logger = logging.getLogger("vidyalaya_ai.api")
    if logger.handlers:
        return logger

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logging to %s", log_path)
    return logger
