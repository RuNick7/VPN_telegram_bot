# -*- coding: utf-8 -*-
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class PayoutPersonalData(BaseObject):
    """
    Персональные данные получателя выплаты. Необходимо передавать, если вы делаете выплату с [проверкой получателя](/developers/payouts/scenario-extensions/recipient-check). Только для обычных выплат.
    """  # noqa: E501

    __id = None
    """Идентификатор персональных данных, сохраненных в ЮKassa."""  # noqa: E501

    @property
    def id(self):
        """
        Возвращает id модели PayoutPersonalData.

        :return: id модели PayoutPersonalData.
        :rtype: str
        """
        return self.__id

    @id.setter
    def id(self, value):
        """
        Устанавливает id модели PayoutPersonalData.

        :param value: id модели PayoutPersonalData.
        :type value: str
        """
        if value is None:  # noqa: E501
            raise ValueError("Invalid value for `id`, must not be `None`")  # noqa: E501
        if value is not None and len(value) > 50:
            raise ValueError("Invalid value for `id`, length must be less than or equal to `50`")  # noqa: E501
        if value is not None and len(value) < 36:
            raise ValueError("Invalid value for `id`, length must be greater than or equal to `36`")  # noqa: E501
        self.__id = value


class PersonalDataType(object):
    """Тип персональных данных — цель, для которой вы будете использовать данные.
    Возможные значение:
    * `sbp_payout_recipient` — [выплаты с проверкой получателя](https://yookassa.ru/developers/payouts/scenario-extensions/recipient-check)(только для выплат через СБП);
    * `payout_statement_recipient` — [выплаты с передачей данных получателя выплаты для выписок из реестра](https://yookassa.ru/developers/payouts/scenario-extensions/recipient-data-send). """  # noqa: E501

    """
    Список допустимых значений
    """
    PAYOUT_STATEMENT_RECIPIENT = "payout_statement_recipient"
    """Выплаты с передачей данных получателя выплаты для выписок из реестра"""
    SBP_PAYOUT_RECIPIENT = "sbp_payout_recipient"
    """Выплаты с проверкой получателя."""


class PersonalDataStatus(object):
    """Статус персональных данных.
    Возможные значения:
     * `waiting_for_operation` — данные сохранены, но не использованы при проведении выплаты;
     * `active` — данные сохранены и использованы при проведении выплаты; данные можно использовать повторно до срока, указанного в параметре `expires_at`;
     * `canceled` — хранение данных отменено, данные удалены, инициатор и причина отмены указаны в объекте cancellation_details (финальный и неизменяемый статус)."""  # noqa: E501

    """
    Список допустимых значений
    """
    WAITING_FOR_OPERATION = "waiting_for_operation"
    """Данные сохранены, но не использованы при проведении выплаты."""
    ACTIVE = "active"
    """Данные сохранены и использованы при проведении выплаты."""
    CANCELED = "canceled"
    """Хранение данных отменено."""
