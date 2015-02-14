from datetime import datetime
from hashlib import sha256

from com.novikov.rfid.AccessLevel import AccessLevel


__author__ = 'Ilia Novikov'


class UserModel:
    CARDS = "CARDS"
    NAME = "NAME"
    ACCESS = "ACCESS"
    EXPIRE = "EXPIRE"
    CREATOR = "CREATOR"
    HASH = "HASH"
    ACTIVE = "ACTIVE"

    def __init__(self, model=None, creator=None, cards=[], name=None, access=AccessLevel.common,
                 expire=datetime(2020, 1, 1), active=True):
        if model:
            self.creator = model[self.CREATOR]
            self.cards = model[self.CARDS]
            self.name = model[self.NAME]
            self.access = AccessLevel(int(model[self.ACCESS]))
            self.expire = model[self.EXPIRE]
            self.__hash = model[self.HASH]
            self.active = model[self.ACTIVE]
        else:
            self.creator = creator
            self.cards = cards
            self.name = name
            self.access = access
            self.expire = expire
            self.__hash = None
            self.active = active
        return

    def __get_hash(self, password):
        salt = 'q6GP9x%ijrG^5O77S=mrICu1irAfTEULt3YOMvJ-bhs9^OPO9cK9QoDr40%R'
        return sha256((salt + password + self.name + salt).encode('utf8')).hexdigest()

    def check_password(self, password):
        return self.__get_hash(password) == self.__hash

    def update_password(self, password):
        self.__hash = self.__get_hash(password)

    def reset_password(self):
        self.__hash = None

    def has_password(self):
        return self.__hash is not None

    def get_model(self):
        return {
            self.CREATOR: self.creator,
            self.CARDS: self.cards,
            self.NAME: self.name,
            self.ACCESS: self.access.value,
            self.EXPIRE: self.expire,
            self.HASH: self.__hash,
            self.ACTIVE: self.active
        }