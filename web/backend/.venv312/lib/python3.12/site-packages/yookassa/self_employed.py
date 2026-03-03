# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common import HttpVerb
from yookassa.domain.request import SelfEmployedRequest
from yookassa.domain.response import SelfEmployedResponse


class SelfEmployed:
    """
    Класс, представляющий модель SelfEmployed.
    """  # noqa: E501

    base_path = '/self_employed'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def find_one(cls, self_employed_id):
        """
        Возвращает информацию о сомозанятом

        :param self_employed_id: Уникальный идентификатор сомозанятого
        :return: SelfEmployedResponse Объект ответа, возвращаемого API при запросе информации о сомозанятом
        """
        instance = cls()
        if not isinstance(self_employed_id, str) or not self_employed_id:
            raise ValueError('Invalid self_employed_id value')

        path = instance.base_path + '/' + self_employed_id
        response = instance.client.request(HttpVerb.GET, path)
        return SelfEmployedResponse(response)

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание сомозанятого

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: SelfEmployedResponse Объект ответа, возвращаемого API при запросе информации о сомозанятом
        """
        instance = cls()
        path = cls.base_path

        if not idempotency_key:
            idempotency_key = uuid.uuid4()

        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = SelfEmployedRequest(params)
        elif isinstance(params, SelfEmployedRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return SelfEmployedResponse(response)
