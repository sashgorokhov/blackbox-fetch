"""
Logging configuration
"""
import logging
import logging.config

from PyQt6.QtWidgets import QStatusBar

from blackbox_fetch import config


def configure():
    """
    Contifure logging facilites
    """
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)


LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'short': {
            'format': '%(levelname)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'formatter': 'default',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': config.LOGS_DIR / f'{config.APP_NAME}.log',
            'maxBytes': 1024 * 1024,  # 1 mb
            'backupCount': 2
        },
    },
    'loggers': {
        'blackbox_fetch': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'ERROR'
    },
}


class StatusBarHandler(logging.StreamHandler):
    def __init__(self, status_bar: QStatusBar):
        self._status_bar = status_bar

        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._status_bar.clearMessage()
            self._status_bar.showMessage(msg, 5000)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
