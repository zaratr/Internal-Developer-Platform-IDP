import logging
import sys
from logging.config import dictConfig

from app.core.request_context import get_request_id


def setup_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "format": (
                        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                        '"logger": "%(name)s", "message": "%(message)s", '
                        '"request_id": "%(request_id)s"}'
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "json",
                    "stream": sys.stdout,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or get_request_id()
        return True


logging.getLogger().addFilter(RequestIdFilter())
