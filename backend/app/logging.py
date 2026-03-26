"""Structured JSON logging configuration."""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging(log_level: str = "info") -> None:
    """Configure all loggers to emit structured JSON to stdout."""
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(module)s %(funcName)s %(lineno)d",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
        },
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())

    # Align uvicorn loggers with the JSON formatter
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False
