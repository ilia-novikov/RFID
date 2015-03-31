from datetime import datetime
from fnmatch import fnmatch
from http.server import BaseHTTPRequestHandler
import json
import logging
from os import path
from base64 import b64decode
from string import Template
from time import sleep
from urllib.parse import urlparse, parse_qs

from magic import Magic
from bs4 import BeautifulSoup, Comment

from com.novikov.rfid.AccessLevel import AccessLevel
from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.rfid.VisitsLogger import VisitsLogger


__author__ = 'Ilia Novikov'


class ServerHandler(BaseHTTPRequestHandler):
    REQUESTS_LOG = 'logs/requests.log'

    def __init__(self, debug, host, db: DatabaseConnector, serial: SerialConnector, stream_port=None, *args):
        self.routes = {
            '/': lambda: self.redirect('/home'),
            '/home': lambda: self.generate_home(),
            '/logs': lambda: self.generate_logs(),
            '/camera': lambda: self.generate_camera(),
            '/door': lambda: self.generate_door(),
            '/control': lambda: self.generate_control_panel(),
            '/control/*': lambda: self.handle_control(),
            '/request/*': lambda: self.handle_ajax(),
        }
        self.directories = {
            'root': 'www',
            'templates': 'www/templates/',
            'include': 'www/include'
        }
        self.includes = ['/css/', '/img/', '/fonts/', '/js/']
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
        self.alerts = []
        self.debug = debug
        if self.debug:
            self.alerts.append({'type': 'warning', 'text': "Сервер находится в режиме тестирования", 'is_alert': True})
        self.logger = logging.getLogger()
        self.db = db
        self.host = host
        self.serial = serial
        self.stream_port = stream_port
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        url = urlparse(self.path).path
        for key in self.routes.keys():
            if fnmatch(url, key):
                self.routes[key]()
                return
        for include in self.includes:
            if str(url).startswith(include):
                filename = self.directories['include'] + url
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

    def get_alerts(self):
        pattern = '<div class="alert alert-{}" role="alert">{}</div>'
        out = []
        for alert in self.alerts:
            text = '<strong>{}!</strong> {}'.format(alert['type'].title(), alert['text']) \
                if alert['is_alert'] else alert['text']
            out.append(pattern.format(alert['type'], text))
        return '\n'.join(out)

    @staticmethod
    def include_css(items):
        out = []
        pattern = '<link rel="stylesheet" href="/css/{}.css">'
        for item in items:
            out.append(pattern.format(item))
        return ''.join(out)

    @staticmethod
    def include_js(items):
        out = []
        pattern = '<script src="/js/{}.js"></script>'
        for item in items:
            out.append(pattern.format(item))
        return ''.join(out)

    @staticmethod
    def include_meta(items):
        out = []
        pattern = Template('<meta name="$name" content="$content">')
        for item in items:
            out.append(pattern.safe_substitute(item))
        return ''.join(out)

    def generate(self, name, title, body=None, code=200):
        template = self.directories['templates'] + name + '.html'
        base = self.directories['templates'] + 'base' + '.html'
        if not path.exists(template):
            pass
        with open(base) as base:
            with open(template) as file:
                html = Template(base.read())
                content = file.read()
                soup = BeautifulSoup(content)
                comments = soup.findAll(text=lambda text: isinstance(text, Comment))
                css = ''
                js = ''
                meta = ''
                if comments:
                    command = json.loads(comments[0].strip())
                    if 'css' in command:
                        css = self.include_css(command['css'])
                    if 'js' in command:
                        js = self.include_js(command['js'])
                    if 'meta' in command:
                        meta = self.include_meta(command['meta'])
                    if 'in_develop' in command and not self.debug:
                        self.generate_error("Страница находится в разработке")
                        return
                html = html.safe_substitute({
                    'meta': meta,
                    'css': css,
                    'js': js,
                    'alerts': self.get_alerts(),
                    'header': title,
                    'content': content
                })
                if body:
                    html = Template(html).safe_substitute(body)
                self.send_response(code)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())

    def generate_error(self, message, code=200):
        self.generate('error', 'Ошибка сервера', {'message': message}, code)

    def generate_logs(self):
        if not path.exists(VisitsLogger.VISITS_LOG):
            self.generate_error("Файл лога не найден")
            return
        with open(VisitsLogger.VISITS_LOG) as log:
            events = [x.strip() for x in log.readlines()[-20:]]
            items = ''.join(['<li class="list-group-item">{}</li>'.format(x) for x in events
                             if not x.startswith('----')])
            self.generate('logs', "Лог посещений", {'items': items})

    def generate_camera(self):
        if not self.stream_port:
            self.generate_error("Поддержка камеры была отключена")
        else:
            source = '{}:{}'.format(self.host, self.stream_port)
            self.generate('camera', 'Камера', {'source': source})

    def generate_not_found(self):
        self.generate_error("Ресурс не найден", code=404)

    def generate_door(self):
        if not self.authorize():
            return
        self.generate('secure/door', "Дверь была открыта")
        self.serial.open()
        sleep(2)
        self.serial.standard()

    def generate_control_panel(self):
        if not self.authorize():
            return
        user = self.get_user()
        if user.access.value < AccessLevel.privileged.value:
            self.generate_error("Недостаточный уровень доступа")
            return
        pattern = '<a class="btn btn-default btn-menu" href="{}" role="button">{}</a> <br>'
        choices = [{'text': "Добавление гостя", 'action': 'add-guest'}]
        if user.access.value >= AccessLevel.administrator.value:
            choices.extend([
                {'text': "Добавление пользователя", 'action': 'add-user'},
                {'text': "Редактирование пользователей", 'action': 'edit-users'},
                {'text': "Просмотр системного лога", 'action': 'application-log'},
                {'text': "Очистка лога посещений", 'action': 'clear-visits'}])
        if user.access == AccessLevel.developer:
            choices.extend([{'text': "Просмотр ночного лога", 'action': 'illegal-log'}])
        actions = ''.join([pattern.format('/control/' + choice['action'], choice['text']) for choice in choices])
        self.generate('secure/panel', "Панель управления", {'actions': actions})

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
            name = '{} ({})'.format(self.get_user().name, self.get_user().access)
        else:
            name = "не авторизован"
        self.generate('home', "RFID сервер", {'name': name})

    def log_message(self, pattern, *args):
        client = list(self.request.getpeername())[0]
        time = datetime.now().strftime('%a, %d %B %Y, %H:%M:%S')
        message = "{} from {} :: {}".format(time, client, pattern % args)
        with open(self.REQUESTS_LOG, 'a') as log:
            log.write(message + '\n')

    def control_add_user(self):
        if not self.authorize():
            return
        user = self.get_user()
        if user.access.value < AccessLevel.privileged.value:
            self.generate_error("Недостаточный уровень доступа")
            return
        access = [str(AccessLevel.guest)]
        if user.access.value >= AccessLevel.administrator.value:
            access.extend([str(AccessLevel.common), str(AccessLevel.privileged), str(AccessLevel.administrator)])
        pattern = '<option>{}</option>'
        choices = ''.join([pattern.format(x) for x in access])
        self.generate('secure/control/add-user', "Добавление пользователя", {'access': choices})

    def handle_ajax(self):
        url = urlparse(self.path).path.split('/')[-1:][0]
        routes = {
            'test': lambda: self.wfile.write(json.dumps({'success': 'OK'}).encode()),
            'validate': lambda: self.validate_card()
        }
        if url in routes:
            routes[url]()
        else:
            self.wfile.write(json.dumps({'error': 'not_found'}).encode())

    def validate_card(self):
        card = parse_qs(urlparse(self.path).query)['card'][0]
        self.wfile.write(json.dumps({
            'success': True,
            'is_valid': not self.db.get_user(card)
        }).encode())

    def handle_control(self):
        url = urlparse(self.path).path.split('/')[-1:][0]
        routes = {
            'add-user': lambda: self.control_add_user()
        }
        if url in routes:
            routes[url]()
        else:
            self.generate_not_found()