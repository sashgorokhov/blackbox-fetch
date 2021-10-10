import abc
import logging
import string
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import serial.tools.list_ports
from blackbox_fetch import msp

logger = logging.getLogger(__name__)


BLACKBOX_FLASH_DRIVE_NAMES = (
    'Betaflight Onboard Flash',
)


def is_blackbox_device(device: str) -> bool:
    try:
        with msp.SerialMSP(port=device) as ser:
            resp: msp.MSP_FC_VARIANT = ser.send_command(msp.MSP_FC_VARIANT)
            logger.debug(f'Successfully connected to MSP device {device}: {resp.fc_variant}')
            return True
    except:
        logger.debug(f'Considering not a blackbox compatible MSP device {device} because of MSP error or what')

    return False


class Filesystem(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_msp_device(self) -> Optional[str]:
        ...

    @abc.abstractmethod
    def get_blackbox_files(self) -> List[Path]:
        ...

    @classmethod
    def get_filesystem(cls) -> 'Filesystem':
        if sys.platform == 'win32':
            return FilesystemWindows()
        raise NotImplementedError()


class FilesystemWindows(Filesystem):
    def get_msp_device(self) -> Optional[str]:
        devices = [comport.device for comport in serial.tools.list_ports.comports()]

        if not devices:
            return None

        logger.debug(f'Available devices: {devices}')

        for device in devices:
            logger.debug(f'Trying {device}')
            if is_blackbox_device(device):
                return device

        return None

    def get_blackbox_files(self) -> List[Path]:
        drive = self.get_blackbox_drive()

        if not drive:
            return []

        return list(drive.glob('*.bbl'))

    @staticmethod
    def get_blackbox_drive() -> Optional[Path]:
        import win32api  # pylint: disable=import-outside-toplevel

        drives = list(filter(lambda p: p.exists(), (Path(f'{letter}:/') for letter in string.ascii_uppercase)))
        drive_labels: List[Tuple[Path, str]] = [(drive, str(win32api.GetVolumeInformation(str(drive))[0])) for drive in drives]

        if not drives:
            return None

        for drive, label in drive_labels:
            if label in BLACKBOX_FLASH_DRIVE_NAMES:
                return drive

        return None
