from threading import Thread

from evdev import InputDevice, KeyEvent
from evdev import ecodes

from Main import Main


__author__ = 'ilia'


class CardReader(Thread):
    codes = {
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

    def __init__(self, parent: Main):
        Thread.__init__(self)
        self.daemon = False
        self.parent = parent

    def run(self):
        path = '/dev/input/by-id/usb-Sycreader_RFID_Technology_Co.__Ltd_SYC_ID_IC_USB_Reader_08FF20140315-event-kbd'
        device = InputDevice(path)
        device.grab()
        try:
            buffer = []
            for event in device.read_loop():
                if self.parent.terminating:
                    break
                if event.type != ecodes.EV_KEY:
                    continue
                press = KeyEvent(event)
                if press.keystate != KeyEvent.key_down:
                    continue
                char = self.codes[press.scancode]
                if char == 'enter':
                    card = ''.join(buffer)
                    self.parent.notify_card(card)
                    buffer.clear()
                    continue
                buffer.append(str(char))
        except KeyboardInterrupt:
            pass
        finally:
            device.ungrab()
            device.close()


CardReader()