from enum import Enum

__author__ = 'Ilia Novikov'


class AccessLevel(Enum):
    guest = 0
    common = 1
    privileged = 2
    administrator = 3
    developer = 4

    def __str__(self):
        return ["Guest", "Common user", "Privileged user", "Administrator", "Developer"][self.value]