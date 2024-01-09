from enum import Enum


class Event(str, Enum):
    CLICK = "CLICK"
    VIEW = "VIEW"
    VIEW_ALL = "VIEW_ALL"
    ADD_CREDIT = "ADD_CREDIT"
