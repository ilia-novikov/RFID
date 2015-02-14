from datetime import datetime

from com.novikov.rfid.UserModel import UserModel
from com.novikov.rfid import __version__

__author__ = 'Ilia Novikov'


class VisitsLogger:
    VISITS_LOG = 'visits.log'
    ILLEGAL_LOG = 'illegal.log'

    def __init__(self):
        with open(self.VISITS_LOG, mode='a') as log:
            log.write('-------------------------------------------------- \n')
        self.__append("Приложение запущено, версия: {} \n".format(__version__))

    @staticmethod
    def __get_datetime():
        return datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: ')

    @staticmethod
    def __is_legal():
        return 8 < datetime.now().hour < 22

    def __append(self, message):
        if self.__is_legal():
            with open(self.VISITS_LOG, mode='a') as visits:
                visits.write(self.__get_datetime() + message)
        else:
            with open(self.ILLEGAL_LOG, mode='a') as illegal:
                illegal.write(self.__get_datetime() + message)

    def visit(self, user: UserModel):
        base = "Вошел {}".format(user.name)
        self.__append("{} ({}) \n".format(
            base,
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

    def inactive_card(self, user: UserModel):
        self.__append("Попытка разблокировки с заблокированной картой: {} ({}) \n".format(
            user.name,
            str(user.access)))

    def expired(self, user: UserModel):
        self.__append("Попытка разблокировки с устаревшей картой: {} ({}) \n".format(
            user.name,
            str(user.access)))

    def exit(self, user: UserModel):
        self.__append("Разработчик завершил выполнение программы: {} \n".format(
            user.name))