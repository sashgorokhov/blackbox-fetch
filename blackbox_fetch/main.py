import argparse
import contextlib
import logging
import sys

from PyQt6.QtWidgets import QApplication

from blackbox_fetch import config, logs
from blackbox_fetch.ui.main_window.cls import MainWindow

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def application() -> QApplication:
    app = QApplication([])
    app.setApplicationName(config.APP_NAME)
    yield app
    app.exec()


def ui_entrypoint():
    with application() as app:
        window = MainWindow(app)
        window.show()


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()  # pylint: disable=unused-variable

    logs.configure()

    try:
        ui_entrypoint()
    except:
        logger.exception('Error in entrypoint')
        sys.exit(-1)


if __name__ == '__main__':
    main()
