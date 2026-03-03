# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.request.refund_request import RefundRequest
from yookassa.domain.response.refund_list_response import RefundListResponse
from yookassa.domain.response.refund_response import RefundResponse


class Refund:
    """
    Класс, представляющий модель Refund.
    """  # noqa: E501

    base_path = '/refunds'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание возврата

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: RefundResponse Объект ответа, возвращаемого API при запросе информации о возврате
        """
        instance = cls()
        path = cls.base_path
        if not idempotency_key:
            idempotency_key = uuid.uuid4()
        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = RefundRequest(params)
        elif isinstance(params, RefundRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return RefundResponse(response)

    @classmethod
    def find_one(cls, refund_id):
        """
        Возвращает информацию о возврате

        :param refund_id: Уникальный идентификатор возврата
        :return: RefundResponse Объект ответа, возвращаемого API при запросе информации о возврате
        """
        instance = cls()
        if not isinstance(refund_id, str) or not refund_id:
            raise ValueError('Invalid payment_id value')
        path = instance.base_path + '/' + refund_id
        response = instance.client.request(HttpVerb.GET, path)
        return RefundResponse(response)

    @classmethod
    def list(cls, params):
        """
        Возвращает список возвратов

        :param params: Данные передаваемые в API
        :return: RefundListResponse Объект ответа, возвращаемого API при запросе списка возвратов
        """
        instance = cls()
        path = cls.base_path

        response = instance.client.request(HttpVerb.GET, path, params)
        return RefundListResponse(response)
