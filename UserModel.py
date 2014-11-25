from datetime import datetime
from hashlib import sha256

__author__ = 'novikov'


class UserModel:
    COLLECTION = "RLAB"

    GUEST = 0
    COMMON = 1
    PRIVILEGED = 2
    DEVELOPER = 3

    LEVELS = ["Guest", "Common user", "Privileged user", "Developer"]

    ID = "ID"
    NAME = "NAME"
    ACCESS = "ACCESS"
    EXPIRE = "EXPIRE"
    CREATOR = "CREATOR"
    HASH = "HASH"

    def __init__(self, model=None, creator=None, card_id=None, name=None, access=COMMON, expire=datetime(2050, 1, 1)):
        if model:
            self.creator = model[self.CREATOR]
            self.id = model[self.ID]
            self.name = model[self.NAME]
            self.access = model[self.ACCESS]
            self.expire = model[self.EXPIRE]
            self._hash = model[self.HASH]
        else:
            self.creator = creator
            self.id = card_id
            self.name = name
            self.access = access
            self.expire = expire
            self._hash = None
        return

    @staticmethod
    def __get_hash(password):
        salt = 'q6GP9x%ijrG^5O77S=mrICu1irAfTEULt3YOMvJ-bhs9^OPO9cK9QoDr40%R'
        return sha256((salt + password).encode('utf8')).hexdigest()

    def check_password(self, password):
        return self.__get_hash(password) == self._hash

    def update_password(self, password):
        self._hash = self.__get_hash(password)

    def has_password(self):
        return self._hash is not None

    def get_model(self):
        return {
            self.CREATOR: self.creator,
            self.ID: self.id,
            self.NAME: self.name,
            self.ACCESS: self.access,
            self.EXPIRE: self.expire,
            self.HASH: self._hash
        }

    def get_access(self):
        return self.LEVELS[self.access]