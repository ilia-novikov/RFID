import logging
import os
from threading import Thread

from evdev import InputDevice, KeyEvent
from evdev import ecodes


__author__ = 'ilia'


class CardReader(Thread):
    __scan_codes = {
        2: 1,
        3: 2,
        4: 3,
        5: 4,
        6: 5,
        7: 6,
        8: 7,
        9: 8,
        10: 9,
        11: 0,
        28: 'enter'
    }

    def __init__(self, parent):
        Thread.__init__(self)
        self.daemon = True
        self.parent = parent
        self.card_id = ''

    def run(self):
        while True:
            try:
                path = \
                    '/dev/input/' \
                    'by-id/' \
                    'usb-Sycreader_RFID_Technology_Co.__Ltd_SYC_ID_IC_USB_Reader_08FF20140315-event-kbd'
                if not os.path.exists(path):
                    logging.error("Считыватель карт не подключен")
                    continue
                device = InputDevice(path)
                device.grab()
                buffer = []
                for event in device.read_loop():
                    if event.type != ecodes.EV_KEY:
                        continue
                    press = KeyEvent(event)
                    if press.keystate != KeyEvent.key_down:
                        continue
                    char = self.__scan_codes[press.scancode]
                    if char == 'enter':
                        if not self.parent.is_waiting_card:
                            buffer.clear()
                            continue
                        self.card_id = ''.join(buffer)
                        buffer.clear()
                        continue
                    buffer.append(str(char))
            except Exception:
                pass