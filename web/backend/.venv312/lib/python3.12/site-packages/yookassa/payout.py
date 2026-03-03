# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.request import PayoutRequest
from yookassa.domain.response import PayoutResponse, PayoutListResponse


class Payout:
    """
    Класс, представляющий модель Payout.
    """  # noqa: E501

    base_path = '/payouts'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def find_one(cls, payout_id):
        """
        Возвращает информацию о выплате

        :param payout_id: Уникальный идентификатор выплаты
        :return: PayoutResponse Объект ответа, возвращаемого API при запросе выплаты
        """
        instance = cls()
        if not isinstance(payout_id, str) or not payout_id:
            raise ValueError('Invalid payout_id value')

        path = instance.base_path + '/' + payout_id
        response = instance.client.request(HttpVerb.GET, path)
        return PayoutResponse(response)

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание выплаты

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: PayoutResponse Объект ответа, возвращаемого API при запросе выплате
        """
        instance = cls()
        path = cls.base_path

        if not idempotency_key:
            idempotency_key = uuid.uuid4()

        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = PayoutRequest(params)
        elif isinstance(params, PayoutRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return PayoutResponse(response)

    @classmethod
    def list(cls, params=None):
        """
        Возвращает список выплат

        :param params: Данные передаваемые в API
        :return: PayoutListResponse Объект ответа, возвращаемого API при запросе списка платежей
        """
        if params is None:
            params = {}
        instance = cls()
        path = cls.base_path

        response = instance.client.request(HttpVerb.GET, path, params)
        return PayoutListResponse(response)
