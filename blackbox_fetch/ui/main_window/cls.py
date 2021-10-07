import contextlib
import logging
import shutil
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog

from blackbox_fetch import logs, io, config
from blackbox_fetch.board import Board
from blackbox_fetch.ui.main_window.form import Ui_MainWindow

logger = logging.getLogger(__name__)


class BackgroundStop(Exception):
    pass


class Background(QObject):
    set_progress = pyqtSignal(int)
    set_status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        self.stop = False
        self.output_directory = config.BASE_DIR
        self._progress = 0

        super(Background, self).__init__()

    def checkstop(self):
        if self.stop:
            logger.debug('Force stopping background job')
            raise BackgroundStop()

    def entrypoint(self):
        try:
            self.run()
        except BackgroundStop:
            logger.debug('Stopping background run')
            return
        except:
            logger.exception('Background run failed')
            if not self.stop:
                self.finished.emit()

    def run(self):
        self.set_progress.emit(0)
        self.set_status.emit('Looking for device to reboot')
        self.reboot_into_storage()
        self.set_progress.emit(20)
        self.set_status.emit('Copying blackbox files')
        self.copy_blackbox_files()
        self.set_progress.emit(80)
        if sys.platform == 'win32':
            import winsound
            winsound.Beep(1500, 150)
            winsound.Beep(1500, 150)
            winsound.Beep(1500, 150)
        self.set_status.emit('Please reconnect device usb')
        self.erase_blackbox()
        self.set_status.emit('Job done, happy debugging!')
        self.set_progress.emit(100)

    def reboot_into_storage(self):
        with self.connect_betafl_board() as board:
            board.show_board_info()
            board.show_blackbox_stats()
            board.reboot(2)
            time.sleep(2)

    def copy_blackbox_files(self):
        paths = list(io.iter_blackbox_paths())
        logger.debug(f'Found {len(paths)} blackbox files: {paths}')

        if not paths:
            logger.info('No blackbox files found')
            return

        progress_value = 20
        progress_increment = int(60 / len(paths))

        for blackbox_src in paths:
            self.checkstop()
            blackbox_src = blackbox_src.resolve()
            blackbox_dst = self.output_directory / blackbox_src.name
            logger.info(f'{blackbox_src} -> {blackbox_dst}')
            if not blackbox_dst.exists():
                shutil.copyfile(blackbox_src, blackbox_dst)

            progress_value += progress_increment
            self.set_progress.emit(progress_value)

    def erase_blackbox(self):
        logger.debug('Waiting for device to erase blackbox')
        with self.connect_betafl_board() as board:
            self.set_status.emit('Erasing blackbox')
            board.erase_dataflash()
            self.wait_dataflash_ready(board)

    def wait_dataflash_ready(self, board: Board):
        while not self.stop and not board.is_dataflash_ready():
            time.sleep(1)

        self.checkstop()

    def wait_for_devices(self):
        while not self.stop:
            devices = io.list_devices()
            if devices:
                return devices
            else:
                time.sleep(0.1)

        self.checkstop()

    @contextlib.contextmanager
    def connect_betafl_board(self):
        while not self.stop:
            devices = self.wait_for_devices()
            logger.info('Available devices: %s', devices)

            for device in devices:
                try:
                    logger.debug('Trying to connect to %s', device)
                    board = Board(device=device)
                    with board:
                        if board:
                            logger.info('Connected to %s', device)
                            yield board
                            return
                        else:
                            logger.info('Failed to connect %s', device)
                            continue
                except:
                    logger.exception('Error connecting to %s', device)
                    continue

            time.sleep(0.1)

        self.checkstop()


class MainWindow(Ui_MainWindow, QMainWindow):
    def __init__(self, app: QApplication):
        self.app = app

        super(MainWindow, self).__init__()

        self.setupUi(self)

        package_logger = logging.getLogger('blackbox_fetch')
        handler = logs.StatusBarHandler(self.statusBar())
        handler.setLevel(logging.INFO)
        package_logger.addHandler(handler)

        self._background_task = Background()
        self._background_task.set_status.connect(self.status_label.setText)
        self._background_task.set_progress.connect(self.progressBar.setValue)
        self._background_task.finished.connect(self.close)
        QThreadPool.globalInstance().start(self._background_task.entrypoint)

        self.output_folder_edit.setText(str(config.BASE_DIR))
        self.output_folder_button.clicked.connect(self.output_folder_edit_clicked)

    def output_folder_edit_clicked(self):
        directory = QFileDialog.getExistingDirectory(
            parent=self,
            options=QFileDialog.Option.ShowDirsOnly,
            directory=str(config.BASE_DIR)
        )
        logger.debug('Set output directory: %s', directory)
        self._background_task.output_directory = Path(directory)
        self.output_folder_edit.setText(directory)

    def closeEvent(self, *args, **kwargs):
        """Terminate application if main window closed"""
        self._background_task.stop = True
        logger.info('Waiting for background run to stop')
        QThreadPool.globalInstance().waitForDone()
        self._app.quit()
