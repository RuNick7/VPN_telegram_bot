# -*- coding: utf-8 -*-


class Context(object):
    """
    Базовый контекстный класс.
    """  # noqa: E501

    def __init__(self, contexts):
        self.__contexts = contexts

    def get_context_data(self, context):
        """
        Возвращает контекстные данные

        :param context: mixed
        :return: mixed
        """
        if context in self.__contexts:
            return getattr(self, context)
