# -*- coding: utf-8 -*-
import platform
import sys

import distro

import yookassa


class UserAgent:
    """
    Класс для создания заголовка User-Agent в запросах к API
    """  # noqa: E501
    VERSION_DELIMITER = '/'
    """Разделитель части заголовка и её версии"""
    PART_DELIMITER = ' '
    """Разделитель между частями заголовка"""

    __os = None
    """Версия операционной системы"""
    __python = None
    """Версия Python"""
    __framework = None
    """Версия фреймворка"""
    __cms = None
    """Версия CMS"""
    __module = None
    """Версия модуля"""
    __sdk = None
    """Версия SDK"""

    def __init__(self):
        self.os = self.define_os()
        self.python = self.define_python()
        self.sdk = self.define_sdk()

    def define_os(self):
        """Определение системы."""
        simple = self.__define_simple_os()
        if simple.name == 'Windows':
            return Version(simple.name, simple.version)
        elif simple.name == 'Linux':
            smart = self.__define_linux_os()
            return Version(smart.name.capitalize(), smart.version)
        else:
            return Version(simple.name, simple.version)

    @staticmethod
    def define_python():
        """Определение версии PHP"""
        info = sys.version_info
        version = str(info.major) + '.' + str(info.minor) + '.' + str(info.micro)
        return Version('Python', version)

    @staticmethod
    def define_sdk():
        """Определение версии SDK"""
        version = yookassa.__version__
        return Version('YooKassa.Python', version)

    @property
    def os(self):
        """Возвращает версию операционной системы."""
        return self.__os

    @os.setter
    def os(self, value):
        """Устанавливает версию операционной системы."""
        self.__os = str(value)

    @property
    def python(self):
        """Возвращает версию Python."""
        return self.__python

    @python.setter
    def python(self, value):
        """Устанавливает версию Python."""
        self.__python = str(value)

    @property
    def framework(self):
        """Возвращает версию фреймворка."""
        return self.__framework

    @framework.setter
    def framework(self, value):
        """Устанавливает версию фреймворка."""
        self.__framework = str(value)

    @property
    def cms(self):
        """Возвращает версию CMS."""
        return self.__cms

    @cms.setter
    def cms(self, value):
        """Устанавливает версию CMS."""
        self.__cms = str(value)

    @property
    def module(self):
        """Возвращает версию модуля."""
        return self.__module

    @module.setter
    def module(self, value):
        """Устанавливает версию модуля."""
        self.__module = str(value)

    @property
    def sdk(self):
        """Возвращает версию SDK."""
        return self.__sdk

    @sdk.setter
    def sdk(self, value):
        """Устанавливает версию SDK."""
        self.__sdk = str(value)

    def set_framework(self, name, version):
        """
        Устанавливает версию фреймворка.

        :param name: Назание фреймворка
        :param version: Версия фреймворка
        :return: UserAgent
        """
        self.framework = Version(name, version)
        return self

    def set_cms(self, name, version):
        """
        Устанавливает версию CMS.

        :param name: Назание CMS
        :param version: Версия CMS
        :return: UserAgent
        """
        self.cms = Version(name, version)
        return self

    def set_module(self, name, version):
        """
        Устанавливает версию модуля.

        :param name: Назание модуля
        :param version: Версия модуля
        :return: UserAgent
        """
        self.module = Version(name, version)
        return self

    def get_header_string(self):
        """
        Возвращает значения header в виде строки
        :return: str
        """
        headers = [str(self.os), str(self.python)]
        if self.framework is not None:
            headers.append(str(self.framework))
        if self.cms is not None:
            headers.append(str(self.cms))
        if self.module is not None:
            headers.append(str(self.module))
        headers.append(str(self.sdk))

        return self.PART_DELIMITER.join(headers)

    @staticmethod
    def __define_simple_os():
        """Определение данных системы для Windows."""
        return Version(platform.system(), platform.release())

    @staticmethod
    def __define_linux_os():
        """Определение данных системы для Linux."""
        return Version(distro.name(), distro.version())

    @staticmethod
    def create_version(name, version):
        """
        Создание строки версии компонента.
        :param name: Название компонента
        :param version: Версия компонента
        :return: str
        """
        strip_data = ' ' + UserAgent.PART_DELIMITER + UserAgent.VERSION_DELIMITER
        return name.strip(strip_data).replace(UserAgent.PART_DELIMITER, '.').replace(UserAgent.VERSION_DELIMITER, '.') \
            + UserAgent.VERSION_DELIMITER \
            + version.strip(strip_data).replace(UserAgent.PART_DELIMITER, '.').replace(UserAgent.VERSION_DELIMITER, '.')


class Version:
    """
    Класс для создания версии компонента
    """  # noqa: E501

    __name = None
    """Название компонента"""
    __version = None
    """Версия компонента"""

    def __init__(self, name, version):
        self.name = name
        self.version = version

    @property
    def name(self):
        """Устанавливает имя"""
        return self.__name

    @name.setter
    def name(self, value):
        """Возвращает имя"""
        self.__name = str(value)

    @property
    def version(self):
        """Возвращает версию"""
        return self.__version

    @version.setter
    def version(self, value):
        """Возвращает версию"""
        self.__version = str(value)

    def __str__(self):
        return UserAgent.create_version(self.name, self.version)
