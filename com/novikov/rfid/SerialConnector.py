import logging
from time import sleep

from serial import Serial, SerialException


__author__ = 'Ilia Novikov'


class SerialConnector:
    __CODE_OPEN = 1
    __CODE_IDLE = 2
    __CODE_LOCK = 3
    __CODE_LED_OK = 4
    __CODE_LED_FAIL = 5
    __CODE_MAINTENANCE = 6
    __TIMEOUT = 1

    def __init__(self, device, speed):
        logging.info("Подключение к UART-устройству {} на скорости {} бод".format(
            device if device else '???',
            speed
        ))
        self.device = device
        self.speed = int(speed)

    def __send(self, data):
        if not self.device:
            logging.error("UART-устройство не задано")
            return
        try:
            data = str(data).encode()
            serial = Serial(self.device, self.speed, timeout=self.__TIMEOUT)
            serial.write(data)
            sleep(10.0 / 1000.0)
            serial.close()
        except SerialException as e:
            logging.error("Ошибка конфигурации UART-устройства: {}".format(e))
        except ValueError as e:
            logging.error("Ошибка конфигурации UART-устройства: {}".format(e))

    def open(self):
        self.__send(self.__CODE_OPEN)
        self.__send(self.__CODE_LED_OK)

    def standard(self):
        self.__send(self.__CODE_IDLE)

    def lock(self):
        self.__send(self.__CODE_LOCK)

    def error(self):
        self.__send(self.__CODE_LED_FAIL)

    def maintenance(self):
        self.__send(self.__CODE_MAINTENANCE)