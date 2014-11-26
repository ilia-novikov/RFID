import logging

from pymongo import MongoClient

from com.novikov.rfid.UserModel import UserModel


__author__ = 'novikov'


class Connector:
    def __init__(self, hostname, port, database, collection, credentials=None):
        logging.info("Подключение к БД на {}:{}".format(hostname, port))
        self.__client = MongoClient(hostname, port)
        self.__db = self.__client[database]
        if credentials:
            logging.info("Использован механизм авторизации логин-пароль")
            self.__db.authenticate(credentials['user'], credentials['password'])
        logging.info("Выбрана коллекция {}".format(collection))
        self.__collection = self.__db[collection]

    def has_users(self):
        return self.__collection.count() > 0

    def add_user(self, user: UserModel):
        logging.info(
            "{} добавляет пользователя {} с правами доступа '{}'".format(
                user.creator,
                user.name,
                str(user.access)))
        result = self.__collection.save(user.get_model())
        logging.info("Результат операции: {}".format(result))

    def get_user(self, card_id):
        logging.info("Поиск пользователя с ID {}".format(card_id))
        user = self.__collection.find_one({UserModel.ID: card_id})
        if user:
            logging.info("Пользователь найден")
            return UserModel(model=user)
        else:
            logging.info("Пользователь не найден")
            return None

    def remove_user(self, user: UserModel, operator: str):
        logging.info("{} удаляет пользователя {} с правами доступа '{}'".format(
            operator,
            user.name,
            str(user.access)))
        result = self.__collection.remove(user.get_model())
        logging.info("Результат операции: {}".format(result))

    def update_user(self, user: UserModel):
        logging.info(
            "Изменение пользователя {} с правами {}".format(
                user.name,
                str(user.access)))
        result = self.__collection.update({UserModel.ID: user.id}, user.get_model())
        logging.info("Результат операции: {}".format(result))

    def get_all_users(self):
        return [UserModel(model=x) for x in self.__collection.find()]