# -*- coding: utf-8 -*-
import json
import logging
import sys
import time


class AppFormatter(logging.Formatter):
    """
    Класс AppFormatter.
    """  # noqa: E501

    def __init__(self, fmt=None, datefmt=None, style='%'):
        __tz = time.strftime('%z')
        if not fmt:
            fmt = "[%(asctime)s.%(msecs)03d" + __tz + "] %(levelname)s [ ] [%(name)s] %(message)s %(context)s"
        if not datefmt:
            datefmt = "%Y-%m-%dT%H:%M:%S"
        super(AppFormatter, self).__init__(fmt, datefmt, style)


class JsonFormatter(logging.Formatter):
    """
    Класс JsonFormatter.
    """  # noqa: E501

    def __init__(self, fmt=None, datefmt=None, style='%'):
        __tz = time.strftime('%z')
        if not fmt:
            fmt = json.dumps(dict({
                "message": "%(message)s", "level": "%(levelname)s", "channel": "%(name)s",
                "extra": [], "app_name": "app_main", "app_type": "python", "log_type": "code",
                "es_index_name": "python-main", "timestamp": "%(asctime)s.%(msecs)03d" + __tz,
                "context": "%(context)s"
            }))
        if not datefmt:
            datefmt = "%Y-%m-%dT%H:%M:%S"
        super(JsonFormatter, self).__init__(fmt, datefmt, style)


class StreamHandler(logging.StreamHandler):
    """
    Класс StreamHandler.
    """  # noqa: E501

    level = 0

    def __init__(self, stream=sys.stdout):
        super(StreamHandler, self).__init__(stream)
        self.setFormatter(JsonFormatter())


class AppHandler(logging.FileHandler):
    """
    Класс AppHandler.
    """  # noqa: E501

    level = 0

    def __init__(self, filename='app.log', mode='a', encoding='utf-8', delay=False):
        super(AppHandler, self).__init__(filename, mode, encoding, delay)
        self.setFormatter(JsonFormatter())


class AppLogger(logging.Logger):
    """
    Класс AppLogger.
    """  # noqa: E501

    def __init__(self, name, level='DEBUG'):
        super(AppLogger, self).__init__(name, level)
        self.addHandler(StreamHandler())
        self.addHandler(AppHandler())
