from http.server import BaseHTTPRequestHandler

__author__ = 'ilia'


class RedirectionHandler(BaseHTTPRequestHandler):
    url = ''

    def do_GET(self):
        self.send_response(301)
        self.send_header("Location", self.url)
        self.end_headers()

    def log_message(self, pattern, *args):
        pass