"""Structured logging setup with correlation ID support."""

import logging
import sys
import uuid
from contextvars import ContextVar

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """
    Get current correlation ID or generate a new one.
    
    Returns:
        Correlation ID string (UUID)
    """
    corr_id = correlation_id_var.get()
    if corr_id is None:
        corr_id = str(uuid.uuid4())
        correlation_id_var.set(corr_id)
    return corr_id


def set_correlation_id(corr_id: str) -> None:
    """
    Set correlation ID for current context.
    
    Args:
        corr_id: Correlation ID string
    """
    correlation_id_var.set(corr_id)


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to log record."""
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


def configure_logging(level: int = logging.INFO, verbose: bool = False) -> None:
    """
    Configure structured logging with correlation ID support.
    
    Args:
        level: Logging level (default: INFO)
        verbose: If True, show HTTP logs at INFO level. If False, suppress HTTP logs to DEBUG.
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s correlation_id=%(correlation_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIDFilter())
    
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    
    # Configure HTTP client logging to respect verbose mode
    # httpx is used by pyzotero for HTTP requests
    # httpcore is the underlying HTTP library used by httpx
    http_loggers = [
        "httpx",
        "httpcore",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.connection",
    ]
    
    if verbose:
        # In verbose mode, allow INFO level HTTP logs
        for logger_name in http_loggers:
            http_logger = logging.getLogger(logger_name)
            http_logger.setLevel(logging.INFO)
    else:
        # In default mode, suppress HTTP logs to DEBUG level
        for logger_name in http_loggers:
            http_logger = logging.getLogger(logger_name)
            http_logger.setLevel(logging.DEBUG)
