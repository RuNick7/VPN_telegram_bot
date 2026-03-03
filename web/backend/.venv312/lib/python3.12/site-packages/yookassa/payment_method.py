# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.request.payment_method_request import PaymentMethodRequest
from yookassa.domain.response.payment_method_response import PaymentMethodResponse


class PaymentMethod:
    """
    Класс, представляющий модель PaymentMethod.
    """  # noqa: E501

    base_path = '/payment_methods'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def find_one(cls, payment_method_id):
        """
        Возвращает информацию о способе оплаты

        :param payment_method_id: Уникальный идентификатор способа оплаты
        :return: PaymentMethodResponse Объект ответа, возвращаемого API при запросе способа оплаты
        """
        instance = cls()
        if not isinstance(payment_method_id, str) or not payment_method_id:
            raise ValueError('Invalid payment_method_id value')

        path = instance.base_path + '/' + payment_method_id
        response = instance.client.request(HttpVerb.GET, path)
        return PaymentMethodResponse(response)

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание способа оплаты

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: PaymentMethodResponse Объект ответа, возвращаемого API при запросе способа оплаты
        """
        instance = cls()
        path = cls.base_path

        if not idempotency_key:
            idempotency_key = uuid.uuid4()

        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = PaymentMethodRequest(params)
        elif isinstance(params, PaymentMethodRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return PaymentMethodResponse(response)
