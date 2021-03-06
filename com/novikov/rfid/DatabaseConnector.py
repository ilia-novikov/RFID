import logging

from pymongo import MongoClient

from com.novikov.rfid.AccessLevel import AccessLevel
from com.novikov.rfid.UserModel import UserModel


__author__ = 'Ilia Novikov'


class DatabaseConnector:
    def __init__(self, hostname, port, database, collection, credentials=None):
        self.logger = logging.getLogger()
        self.logger.info("Подключение к БД на {}:{}".format(hostname, port))
        self.__client = MongoClient(hostname, port)
        self.__db = self.__client[database]
        if credentials:
            self.logger.info("Использован механизм авторизации логин-пароль")
            self.__db.authenticate(credentials['user'], credentials['password'])
        self.logger.info("Выбрана коллекция {}".format(collection))
        self.__collection = self.__db[collection]
        self.migrate()

    def migrate(self):
        for item in self.__collection.find():
            if 'ID' in item:
                card_id = item['ID']
                self.__collection.update({'ID': card_id},
                                         {'$set': {UserModel.CARDS: [card_id]},
                                          '$unset': {'ID': True}})

    def has_any_developer(self):
        return self.__collection.find({UserModel.ACCESS: AccessLevel.developer.value}).count() != 0

    @staticmethod
    def add_db_admin(hostname, port, database, credentials):
        logging.getLogger().info("Создание администратора БД")
        client = MongoClient(hostname, port)
        db = client[database]
        db.add_user(credentials['user'], credentials['password'])
        client.close()

    def has_users(self):
        return self.__collection.count() > 0

    def add_user(self, user: UserModel):
        self.logger.info(
            "{} добавляет пользователя {} с правами доступа '{}'".format(
                user.creator,
                user.name,
                str(user.access)))
        result = self.__collection.save(user.get_model())
        self.logger.info("Результат операции: {}".format(result))

    def get_user(self, card_id):
        self.logger.info("Поиск пользователя с ID {}".format(card_id))
        user = self.__collection.find_one({UserModel.CARDS: card_id})
        if user:
            self.logger.info("Пользователь найден")
            return UserModel(model=user)
        else:
            self.logger.info("Пользователь не найден")
            return None

    def remove_user(self, user: UserModel, operator: str):
        self.logger.info("{} удаляет пользователя {} с правами доступа '{}'".format(
            operator,
            user.name,
            str(user.access)))
        result = self.__collection.remove(user.get_model())
        self.logger.info("Результат операции: {}".format(result))

    def update_user(self, user: UserModel):
        self.logger.info(
            "Изменение пользователя {} с правами {}".format(
                user.name,
                str(user.access)))
        result = self.__collection.update({UserModel.CARDS: {'$in': user.cards}}, user.get_model())
        self.logger.info("Результат операции: {}".format(result))

    def get_all_users(self):
        return [UserModel(model=x) for x in self.__collection.find()]

    def drop_collection(self):
        self.__collection.drop()

    def drop_db_user(self, user):
        self.__db.remove_user(user)