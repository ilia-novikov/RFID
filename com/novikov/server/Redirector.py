from http.server import HTTPServer
from threading import Thread

from com.novikov.server.RedirectionHandler import RedirectionHandler


__author__ = 'ilia'


class Redirector(Thread):
    HTTP_PORT = 80

    def __init__(self, host):
        Thread.__init__(self)
        self.host = host

    def run(self):
        RedirectionHandler.url = 'https://' + self.host
        HTTPServer((self.host, self.HTTP_PORT), RedirectionHandler).serve_forever()