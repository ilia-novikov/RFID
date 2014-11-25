import logging

from pymongo import MongoClient

from UserModel import UserModel


__author__ = 'novikov'


class Connector:
    DATABASE = 'users'

    def __init__(self, hostname='localhost', port=27017):
        logging.info("Подключение к БД на {}:{}".format(hostname, port))
        self.client = MongoClient(hostname, port)
        self.db = self.client[self.DATABASE]
        logging.info("Выбрана коллекция {}".format(UserModel.COLLECTION))
        self.collection = self.db[UserModel.COLLECTION]

    def add_user(self, user: UserModel):
        logging.info(
            "{} добавляет пользователя {} с правами доступа '{}'".format(
                user.creator,
                user.name, user.get_access()))
        result = self.collection.save(user.get_model())
        logging.info("Результат операции: {}".format(result))

    def get_user(self, card_id):
        logging.info("Поиск пользователя с ID {}".format(card_id))
        user = self.collection.find_one({UserModel.ID: card_id})
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
            user.get_access()))
        result = self.collection.remove(user.get_model())
        logging.info("Результат операции: {}".format(result))

    def update_user(self, user: UserModel):
        logging.info(
            "Изменение пользователя {} с правами {}".format(
                user.name,
                user.get_access()))
        result = self.collection.update({UserModel.ID: user.id}, user.get_model())
        logging.info("Результат операции: {}".format(result))