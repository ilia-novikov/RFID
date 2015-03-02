from http.server import BaseHTTPRequestHandler
import logging
from os import path
from base64 import b64decode

from magic import Magic

from com.novikov.rfid.VisitsLogger import VisitsLogger


__author__ = 'Ilia Novikov'


class ServerHandler(BaseHTTPRequestHandler):
    directories = {
        'root': 'www',
        'secure': 'www/secure/',
        'templates': 'www/templates/',
        'pages': 'www/pages/',
        'include': 'www/include/'
    }

    db = None
    logger = logging.getLogger()
    routes = {}

    def authorize(self, filename):
        header = self.headers['Authorization']
        if not header:
            self.do_AUTHHEAD()
            self.generate_error("авторизация не была завершена")
        else:
            header = header[header.find(' '):]
            users = self.db.get_all_users()
            card, password = b64decode(header).decode('utf-8').split(':')
            user = [x for x in users if card in x.cards and x.check_password(password)]
            if user:
                mime = Magic(mime=True).from_file(filename)
                self.send_response(200)
                self.send_header('Content-type', mime)
                with open(filename, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.do_AUTHHEAD()
                self.generate_error("неверный логин или пароль")

    def generate(self, name, title, body, code=200):
        template = self.directories['templates'] + name + '.html'
        base = self.directories['templates'] + 'base' + '.html'
        if not path.exists(template):
            pass
        with open(base) as base:
            with open(template) as file:
                html = base.read().format(title, file.read())
                html = html.format(body)
                self.send_response(code)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())

    def generate_error(self, message, code=200):
        self.generate('error', 'Ошибка сервера', message, code)

    def generate_logs(self):
        with open(VisitsLogger.VISITS_LOG) as log:
            events = [x.strip() for x in log.readlines()[-20:]]
            view = ''.join(['<li>{}</li>'.format(x) for x in events])
            self.generate('logs', "Лог посещений", view)

    def generate_camera(self):
        self.generate('camera', 'Камера', '')

    def not_found(self):
        self.generate_error("файл не найден", code=404)

    def redirect(self, url):
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

    def route(self, filename):
        if self.directories['secure'] in filename:
            self.authorize(filename)
            return
        self.send_file(filename)

    def send_file(self, filename):
        if path.exists(filename) and path.isfile(filename):
            mime = Magic(mime=True).from_file(filename)
            self.send_response(200)
            self.send_header('Content-type', mime)
            with open(filename, 'rb') as file:
                self.wfile.write(file.read())
        else:
            self.not_found()

    def do_GET(self):
        self.routes = {
            '/': lambda: self.redirect('/home'),
            '/home': lambda: self.generate('home', "Сервер RFID", ''),
            '/test': lambda: self.route(self.directories['secure'] + 'test.jpg'),
            '/logs': lambda: self.generate_logs(),
            '/camera': lambda: self.generate_camera()
        }
        url = self.path
        if url in self.routes:
            self.routes[url]()
            return
        if url.startswith('/include'):
            filename = self.directories['root'] + url
            self.send_file(filename)
            return
        self.not_found()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Access to RFID server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()