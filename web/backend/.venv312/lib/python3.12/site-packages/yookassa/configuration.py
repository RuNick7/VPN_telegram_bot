# -*- coding: utf-8 -*-
import logging

from yookassa.domain.common.user_agent import Version
from yookassa.logging.adapter import Adapter


class ConfigurationError(Exception):
    """
    Ошибка конфигурации запроса. Не установлены параметры авторизации.
    """  # noqa: E501
    pass


class Configuration(object):
    """
    Класс для загрузки конфига API клиента.
    """  # noqa: E501

    api_url = "https://api.yookassa.ru/v3"
    """Базовый URL для API Кассы."""
    account_id = None
    """Идентификатор магазина"""
    secret_key = None
    """Секретный ключ."""
    timeout = 1800
    """Время через которое будут осуществляться повторные запросы."""
    max_attempts = 3
    """Количество повторных запросов при ответе API статусом 202."""
    auth_token = None
    """OAuth токен."""
    logger = None
    """Объект для логирования запросов."""
    agent_framework = None
    """Версия фреймворка."""
    agent_cms = None
    """Версия CMS."""
    agent_module = None
    """Версия модуля."""
    verify = None
    """Проверка сертификата (bool)."""

    def __init__(self, **kwargs):
        self.assert_has_api_credentials()

    @staticmethod
    def configure(account_id, secret_key, logger=None, **kwargs):
        """
        Устанавливает настройки конфигурации для базовой авторизации.

        :param account_id: Идентификатор магазина.
        :param secret_key: Секретный ключ.
        :param logger: Объект для логирования запросов.
        :param kwargs: Словарь с дополнительными параметрами.
        """
        Configuration.account_id = account_id
        Configuration.secret_key = secret_key
        Configuration.auth_token = None
        Configuration.configure_logger(logger)
        Configuration.api_url = kwargs.get("api_url", "https://api.yookassa.ru/v3")
        Configuration.timeout = kwargs.get("timeout", 1800)
        Configuration.max_attempts = kwargs.get("max_attempts", 3)
        Configuration.verify = kwargs.get("verify", None)

    @staticmethod
    def configure_auth_token(token, logger=None, **kwargs):
        """
        Устанавливает настройки конфигурации для авторизации по OAuth.

        :param token: OAuth токен.
        :param logger: Объект для логирования запросов.
        :param kwargs: Словарь с дополнительными параметрами.
        """
        Configuration.account_id = None
        Configuration.secret_key = None
        Configuration.auth_token = token
        Configuration.configure_logger(logger)
        Configuration.api_url = kwargs.get("api_url", "https://api.yookassa.ru/v3")
        Configuration.timeout = kwargs.get("timeout", 1800)
        Configuration.max_attempts = kwargs.get("max_attempts", 3)
        Configuration.verify = kwargs.get("verify", None)

    @staticmethod
    def configure_logger(logger):
        """
        Устанавливает настройки конфигурации для логирования.

        :param logger: Объект для логирования запросов.
        """
        if isinstance(logger, logging.Logger):
            Configuration.logger = Adapter(logger, {"context": {}})

    @staticmethod
    def configure_user_agent(framework=None, cms=None, module=None):
        """
        Устанавливает настройки конфигурации для User-Agent.

        :param framework: Версия фреймворка.
        :param cms: Версия CMS.
        :param module: Версия модуля.
        """
        if isinstance(framework, Version):
            Configuration.agent_framework = framework
        if isinstance(cms, Version):
            Configuration.agent_cms = cms
        if isinstance(module, Version):
            Configuration.agent_module = module

    @staticmethod
    def instantiate():
        """
        Получение объекта конфигурации.

        :return: Configuration
        """
        return Configuration(
            shop_id=Configuration.account_id,
            shop_password=Configuration.secret_key,
            timeout=Configuration.timeout,
            max_attempts=Configuration.max_attempts,
            auth_token=Configuration.auth_token,
            agent_framework=Configuration.agent_framework,
            agent_cms=Configuration.agent_cms,
            agent_module=Configuration.agent_module,
            logger=Configuration.logger,
            api_url=Configuration.api_url,
            verify=Configuration.verify
        )

    @staticmethod
    def api_endpoint():
        """
        Получение объекта конфигурации базового URL для API Кассы.

        :return: str
        """
        return Configuration.api_url

    def has_api_credentials(self):
        """
        Установлены ли параметры для базовой авторизации.

        :return: bool
        """
        return self.account_id is not None and self.secret_key is not None

    def assert_has_api_credentials(self):
        """
        Установлены ли параметры для базовой авторизации или авторизации по OAuth.
        Если параметры не установлены, то будет вызвано исключение ConfigurationError
        """
        if self.auth_token is None and not self.has_api_credentials():
            raise ConfigurationError("account_id and secret_key are required")
        elif self.auth_token and self.has_api_credentials():
            raise ConfigurationError("Could not configure authorization with auth_token and basic auth")
