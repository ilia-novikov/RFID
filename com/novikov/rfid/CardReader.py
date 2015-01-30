from threading import Thread

from evdev import InputDevice

__author__ = 'ilia'


class CardReader(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.daemon = True
        self.parent = parent

    def run(self):
        path = '/dev/input/by-id/usb-Sycreader_RFID_Technology_Co.__Ltd_SYC_ID_IC_USB_Reader_08FF20140315-event-kbd'
        device = InputDevice(path)
        try:
            while True:
                if self.parent.is_waiting_card:
                    device.ungrab()
                else:
                    device.grab()
        except SystemExit:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            device.ungrab()
            device.close()