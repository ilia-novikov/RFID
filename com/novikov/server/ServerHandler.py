from http.server import BaseHTTPRequestHandler
import logging
from os import path
from base64 import b64decode
from time import sleep

from magic import Magic

from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.rfid.VisitsLogger import VisitsLogger


__author__ = 'Ilia Novikov'


class ServerHandler(BaseHTTPRequestHandler):
    REQUESTS_LOG = 'logs/requests.log'

    def __init__(self, host, db: DatabaseConnector, serial: SerialConnector, stream_port=None, *args):
        self.routes = {
            '/': lambda: self.redirect('/home'),
            '/home': lambda: self.generate_home(),
            '/logs': lambda: self.generate_logs(),
            '/camera': lambda: self.generate_camera(),
            '/door': lambda: self.generate_door()
        }
        self.directories = {
            'root': 'www',
            'templates': 'www/templates/',
        }
        self.mimes = {
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.html': 'text/html',
            '.ico': 'image/x-icon',
            '.jpg': 'image/jpeg',
            '.woff2': 'application/font-woff2',
            '.woff': 'application/font-woff2',
            '.ttf': 'application/octet-stream',
            '.svg': 'image/svg+xml'
        }
        self.alerts = [
            {'type': 'warning', 'text': "Сервер находится в режиме тестирования", 'is_alert': True},
        ]
        self.logger = logging.getLogger()
        self.db = db
        self.host = host
        self.serial = serial
        self.stream_port = stream_port
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        url = self.path
        if url in self.routes:
            self.routes[url]()
            return
        if url.startswith('/include'):
            filename = self.directories['root'] + url
            self.send_file(filename)
            return
        self.generate_not_found()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Access to RFID server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def authorize(self, request=True):
        if not self.headers['Authorization']:
            if request:
                self.do_AUTHHEAD()
                self.generate_error("Авторизация прервана", code=0)
            return False
        else:
            user = self.get_user()
            if user:
                if not user.active:
                    if request:
                        self.generate_error("Пользователь был заблокирован", code=0)
                    return False
                return True
            else:
                if request:
                    self.do_AUTHHEAD()
                    self.generate_error("Неверный логин или пароль", code=0)
                return False

    def is_authorized(self):
        return self.authorize(request=False)

    def get_user(self):
        header = self.headers['Authorization']
        header = header[header.find(' '):]
        users = self.db.get_all_users()
        card, password = b64decode(bytes(header, 'utf-8')).decode('utf-8').split(':')
        user = [x for x in users if card in x.cards and x.check_password(password)]
        if len(user) == 0:
            return None
        return user[0]

    def redirect(self, url):
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

    def get_page_header(self):
        pattern = '<div class="alert alert-{}" role="alert">{}</div>'
        out = []
        for alert in self.alerts:
            text = '<strong>{}!</strong> {}'.format(alert['type'].title(), alert['text']) \
                if alert['is_alert'] else alert['text']
            out.append(pattern.format(alert['type'], text))
        return '\n'.join(out)

    def generate(self, name, title, body, code=200):
        template = self.directories['templates'] + name + '.html'
        base = self.directories['templates'] + 'base' + '.html'
        if not path.exists(template):
            pass
        with open(base) as base:
            with open(template) as file:
                if code:
                    self.send_response(code)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                html = base.read().format(self.get_page_header(), title, file.read())
                html = html.format(body)
                self.wfile.write(html.encode())

    def generate_error(self, message, code=200):
        self.generate('error', 'Ошибка сервера', message, code)

    def generate_logs(self):
        if not path.exists(VisitsLogger.VISITS_LOG):
            self.generate_error("Файл лога не найден")
            return
        with open(VisitsLogger.VISITS_LOG) as log:
            events = [x.strip() for x in log.readlines()[-20:]]
            view = ''.join(['<li class="list-group-item">{}</li>'.format(x) for x in events
                            if not x.startswith('----')])
            self.generate('logs', "Лог посещений", view)

    def generate_camera(self):
        if not self.stream_port:
            self.generate_error("Поддержка камеры была отключена")
        else:
            self.generate('camera', 'Камера', '{}:{}'.format(self.host, self.stream_port))

    def generate_not_found(self):
        self.generate_error("Ресурс не найден", code=404)

    def generate_door(self):
        if not self.authorize():
            return
        self.generate('secure/door', "Замок был открыт", '')
        self.serial.open()
        sleep(2)
        self.serial.standard()

    def send_file(self, filename):
        if path.exists(filename) and path.isfile(filename):
            extension = path.splitext(filename)[1]
            if extension in self.mimes:
                mime = self.mimes[extension]
            else:
                mime = Magic(mime=True).from_file(filename)
            self.send_response(200)
            self.send_header('Content-type', mime)
            self.end_headers()
            with open(filename, 'rb') as file:
                self.wfile.write(file.read())
        else:
            self.generate_not_found()

    def generate_home(self):
        if self.is_authorized():
            name = self.get_user().name
        else:
            name = "не авторизован"
        self.generate('home', "RFID сервер", name)

    def log_message(self, pattern, *args):
        with open(self.REQUESTS_LOG, 'a') as log:
            log.write(pattern % args + '\n')