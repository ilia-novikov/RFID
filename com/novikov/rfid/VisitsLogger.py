from datetime import datetime

from com.novikov.rfid.UserModel import UserModel
from com.novikov.rfid import __version__

__author__ = 'novikov'


class VisitsLogger:
    FILENAME = ''

    def __init__(self):
        self.__append("Приложение запущено, версия: {}".format(__version__))

    @staticmethod
    def __get_datetime():
        return datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: ')

    def __append(self, message):
        with open(self.FILENAME, mode='a') as visits:
            visits.write(self.__get_datetime() + message)

    def visit(self, user: UserModel):
        self.__append("Вошел {} ({}) \n".format(
            user.name,
            str(user.access)))

    def wrong_password(self, user: UserModel):
        self.__append("Неверный ввод пароля к аккаунту {} ({}) \n".format(
            user.name,
            str(user.access)))

    def wrong_id(self, card_id: str):
        self.__append("Неверный ID карты: {} \n".format(
            card_id))

    def wrong_access(self, user: UserModel):
        self.__append("Попытка разблокировки с низким уровнем прав: {} ({}) \n".format(
            user.name,
            str(user.access)))