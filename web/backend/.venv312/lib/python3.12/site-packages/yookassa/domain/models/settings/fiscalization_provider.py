# coding: utf-8

class FiscalizationProvider(object):
    """
    Решение ЮKassa, которое магазин использует для отправки чеков. Возможные значения:
        * [54-ФЗ: Чеки от ЮKassa](/developers/payment-acceptance/receipts/54fz/yoomoney/basics) — `avanpost`
        * [54-ФЗ: сторонняя онлайн-касса](/developers/payment-acceptance/receipts/54fz/other-services/basics) (наименование онлайн-кассы) — ~`a_qsi` (aQsi online), ~`atol` (АТОЛ Онлайн), ~`business_ru` (Бизнес.ру), ~`digital_kassa` (digitalkassa), ~`evotor` (Эвотор), ~`first_ofd` (Первый ОФД), ~`kit_invest` (Кит Инвест), ~`komtet` (КОМТЕТ Касса), ~`life_pay` (LIFE PAY), ~`mertrade` (Mertrade), ~`modul_kassa` (МодульКасса), ~`rocket` (RocketR), ~`shtrih_m` (Orange Data).
    """  # noqa: E501

    """
    Список допустимых значений
    """
    ATOL = "atol"
    """АТОЛ Онлайн"""
    BUSINESS_RU = "business_ru"
    """Бизнес.ру"""
    SHTRIH_M = "shtrih_m"
    """Orange Data"""
    MODUL_KASSA = "modul_kassa"
    """МодульКасса"""
    EVOTOR = "evotor"
    """Эвотор"""
    KIT_INVEST = "kit_invest"
    """Кит Инвест"""
    A_QSI = "a_qsi"
    """aQsi online"""
    AVANPOST = "avanpost"
    """54-ФЗ: Чеки от ЮKassa"""
    MERTRADE = "mertrade"
    """Mertrade"""
    FIRST_OFD = "first_ofd"
    """Первый ОФД"""
    LIFE_PAY = "life_pay"
    """LIFE PAY"""
    ROCKET = "rocket"
    """RocketR"""
    DIGITAL_KASSA = "digital_kassa"
    """digitalkassa"""
    KOMTET = "komtet"
    """КОМТЕТ Касса"""
