"""
Dedicated logging for Builder AI - writes to file directly.

Bypasses Frappe logging to ensure logs are captured even if worker crashes.
This is critical for debugging background job failures where standard
Frappe error logging may not work (e.g., worker killed by OOM or timeout).

Usage:
    from unpress_core.ai.logging import ai_log

    ai_log("info", "Starting page generation", page="Accueil", theme="modern")
    ai_log("error", "LLM request failed", error=str(e), timeout=600)
"""

import logging
import os
import threading
from typing import Any


def get_log_path() -> str:
    """
    Get path to builder_ai.log in Frappe logs directory.

    Falls back to /tmp if Frappe is not available.
    """
    try:
        import frappe
        logs_dir = os.path.join(frappe.get_site_path(), "logs")
    except Exception:
        logs_dir = "/tmp"

    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "builder_ai.log")


# Thread-local logger instances
_logger_lock = threading.Lock()
_logger = None


def get_ai_logger() -> logging.Logger:
    """
    Get or create dedicated AI logger.

    The logger is configured to:
    - Write to a dedicated file (builder_ai.log)
    - Flush immediately after each write
    - Not propagate to root logger (avoid duplication)
    """
    global _logger

    with _logger_lock:
        if _logger is None:
            _logger = logging.getLogger("builder_ai")
            _logger.setLevel(logging.DEBUG)

            # Avoid duplicate handlers if called multiple times
            if not _logger.handlers:
                # File handler with immediate flush
                handler = logging.FileHandler(get_log_path())
                handler.setLevel(logging.DEBUG)

                formatter = logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                handler.setFormatter(formatter)
                _logger.addHandler(handler)

            # Prevent propagation to root logger
            _logger.propagate = False

    return _logger


def ai_log(level: str, message: str, **context: Any) -> None:
    """
    Log with context - writes immediately to file.

    Args:
        level: Log level (debug, info, warning, error)
        message: Main log message
        **context: Additional key=value pairs to include

    Examples:
        ai_log("info", "Starting generation", job_id="abc123")
        ai_log("error", "HTTP timeout", url="https://...", timeout=600)
    """
    logger = get_ai_logger()

    # Format context as pipe-separated key=value pairs
    ctx_str = ""
    if context:
        ctx_parts = []
        for k, v in context.items():
            # Truncate long values
            v_str = str(v)
            if len(v_str) > 200:
                v_str = v_str[:200] + "..."
            ctx_parts.append(f"{k}={v_str}")
        ctx_str = " | " + " | ".join(ctx_parts)

    full_msg = f"{message}{ctx_str}"

    # Log at appropriate level
    if level == "debug":
        logger.debug(full_msg)
    elif level == "info":
        logger.info(full_msg)
    elif level == "warning":
        logger.warning(full_msg)
    elif level == "error":
        logger.error(full_msg)
    else:
        logger.info(full_msg)

    # Force flush to ensure log is written immediately
    # This is critical for catching logs before worker crash
    for handler in logger.handlers:
        handler.flush()


__all__ = ["ai_log", "get_ai_logger", "get_log_path"]
