import os
import sys
from pathlib import Path

APP_NAME: str = 'blackbox_fetch'

EXECUTABLE_PATH: Path = Path(sys.argv[0]).absolute()

FROZEN: bool = getattr(sys, 'frozen', False)

if FROZEN:
    BASE_DIR: Path = EXECUTABLE_PATH.parent
else:
    BASE_DIR = Path(__file__).parents[1]

# TODO: Handle linux and mac
LOCALAPPDATA_DIR: Path = Path(os.environ.get('LOCALAPPDATA', BASE_DIR / 'LOCALAPPDATA'))
APP_DATA_DIR = LOCALAPPDATA_DIR / APP_NAME
SETTINGS_DIR: Path = APP_DATA_DIR / 'Settings'
LOGS_DIR: Path = APP_DATA_DIR / 'Logs'
