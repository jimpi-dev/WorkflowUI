import logging
import logging.config
import os
from typing import Literal


EnvType = Literal["development", "staging", "production"]


def _get_env() -> EnvType:
    raw = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").strip().lower()
    if raw in {"prod", "production"}:
        return "production"
    if raw in {"stage", "staging"}:
        return "staging"
    return "development"


def _get_default_log_level(env: EnvType) -> str:
    if env == "production":
        return "WARNING"
    if env == "staging":
        return "INFO"
    return "DEBUG"


def get_effective_log_level() -> str:
    """
    Resolve the effective minimum log level for the application.

    Order of precedence:
    1. APP_LOG_LEVEL (if set)
    2. APP_ENV / ENV (environment) specific default
    """
    env = _get_env()
    override = (os.environ.get("APP_LOG_LEVEL") or "").strip().upper()
    if override in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        return override
    return _get_default_log_level(env)


class ColorFormatter(logging.Formatter):
    """
    Simple ANSI color formatter for console output.
    Colors the log level name to make log lines easier to scan.
    """

    COLORS = {
        "DEBUG": "\x1b[36m",  # Cyan
        "INFO": "\x1b[32m",  # Green
        "WARNING": "\x1b[33m",  # Yellow
        "ERROR": "\x1b[31m",  # Red
        "CRITICAL": "\x1b[41m",  # Red background
    }
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        color = self.COLORS.get(original_levelname, "")
        if color:
            record.levelname = f"{color}{original_levelname}{self.RESET}"
        try:
            return super().format(record)
        finally:
            # Restore original value so other handlers/formatters are not affected
            record.levelname = original_levelname


def setup_logging() -> None:
    """
    Configure application-wide logging.

    This configures the root logger as well as commonly-used third-party loggers.
    It is safe to call multiple times; logging.config.dictConfig will replace
    existing handlers based on the dictionary configuration.
    """
    level = get_effective_log_level()
    env = _get_env()

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
            "simple": {
                "format": "%(levelname)s: %(message)s",
            },
            "color": {
                "()": "logging_config.ColorFormatter",
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "color" if env != "production" else "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
        "loggers": {
            # Uvicorn's loggers
            "uvicorn": {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                # Access logs can be noisy; keep them at INFO in non-production
                # and WARNING in production via level override below.
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            # Reduce noise from common libraries if needed
            "sqlalchemy.engine": {
                "level": "WARNING" if _get_env() == "production" else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    # Adjust uvicorn.access level for production specifically
    if _get_env() == "production":
        log_config["loggers"]["uvicorn.access"]["level"] = "WARNING"

    logging.config.dictConfig(log_config)

