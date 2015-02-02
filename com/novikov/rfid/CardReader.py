import logging
import os
from threading import Thread
from time import sleep

from evdev import InputDevice


__author__ = 'Ilia Novikov'


class CardReader(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.daemon = True
        self.parent = parent
        self.name = "CardReaderThread"

    def run(self):
        path = '/dev/input/by-id/usb-Sycreader_RFID_Technology_Co.__Ltd_SYC_ID_IC_USB_Reader_08FF20140315-event-kbd'
        if not os.path.exists(path):
            logging.error("Считыватель RFID не подключен")
            return
        device = InputDevice(path)
        is_locked = False
        try:
            while True:
                if self.parent.is_waiting_card and is_locked:
                    attempt = 0
                    while True:
                        try:
                            attempt += 1
                            logging.info("Попытка разблокировать считыватель карт ({})".format(attempt))
                            device.ungrab()
                            logging.info("Попытка удачна, считыватель разблокирован")
                            attempt = 0
                            is_locked = False
                            break
                        except OSError:
                            logging.info("Ошибка при разблокировании считывателя")
                            pass
                elif not self.parent.is_waiting_card and not is_locked:
                    attempt = 0
                    while True:
                        try:
                            attempt += 1
                            logging.info("Попытка блокировать считыватель карт ({})".format(attempt))
                            device.grab()
                            logging.info("Попытка удачна, считыватель блокирован")
                            is_locked = True
                            break
                        except OSError:
                            logging.info("Ошибка при блокировании считывателя")
                            pass
                else:
                    sleep(0.5)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            device.ungrab()
            device.close()