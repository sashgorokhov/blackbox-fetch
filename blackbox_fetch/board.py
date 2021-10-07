import logging
import time

from yamspy import MSPy



logger = logging.getLogger(__name__)


class Board(MSPy):
    def __init__(self, device):
        self.device = device
        super(Board, self).__init__(
            device=device,
            logfilename='board.log',
            loglevel='DEBUG'
        )

    def basic_info(self):
        pass

    def reboot(self, mode):
        self.send_RAW_msg(MSPy.MSPCodes['MSP_SET_REBOOT'], data=self.convert([mode]))

    def send_and_process(self, cmd):
        if self.send_RAW_msg(cmd):
            dataHandler = self.receive_msg()
            self.process_recv_data(dataHandler)

    def show_board_info(self):
        self.send_and_process(MSPy.MSPCodes['MSP_API_VERSION'])
        self.send_and_process(MSPy.MSPCodes['MSP_NAME'])
        logger.info('MSP protocol version: %s', self.CONFIG['mspProtocolVersion'])
        logger.info('Api version: %s', self.CONFIG['apiVersion'])
        logger.info('Name: %s', self.CONFIG['name'])

    def show_blackbox_stats(self):
        self.send_and_process(MSPy.MSPCodes['MSP_DATAFLASH_SUMMARY'])
        used = self.DATAFLASH['usedSize'] or 0
        total = self.DATAFLASH['totalSize'] or 1
        logger.info(f'Blackbox used: {used}/{total} {round(used / total, 1) * 100}%')

    def is_dataflash_ready(self) -> bool:
        self.send_and_process(MSPy.MSPCodes['MSP_DATAFLASH_SUMMARY'])
        return self.DATAFLASH['ready']

    def erase_dataflash(self):
        self.send_RAW_msg(MSPy.MSPCodes['MSP_DATAFLASH_ERASE'])
