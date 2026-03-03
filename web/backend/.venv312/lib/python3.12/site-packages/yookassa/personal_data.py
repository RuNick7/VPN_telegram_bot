# -*- coding: utf-8 -*-
import uuid

from yookassa.client import ApiClient
from yookassa.domain.common import HttpVerb
from yookassa.domain.request import SbpPayoutRecipientPersonalDataRequest, PayoutStatementRecipientPersonalDataRequest, \
    PersonalDataRequestFactory
from yookassa.domain.response import PersonalDataResponse


class PersonalData:
    """
    Класс, представляющий модель PersonalData.
    """  # noqa: E501

    base_path = '/personal_data'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def find_one(cls, personal_data_id):
        """
        Возвращает информацию о персональных данных

        :param personal_data_id: Уникальный идентификатор персональных данных
        :return: PersonalDataResponse Объект ответа, возвращаемого API при запросе персональных данных
        """
        instance = cls()
        if not isinstance(personal_data_id, str) or not personal_data_id:
            raise ValueError('Invalid personal_data_id value')

        path = instance.base_path + '/' + personal_data_id
        response = instance.client.request(HttpVerb.GET, path)
        return PersonalDataResponse(response)

    @classmethod
    def create(cls, params, idempotency_key=None):
        """
        Создание персональных данных

        :param params: Данные передаваемые в API
        :param idempotency_key: Ключ идемпотентности
        :return: PersonalDataResponse Объект ответа, возвращаемого API при запросе персональных данных
        """
        instance = cls()
        path = cls.base_path

        if not idempotency_key:
            idempotency_key = uuid.uuid4()

        headers = {
            'Idempotence-Key': str(idempotency_key)
        }

        if isinstance(params, dict):
            params_object = PersonalDataRequestFactory().create(params, 'request')
        elif isinstance(params, SbpPayoutRecipientPersonalDataRequest) or isinstance(params, PayoutStatementRecipientPersonalDataRequest):
            params_object = params
        else:
            raise TypeError('Invalid params value type')

        response = instance.client.request(HttpVerb.POST, path, None, headers, params_object)
        return PersonalDataResponse(response)
