import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables for tracing across async functions
ctx_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
ctx_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
ctx_document_id: ContextVar[str | None] = ContextVar("document_id", default=None)
ctx_task_id: ContextVar[str | None] = ContextVar("task_id", default=None)


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON including contextual IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Automatically attach contextual IDs if set
        request_id = ctx_request_id.get()
        if request_id:
            log_entry["request_id"] = request_id

        tenant_id = ctx_tenant_id.get()
        if tenant_id:
            log_entry["tenant_id"] = tenant_id

        document_id = ctx_document_id.get()
        if document_id:
            log_entry["document_id"] = document_id

        task_id = ctx_task_id.get()
        if task_id:
            log_entry["task_id"] = task_id

        # Attach exception details if an error was raised
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configures structured JSON logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(console_handler)

    # Silence noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root_logger
