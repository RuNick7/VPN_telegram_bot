# -*- coding: utf-8 -*-
from yookassa.client import ApiClient
from yookassa.domain.common.http_verb import HttpVerb
from yookassa.domain.response import SbpBankListResponse


class SbpBanks:
    """
    Класс, представляющий модель SbpBanks.
    """  # noqa: E501

    base_path = '/sbp_banks'

    def __init__(self):
        self.client = ApiClient()

    @classmethod
    def list(cls):
        """
        Возвращает список участников СБП

        :return: SbpBankListResponse Объект ответа, возвращаемого API при запросе списка участников СБП
        """
        instance = cls()
        path = cls.base_path

        response = instance.client.request(HttpVerb.GET, path)
        return SbpBankListResponse(response)
