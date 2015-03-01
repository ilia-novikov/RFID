from http.server import BaseHTTPRequestHandler
import logging
from os import path
from base64 import b64decode

from magic import Magic


__author__ = 'Ilia Novikov'


class ServerHandler(BaseHTTPRequestHandler):
    directories = {
        'root': 'www',
        'secure': 'www/secure/',
        'templates': 'www/templates/',
        'pages': 'www/pages/',
        'include': 'www/include/'
    }

    routes = {
        '/home': directories['pages'] + 'home.html',
        '/test': directories['secure'] + 'test.jpg'
    }

    redirection = {
        '/': '/home'
    }

    exclusions = [
        directories['include']
    ]

    db = None
    logger = logging.getLogger()

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

    def generate(self, name, title, body):
        template = self.directories['templates'] + name + '.html'
        base = self.directories['templates'] + 'base' + '.html'
        if not path.exists(template):
            pass
        with open(base) as base:
            with open(template) as file:
                html = base.read().format(title, file.read())
                html = html.format(body)
                self.wfile.write(html.encode())

    def generate_error(self, message):
        self.generate('error', 'RFID', message)

    def not_found(self):
        self.generate_error("файл не найден")

    def redirect(self, url):
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

    def route(self, url):
        filename = self.routes[url]
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
        url = self.path
        if url in self.redirection:
            self.redirect(self.redirection[url])
            return
        if url in self.routes:
            self.route(url)
        if url.startswith('/include'):
            filename = self.directories['root'] + url
            self.send_file(filename)

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Access to RFID server"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()