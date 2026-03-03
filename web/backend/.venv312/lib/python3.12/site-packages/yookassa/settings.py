# -*- coding: utf-8 -*-
from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.models import Me


class Settings:
    """
    Класс, представляющий модель Settings.
    """  # noqa: E501

    base_path = '/me'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def get_account_settings(cls, params=None):
        """
        Возвращает информацию о магазине

        :param params: (dict | None) Параметры поиска.
            В настоящее время доступен только {'on_behalf_of': account_id}
        :return: Me Информация о настройках магазина или шлюза
        """
        instance = cls()
        path = cls.base_path

        response = instance.client.request(HttpVerb.GET, path, params)
        return Me(response)
