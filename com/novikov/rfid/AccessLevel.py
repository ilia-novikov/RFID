from enum import Enum

__author__ = 'novikov'


class AccessLevel(Enum):
    guest = 0
    common = 1
    privileged = 2
    developer = 3

    def __str__(self):
        return ["Guest", "Common user", "Privileged user", "Developer"][self.value]