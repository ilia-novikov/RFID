from http.server import HTTPServer
import logging
import os

from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.server.ServerHandler import ServerHandler


__author__ = 'Ilia Novikov'


class Server:
    def __init__(self, port, db: DatabaseConnector, serial: SerialConnector):
        server = None
        try:
            self.logger = logging.getLogger()
            self.logger.info("Сервер был запущен на порту {}".format(port))
            stream_port = 8080
            host = '192.168.1.207'
            self.stream = self.start_stream(host, stream_port, '/dev/video0', 2048)
            handler = lambda *args: ServerHandler(host, db, serial, stream_port, *args)
            binding = (host, port)
            server = HTTPServer(binding, handler)
            server.serve_forever()
        except KeyboardInterrupt:
            if server:
                server.socket.close()
            if self.stream:
                self.stream.close()

    def start_stream(self, host, port, source, buffer):
        command = 'su {} -c \'vlc v4l://:v4l-vdev="{}" :sout="#transcode{{vcodec=theo,vb={},scale=1,acodec=vorb,' \
                  'ab=128,channels=2,samplerate=44100}}:http{{mux=ogg,dst={}:{}/stream}}" :sout-keep\ > /dev/null 2>&1\''
        command = command.format(
            'ilia',
            source,
            buffer,
            host,
            port
        )
        self.logger.info("Сетевой поток камеры был запущен на порту {}".format(port))
        return os.popen(command)