import contextlib
import logging
import shutil
import time
from pathlib import Path
from typing import ContextManager

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog

from blackbox_fetch import logs, io, config, msp
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

        self.fs = io.Filesystem.get_filesystem()  # pylint: disable=invalid-name

        super().__init__()

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
            self.set_progress.emit(100)
            self.set_status.emit('Unexpected error occured')

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
        self.set_status.emit('Please reconnect device usb')
        self.erase_blackbox()
        self.set_status.emit('Job done, happy debugging!')
        self.set_progress.emit(100)

    def reboot_into_storage(self):
        with self.connect_blackbox_board() as board:
            resp: msp.MSP_DATAFLASH_SUMMARY = board.send_command(msp.MSP_DATAFLASH_SUMMARY)
            logger.info(f'Blackbox used: {resp.used_size}/{resp.total_size} {round(resp.used_size / resp.total_size, 1) * 100}%')
            board.send_command(msp.MSP_REBOOT_MSD)

    def copy_blackbox_files(self):
        paths = self.fs.get_blackbox_files()
        while not self.stop and not paths:
            time.sleep(0.1)
            paths = self.fs.get_blackbox_files()

        self.checkstop()

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
        with self.connect_blackbox_board() as board:
            self.set_status.emit('Erasing blackbox')
            board.send_command(msp.MSP_DATAFLASH_ERASE)

            while not self.stop and not board.send_command(msp.MSP_DATAFLASH_SUMMARY).ready:
                time.sleep(1)

            self.checkstop()

    @contextlib.contextmanager
    def connect_blackbox_board(self) -> ContextManager[msp.SerialMSP]:
        device = self.fs.get_msp_device()

        while not self.stop and not device:
            time.sleep(0.1)
            device = self.fs.get_msp_device()

        self.checkstop()
        logger.info(f'Connected to {device}')

        with msp.SerialMSP(port=device) as ser:
            yield ser


class MainWindow(Ui_MainWindow, QMainWindow):
    def __init__(self, app: QApplication):
        self.app = app

        super().__init__()

        self.setupUi(self)

        package_logger = logging.getLogger('blackbox_fetch')
        handler = logs.StatusBarHandler(self.statusBar())
        handler.setLevel(logging.INFO)
        package_logger.addHandler(handler)

        self.output_folder_edit.setText(str(config.BASE_DIR))
        self.output_folder_button.clicked.connect(self.output_folder_edit_clicked)

        self._background_task = Background()
        self._background_task.set_status.connect(self.status_label.setText)
        self._background_task.set_progress.connect(self.progressBar.setValue)
        self._background_task.finished.connect(self.close)
        QThreadPool.globalInstance().start(self._background_task.entrypoint)

    def output_folder_edit_clicked(self):
        directory = QFileDialog.getExistingDirectory(
            parent=self,
            options=QFileDialog.Option.ShowDirsOnly,
            directory=str(config.BASE_DIR)
        )
        logger.debug(f'Set output directory: {directory}')
        self._background_task.output_directory = Path(directory)
        self.output_folder_edit.setText(directory)

    def closeEvent(self, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
        """Terminate application if main window closed"""
        self._background_task.stop = True
        logger.info('Waiting for background run to stop')
        QThreadPool.globalInstance().waitForDone()
        self.app.quit()
