# -*- coding: utf-8 -*-
from yookassa.domain.request import PayoutRequest


class PayoutRequestBuilder(object):
    """
    Конструктор запроса на проведение новой выплаты.
    """  # noqa: E501

    def __init__(self):
        self.__request = PayoutRequest()

    def set_amount(self, value):
        """
        Устанавливает amount модели PayoutRequestBuilder.

        :param value: amount модели PayoutRequestBuilder.
        :type value: Amount
        :rtype: PayoutRequestBuilder
        """
        self.__request.amount = value
        return self

    def set_description(self, value):
        """
        Устанавливает description модели PayoutRequestBuilder.

        :param value: description модели PayoutRequestBuilder.
        :type value: str
        :rtype: PayoutRequestBuilder
        """
        self.__request.description = value
        return self

    def set_payout_token(self, value):
        """
        Устанавливает payout_token модели PayoutRequestBuilder.

        :param value: payout_token модели PayoutRequestBuilder.
        :type value: str
        :rtype: PayoutRequestBuilder
        """
        self.__request.payout_token = value
        return self

    def set_payout_destination_data(self, value):
        """
        Устанавливает payout_destination_data модели PayoutRequestBuilder.

        :param value: payout_destination_data модели PayoutRequestBuilder.
        :type value: PayoutDestination
        :rtype: PayoutRequestBuilder
        """
        self.__request.payout_destination_data = value
        return self

    def set_deal(self, value):
        """
        Устанавливает deal модели PayoutRequestBuilder.

        :param value: deal модели PayoutRequestBuilder.
        :type value: PayoutDealInfo
        :rtype: PayoutRequestBuilder
        """
        self.__request.deal = value
        return self

    def set_metadata(self, value):
        """
        Устанавливает metadata модели PayoutRequestBuilder.

        :param value: metadata модели PayoutRequestBuilder.
        :type value: dict[str, str]
        :rtype: PayoutRequestBuilder
        """
        self.__request.metadata = value
        return self

    def build(self):
        """
        Возвращает request модели PayoutRequestBuilder.

        :return: request модели PayoutRequestBuilder.
        :rtype: PayoutRequest
        """
        return self.__request
