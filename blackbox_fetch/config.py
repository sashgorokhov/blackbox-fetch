import os
import sys
from pathlib import Path


IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform == 'linux'

APP_NAME: str = 'blackbox_fetch'

EXECUTABLE_PATH: Path = Path(sys.argv[0]).absolute()

FROZEN: bool = getattr(sys, 'frozen', False)

if FROZEN:
    BASE_DIR: Path = EXECUTABLE_PATH.parent
else:
    BASE_DIR = Path(__file__).parents[1]

if IS_WINDOWS:
    LOCALAPPDATA_DIR: Path = Path(os.environ.get('LOCALAPPDATA', BASE_DIR / 'LOCALAPPDATA'))
elif IS_LINUX:
    LOCALAPPDATA_DIR: Path = (Path('~/.config') / APP_NAME).expanduser()
else:
    raise NotImplementedError('Unsupported platform')

APP_DATA_DIR = LOCALAPPDATA_DIR / APP_NAME
SETTINGS_DIR: Path = APP_DATA_DIR / 'Settings'
LOGS_DIR: Path = APP_DATA_DIR / 'Logs'
