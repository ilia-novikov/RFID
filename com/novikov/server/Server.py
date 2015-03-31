from http.server import HTTPServer
import logging
import os
import socket
import ssl
from subprocess import Popen
from threading import Thread

from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.server.Redirector import Redirector
from com.novikov.server.ServerHandler import ServerHandler


__author__ = 'Ilia Novikov'


class Server(Thread):
    SSL_CERTIFICATE = 'keys/server.pem'
    HTTPS_PORT = 443
    STREAM_PORT = 8080
    STREAM_SOURCE = '/dev/video0'
    STREAM_BUFFER = 2 * 1024

    def __init__(self, debug: bool, streaming: bool, db: DatabaseConnector, serial: SerialConnector):
        Thread.__init__(self)
        self.logger = logging.getLogger()
        host = self.__resolve_hostname() if debug else socket.gethostname()
        self.logger.info("Сервер был запущен по адресу {}:{}".format(host, self.HTTPS_PORT))
        if not os.path.exists(self.SSL_CERTIFICATE):
            self.logger.warning("Не найден SSL сертификат")
            self.logger.warning("Будет создан новый SSL сертификат")
            print("Создание SSL сертификата для {}".format(host))
            Popen(['./generate'], shell=True).wait()
        if streaming:
            self.stream = self.__start_stream(host, self.STREAM_PORT, self.STREAM_SOURCE, self.STREAM_BUFFER)
            handler = lambda *args: ServerHandler(debug, host, db, serial, self.STREAM_PORT, *args)
        else:
            self.stream = None
            self.logger.info("Поддержка камеры была отключена")
            handler = lambda *args: ServerHandler(debug, host, db, serial, None, *args)
        binding = (host, self.HTTPS_PORT)
        self.server = HTTPServer(binding, handler)
        self.is_running = True
        self.server.socket = ssl.wrap_socket(self.server.socket, certfile=self.SSL_CERTIFICATE, server_side=True)
        Redirector(host).start()

    def __start_stream(self, host, port, source, buffer):
        command = 'su {} -c \'vlc v4l://:v4l-vdev="{}" :sout="#transcode{{vcodec=theo,vb={},scale=1,acodec=vorb,' \
                  'ab=128,channels=2,samplerate=44100}}:http{{mux=ogg,dst={}:{}/stream}}" :sout-keep\ > /dev/null 2>&1\''
        command = command.format(
            'ilia',
            source,
            buffer,
            host,
            port
        )
        self.logger.info("Сетевой поток камеры был запущен по адресу {}:{}".format(host, port))
        return os.popen(command)

    @staticmethod
    def __resolve_hostname():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('google.com', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def run(self):
        while self.__is_running():
            self.server.handle_request()

    def __is_running(self):
        return self.is_running

    def stop(self):
        self.is_running = False
        self.server.shutdown()