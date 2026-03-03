# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.request import InvoiceRequest
from yookassa.domain.response.invoice_response import InvoiceResponse


class Invoice:
    """
    Класс, представляющий модель Invoice.
    """  # noqa: E501

    base_path = '/invoices'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def find_one(cls, invoice_id):
        """
        Возвращает информацию о счёте

        :param invoice_id: Уникальный идентификатор счёта
        :return: InvoiceResponse Объект ответа, возвращаемого API при запросе счёта
        """
        instance = cls()
        if not isinstance(invoice_id, str) or not invoice_id:
            raise ValueError('Invalid invoice_id value')

        path = instance.base_path + '/' + invoice_id
        response = instance.client.request(HttpVerb.GET, path)
        return InvoiceResponse(response)

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание счёта

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: InvoiceResponse Объект ответа, возвращаемого API при запросе выплате
        """
        instance = cls()
        path = cls.base_path

        if not idempotency_key:
            idempotency_key = uuid.uuid4()

        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = InvoiceRequest(params)
        elif isinstance(params, InvoiceRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return InvoiceResponse(response)
