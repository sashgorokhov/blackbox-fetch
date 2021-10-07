import string
import sys
import time
from pathlib import Path
from typing import List, Generator
import serial.tools.list_ports


def _list_devices_win():
    return [comport.device for comport in serial.tools.list_ports.comports()]


def _list_drives_win() -> List[Path]:
    return list(filter(lambda p: p.exists(), (Path(f'{letter}:/') for letter in string.ascii_uppercase)))


def list_drives() -> List[Path]:
    if sys.platform == 'win32':
        return _list_drives_win()
    raise NotImplementedError()


def list_devices():
    if sys.platform == 'win32':
        return _list_devices_win()
    raise NotImplementedError()


def iter_blackbox_paths() -> Generator[Path, None, None]:
    for drive in list_drives():
        yield from drive.glob('*.bbl')
