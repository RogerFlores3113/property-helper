"""structlog JSON logging configuration."""
from __future__ import annotations

import structlog


def configure_logging() -> None:
    """Configure structlog to emit ISO-timestamped JSON log lines."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


log = structlog.get_logger()
