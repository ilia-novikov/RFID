from configparser import ConfigParser
from os.path import exists


__author__ = 'novikov'


class Settings:
    FILENAME = 'config.ini'

    __DB_SECTION = 'db'
    DB_HOST = 'db_host'
    DB_PORT = 'db_port'
    DB_USER = 'db_user'
    DB_PASSWORD = 'db_password'
    DB_NAME = 'db_name'
    DB_COLLECTION = 'db_collection'

    __DELAY_SECTION = 'time'
    DELAY_ERROR = 'delay_error'
    DELAY_SUCCESS = 'delay_success'

    def __init__(self):
        self.is_first_run = not exists(self.FILENAME)
        self.settings = ConfigParser()
        if not self.is_first_run:
            self.load()

    def load(self):
        self.settings.read(self.FILENAME)

    def save(self):
        with open(self.FILENAME, 'w') as writer:
            self.settings.write(writer)

    def __set_option(self, section, option, value):
        if section not in self.settings:
            self.settings.add_section(section)
        self.settings.set(section, option, value)

    def get_db_option(self, option):
        return self.settings.get(self.__DB_SECTION, option, fallback=None)

    def set_db_option(self, option, value):
        self.__set_option(self.__DB_SECTION, option, value)

    def get_delay_option(self, option):
        return int(self.settings.get(self.__DELAY_SECTION, option, fallback=0))

    def set_delay_option(self, option, value):
        self.__set_option(self.__DELAY_SECTION, option, value)