# -*- coding: utf-8 -*-


class HttpVerb(object):
    """
    Константы, представляющие глаголы http-метода. Возможные значения:

    * yookassa.domain.common.HttpVerb.GET
    * yookassa.domain.common.HttpVerb.POST
    * yookassa.domain.common.HttpVerb.PUT
    * yookassa.domain.common.HttpVerb.PATCH
    * yookassa.domain.common.HttpVerb.HEAD
    * yookassa.domain.common.HttpVerb.OPTIONS
    * yookassa.domain.common.HttpVerb.DELETE
    """  # noqa: E501

    """
    Список допустимых значений
    """
    GET = 'get'
    """Используется для получения данных от сервера"""
    POST = 'post'
    """Используется для отправки данных на сервер"""
    PUT = 'put'
    """Используется для обновление ресурса"""
    PATCH = 'patch'
    """Используется для частичного обновления ресурса"""
    HEAD = 'head'
    """Используется для получения только заголовков"""
    OPTIONS = 'options'
    """Используется для запроса информации об опциях соединения, доступных в цепочке запросов и ответов"""
    DELETE = 'delete'
    """Используется для удаление ресурса"""
