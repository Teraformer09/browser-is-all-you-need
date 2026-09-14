import copy
import json
import re
import xml.etree.ElementTree as ET


class Unassessable(Exception):
    pass


def require(value, reason):
    if not value:
        raise Unassessable(reason)
