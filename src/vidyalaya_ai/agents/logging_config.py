"""Logging setup for the agents layer."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_agents_logging(log_path: Path | str = "logs/agents.log") -> logging.Logger:
    """Configure agents file logging.

    Mirrors :func:`vidyalaya_ai.api.logging_config.setup_api_logging`. Without
    this the ``vidyalaya_ai.agents`` logger has no handler, so agent activity —
    tool calls (``search_textbook``, ``get_chat_history``), history healing, and
    turn timeouts — never reaches ``logs/agents.log``.
    """
    logger = logging.getLogger("vidyalaya_ai.agents")
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
