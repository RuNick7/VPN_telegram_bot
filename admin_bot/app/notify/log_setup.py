"""Logging configuration with file output and error reporting."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.config.settings import settings


class ErrorReportingHandler(logging.Handler):
    """Custom handler that sends ERROR and above to admins."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.ERROR:
            # Schedule admin notification asynchronously
            import asyncio
            from app.notify.admin import send_admin_message

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        send_admin_message(f"🔴 Лог ошибки:\n\n{self.format(record)}")
                    )
                else:
                    asyncio.run(
                        send_admin_message(f"🔴 Лог ошибки:\n\n{self.format(record)}")
                    )
            except Exception:
                # Fallback: just log to stderr
                print(f"Failed to send error notification: {self.format(record)}", file=sys.stderr)


def setup_logging() -> None:
    """Configure logging to file and console."""
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Error reporting handler
    error_handler = ErrorReportingHandler()
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
