# -*- coding: utf-8 -*-

class Locale:
    """
     Класс, представляющий модель Locale.

     Язык интерфейса, писем и смс, которые будет видеть или получать пользователь. Формат соответствует [ISO/IEC 15897](https://en.wikipedia.org/wiki/Locale_(computer_software)).

     Возможные значения:
     - `ru_RU` - Русский
     - `en_US` - English

     Регистр важен.
    """  # noqa: E501

    RUSSIAN = 'ru_RU'
    """Русский"""
    ENGLISH = 'en_US'
    """English"""
