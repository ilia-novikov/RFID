from http.server import HTTPServer
import logging
import os
import socket
import ssl
from subprocess import Popen
from threading import Thread

from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.server.ServerHandler import ServerHandler


__author__ = 'Ilia Novikov'


class Server(Thread):
    SSL_CERTIFICATE = 'keys/server.pem'

    def __init__(self, port, streaming: bool, db: DatabaseConnector, serial: SerialConnector):
        Thread.__init__(self)
        self.logger = logging.getLogger()
        host = socket.gethostname()
        self.logger.info("Сервер был запущен по адресу {}:{}".format(host, port))
        if not os.path.exists(self.SSL_CERTIFICATE):
            self.logger.warning("Не найден SSL сертификат")
            self.logger.warning("Будет создан новый SSL сертификат")
            print("Создание SSL сертификата для {}".format(host))
            Popen(['./generate'], shell=True).wait()
        if streaming:
            stream_port = 8080
            buffer = 2 * 1024
            self.stream = self.__start_stream(host, stream_port, '/dev/video0', buffer)
            handler = lambda *args: ServerHandler(host, db, serial, stream_port, *args)
        else:
            self.stream = None
            self.logger.info("Поддержка камеры была отключена")
            handler = lambda *args: ServerHandler(host, db, serial, None, *args)
        binding = (host, port)
        self.server = HTTPServer(binding, handler)
        self.server.socket = ssl.wrap_socket(self.server.socket, certfile=self.SSL_CERTIFICATE, server_side=True)

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

    def run(self):
        self.server.serve_forever()

