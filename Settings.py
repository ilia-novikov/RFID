from configparser import ConfigParser
from os.path import exists


__author__ = 'novikov'


class Settings:
    FILENAME = 'config.ini'

    _DB_SECTION = 'db'
    DB_HOST = 'db_host'
    DB_PORT = 'db_port'
    DB_USER = 'db_user'
    DB_PASSWORD = 'db_password'
    DB_NAME = 'db_name'
    DB_COLLECTION = 'db_collection'

    def __init__(self):
        self.is_first_run = not exists(self.FILENAME)
        self.settings = ConfigParser()

    def load(self):
        self.settings.read(self.FILENAME)

    def save(self):
        with open(self.FILENAME, 'w') as writer:
            self.settings.write(writer)

    def get_db_option(self, option):
        return self.settings.get(self._DB_SECTION, option, fallback=None)

    def set_db_option(self, option, value):
        if self._DB_SECTION not in self.settings:
            self.settings.add_section(self._DB_SECTION)
        self.settings.set(self._DB_SECTION, option, value)