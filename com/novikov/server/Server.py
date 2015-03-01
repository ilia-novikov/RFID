from http.server import HTTPServer

from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.server.ServerHandler import ServerHandler


__author__ = 'Ilia Novikov'


class Server:
    def __init__(self, port, db: DatabaseConnector):
        server = None
        try:
            handler = ServerHandler
            handler.db = db
            server = HTTPServer(('localhost', port), ServerHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            if server:
                server.socket.close()