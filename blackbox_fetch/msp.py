import dataclasses
import logging
import struct
import threading
import time
from typing import Union, List, Type, Optional, Tuple, TypeVar

import serial

logger = logging.getLogger(__name__)


class SerialError(Exception):
    pass


class SerialConnection:
    def __init__(self, port: str):
        self.port = port
        self._conn = serial.Serial()
        self._conn.port = port
        self._conn.baudrate = 115200
        self._conn.bytesize = serial.EIGHTBITS
        self._conn.parity = serial.PARITY_NONE
        self._conn.stopbits = serial.STOPBITS_ONE
        self._conn.timeout = 1
        self._conn.xonxoff = False
        self._conn.rtscts = False
        self._conn.dsrdtr = False
        self._conn.writeTimeout = 1

        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()

        self.trials = 3

    def __enter__(self):
        if self._conn.is_open:
            logger.warning(f'Attempting to open already opened serial port {self.port}')
            return self

        for _ in range(self.trials):
            try:
                self._conn.open()
                break
            except Exception as e:
                logger.error(f'Port {self.port} connection exception')

            time.sleep(0.5)
        else:
            raise SerialError(f'Failed to connect to {self.port}')

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._conn.closed:
            self._conn.close()

    def write(self, buffer: Union[bytes, bytearray]) -> int:
        with self._write_lock:
            return self._conn.write(buffer)

    def read(self, size: int = 1) -> bytes:
        with self._read_lock:
            return self._conn.read(size)


@dataclasses.dataclass
class MSPResponse:
    msp_code: bytes
    data: bytes

    length: bytes
    preamble: bytes
    crc: bytes

    @property
    def msp_code_i(self) -> int:
        return struct.unpack('<B', self.msp_code)[0]

    @property
    def length_i(self) -> int:
        return struct.unpack('<B', self.length)[0]

    @property
    def crc_i(self) -> int:
        return struct.unpack('<B', self.crc)[0]

    def calc_crc(self) -> int:
        crc = self.length_i ^ self.msp_code_i

        for data_b in self.data:
            crc ^= data_b

        return crc


class MSPCommand:
    code: int = 0
    payload: List[int] = None

    need_response = False

    @classmethod
    def make_request(cls) -> Tuple[int, Union[List[int], bytearray]]:
        return cls.code, cls.payload or []

    @classmethod
    def make_response(cls, response: MSPResponse):
        raise NotImplemented()


@dataclasses.dataclass
class MSP_API_VERSION(MSPCommand):
    code = 1

    need_response = True

    msp_protocol_version: int
    api_version: str

    @classmethod
    def make_response(cls, response: MSPResponse) -> 'MSP_API_VERSION':
        data = struct.unpack('<BBB', response.data)
        protocol_version, api_version_major, api_version_minor = data
        return cls(
            msp_protocol_version=protocol_version,
            api_version=f'{api_version_major}.{api_version_minor}'
        )


@dataclasses.dataclass()
class MSP_FC_VARIANT(MSPCommand):
    code = 2

    need_response = True

    fc_variant: str

    @classmethod
    def make_response(cls, response: MSPResponse) -> 'MSP_FC_VARIANT':
        data = struct.unpack('<4c', response.data)

        return cls(
            fc_variant=''.join(map(lambda c: c.decode(), data))
        )


@dataclasses.dataclass()
class MSP_REBOOT_MSD(MSPCommand):
    code = 68
    payload = [2]
    need_response = False


@dataclasses.dataclass()
class MSP_DATAFLASH_SUMMARY(MSPCommand):
    code = 70
    need_response = True

    ready: bool
    supported: bool
    sectors: int
    total_size: int
    used_size: int

    @classmethod
    def make_response(cls, response: MSPResponse) -> 'MSP_DATAFLASH_SUMMARY':
        data = struct.unpack('<BIII', response.data)
        ready_supported, sectors, total, used = data

        return MSP_DATAFLASH_SUMMARY(
            ready=(ready_supported & 1) != 0,
            supported=(ready_supported & 2) != 0,
            sectors=sectors,
            total_size=total,
            used_size=used,
        )


@dataclasses.dataclass()
class MSP_DATAFLASH_ERASE(MSPCommand):
    code = 72
    need_response = False


T = TypeVar('T', bound=MSPCommand)


def payload_prepare(data, n=16):
    buffer = []
    for val in data:
        for i in range(int(n / 8)):
            buffer.append((int(val) >> i * 8) & 255)
    return buffer


class SerialMSP(SerialConnection):
    """
    https://www.hamishmb.com/multiwii/wiki/index.php?title=Multiwii_Serial_Protocol
    """

    def __init__(self, *args, **kwargs):
        super(SerialMSP, self).__init__(*args, **kwargs)

        self._msp_read_lock = threading.Lock()

    def _send(self, msp_code: int, payload: Union[List[int], bytearray] = None):
        payload = payload or []

        s_payload = len(payload)

        assert msp_code < 255

        s_buffer = s_payload + 6

        buffer = bytearray([0] * s_buffer)

        buffer[0] = 36  # $
        buffer[1] = 77  # M
        buffer[2] = 60  # <
        buffer[3] = s_payload
        buffer[4] = msp_code

        checksum = buffer[3] ^ buffer[4]

        for n, value in enumerate(payload, start=5):
            buffer[n] = value
            checksum ^= value

        buffer[-1] = checksum

        self.write(buffer)

    def _recv(self) -> MSPResponse:
        with self._msp_read_lock:
            preamble = self.read(3)
            length = self.read(1)
            code = self.read(1)

            length_i = struct.unpack('<B', length)[0]
            data = self.read(length_i)

            crc = self.read(1)

        response = MSPResponse(
            preamble=preamble,
            length=length,
            msp_code=code,
            data=data,
            crc=crc,
        )

        if response.crc_i != response.calc_crc():
            logger.debug(f'CRC check failed: expected {response.crc}, got {response.calc_crc()}: {response}')
            raise SerialError(f'CRC check failed: {response}')

        return response

    def send_command(self, command: Type[T]) -> Optional[T]:
        logger.debug(f'Send: {command.__name__}')
        msp_code, payload = command.make_request()

        payload = payload_prepare(payload)

        self._send(msp_code=msp_code, payload=payload)

        try:
            response = self._recv()
        except:
            if command.need_response:
                raise
            else:
                logger.warning('Tried to receive serial response but got error, skipping')

        if command.need_response:
            try:
                r = command.make_response(response)
                logger.debug(f'Response: {r}')
                return r
            except SerialError:
                raise
            except:
                logger.exception(f'Failed to build command {command.__name__} response from {response}')
                raise SerialError('Foo bar :(')
