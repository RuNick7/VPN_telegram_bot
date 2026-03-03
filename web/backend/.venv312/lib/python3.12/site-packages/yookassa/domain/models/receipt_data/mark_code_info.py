# coding: utf-8
import re  # noqa: F401

from yookassa.domain.common import BaseObject


class MarkCodeInfo(BaseObject):
    """
    Код товара (тег в 54 ФЗ — 1163). Обязательный параметр, если одновременно выполняются эти условия:
      * вы используете Чеки от ЮKassa или онлайн-кассу, обновленную до ФФД 1.2;
      * товар нужно [маркировать](http://docs.cntd.ru/document/902192509).
    Должно быть заполнено хотя бы одно поле.
    """  # noqa: E501

    __mark_code_raw = None
    """
    Код товара в том виде, в котором он был прочитан сканером (тег в 54 ФЗ — 2000).
    Нужно передавать, если используете онлайн-кассу Orange Data.
    Пример: ~`010460406000590021N4N57RTCBUZTQ\\u001d2403054002410161218\\u001d1424010191ffd0\\u001g92tIAF/YVpU4roQS3M/m4z78yFq0nc/WsSmLeX6QkF/YVWwy5IMYAeiQ91Xa2m/fFSJcOkb2N+uUUtfr4n0mOX0Q==`
    """  # noqa: E501

    __unknown = None
    """Нераспознанный код товара (тег в 54 ФЗ — 1300)."""  # noqa: E501

    __ean_8 = None
    """Код товара в формате EAN-8 (тег в 54 ФЗ — 1301)."""  # noqa: E501

    __ean_13 = None
    """Код товара в формате EAN-13 (тег в 54 ФЗ — 1302)."""  # noqa: E501

    __itf_14 = None
    """Код товара в формате ITF-14 (тег в 54 ФЗ — 1303)."""  # noqa: E501

    __gs_10 = None
    """
    Код товара в формате GS1.0 (тег в 54 ФЗ — 1304).
    Можно передавать, если используете онлайн-кассу Orange Data, aQsi, Кит Инвест.
    """  # noqa: E501

    __gs_1m = None
    """Код товара в формате GS1.M (тег в 54 ФЗ — 1305)."""  # noqa: E501

    __short = None
    """Код товара в формате короткого кода маркировки (тег в 54 ФЗ — 1306)."""  # noqa: E501

    __fur = None
    """Контрольно-идентификационный знак мехового изделия (тег в 54 ФЗ — 1307)."""  # noqa: E501

    __egais_20 = None
    """Код товара в формате ЕГАИС-2.0 (тег в 54 ФЗ — 1308)."""  # noqa: E501

    __egais_30 = None
    """Код товара в формате ЕГАИС-3.0 (тег в 54 ФЗ — 1309)."""  # noqa: E501

    @property
    def mark_code_raw(self):
        """
        Возвращает mark_code_raw модели MarkCodeInfo.

        :return: mark_code_raw модели MarkCodeInfo.
        :rtype: str
        """
        return self.__mark_code_raw

    @mark_code_raw.setter
    def mark_code_raw(self, value):
        """
        Устанавливает mark_code_raw модели MarkCodeInfo.

        :param value: mark_code_raw модели MarkCodeInfo.
        :type value: str
        """
        self.__mark_code_raw = value

    @property
    def unknown(self):
        """
        Возвращает unknown модели MarkCodeInfo.

        :return: unknown модели MarkCodeInfo.
        :rtype: str
        """
        return self.__unknown

    @unknown.setter
    def unknown(self, value):
        """
        Устанавливает unknown модели MarkCodeInfo.

        :param value: unknown модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 32:
            raise ValueError("Invalid value for `unknown`, length must be less than or equal to `32`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `unknown`, length must be greater than or equal to `1`")  # noqa: E501
        self.__unknown = value

    @property
    def ean_8(self):
        """
        Возвращает ean_8 модели MarkCodeInfo.

        :return: ean_8 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__ean_8

    @ean_8.setter
    def ean_8(self, value):
        """
        Устанавливает ean_8 модели MarkCodeInfo.

        :param value: ean_8 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 8:
            raise ValueError("Invalid value for `ean_8`, length must be less than or equal to `8`")  # noqa: E501
        if value is not None and len(value) < 8:
            raise ValueError("Invalid value for `ean_8`, length must be greater than or equal to `8`")  # noqa: E501
        self.__ean_8 = value

    @property
    def ean_13(self):
        """
        Возвращает ean_13 модели MarkCodeInfo.

        :return: ean_13 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__ean_13

    @ean_13.setter
    def ean_13(self, value):
        """
        Устанавливает ean_13 модели MarkCodeInfo.

        :param value: ean_13 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 13:
            raise ValueError("Invalid value for `ean_13`, length must be less than or equal to `13`")  # noqa: E501
        if value is not None and len(value) < 13:
            raise ValueError("Invalid value for `ean_13`, length must be greater than or equal to `13`")  # noqa: E501
        self.__ean_13 = value

    @property
    def itf_14(self):
        """
        Возвращает itf_14 модели MarkCodeInfo.

        :return: itf_14 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__itf_14

    @itf_14.setter
    def itf_14(self, value):
        """
        Устанавливает itf_14 модели MarkCodeInfo.

        :param value: itf_14 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 14:
            raise ValueError("Invalid value for `itf_14`, length must be less than or equal to `14`")  # noqa: E501
        if value is not None and len(value) < 14:
            raise ValueError("Invalid value for `itf_14`, length must be greater than or equal to `14`")  # noqa: E501
        self.__itf_14 = value

    @property
    def gs_10(self):
        """
        Возвращает gs_10 модели MarkCodeInfo.

        :return: gs_10 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__gs_10

    @gs_10.setter
    def gs_10(self, value):
        """
        Устанавливает gs_10 модели MarkCodeInfo.

        :param value: gs_10 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 38:
            raise ValueError("Invalid value for `gs_10`, length must be less than or equal to `38`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `gs_10`, length must be greater than or equal to `1`")  # noqa: E501
        self.__gs_10 = value

    @property
    def gs_1m(self):
        """
        Возвращает gs_1m модели MarkCodeInfo.

        :return: gs_1m модели MarkCodeInfo.
        :rtype: str
        """
        return self.__gs_1m

    @gs_1m.setter
    def gs_1m(self, value):
        """
        Устанавливает gs_1m модели MarkCodeInfo.

        :param value: gs_1m модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 200:
            raise ValueError("Invalid value for `gs_1m`, length must be less than or equal to `200`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `gs_1m`, length must be greater than or equal to `1`")  # noqa: E501
        self.__gs_1m = value

    @property
    def short(self):
        """
        Возвращает short модели MarkCodeInfo.

        :return: short модели MarkCodeInfo.
        :rtype: str
        """
        return self.__short

    @short.setter
    def short(self, value):
        """
        Устанавливает short модели MarkCodeInfo.

        :param value: short модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 38:
            raise ValueError("Invalid value for `short`, length must be less than or equal to `38`")  # noqa: E501
        if value is not None and len(value) < 1:
            raise ValueError("Invalid value for `short`, length must be greater than or equal to `1`")  # noqa: E501
        self.__short = value

    @property
    def fur(self):
        """
        Возвращает fur модели MarkCodeInfo.

        :return: fur модели MarkCodeInfo.
        :rtype: str
        """
        return self.__fur

    @fur.setter
    def fur(self, value):
        """
        Устанавливает fur модели MarkCodeInfo.

        :param value: fur модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 20:
            raise ValueError("Invalid value for `fur`, length must be less than or equal to `20`")  # noqa: E501
        if value is not None and len(value) < 20:
            raise ValueError("Invalid value for `fur`, length must be greater than or equal to `20`")  # noqa: E501
        self.__fur = value

    @property
    def egais_20(self):
        """
        Возвращает egais_20 модели MarkCodeInfo.

        :return: egais_20 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__egais_20

    @egais_20.setter
    def egais_20(self, value):
        """
        Устанавливает egais_20 модели MarkCodeInfo.

        :param value: egais_20 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 33:
            raise ValueError("Invalid value for `egais_20`, length must be less than or equal to `33`")  # noqa: E501
        if value is not None and len(value) < 33:
            raise ValueError("Invalid value for `egais_20`, length must be greater than or equal to `33`")  # noqa: E501
        self.__egais_20 = value

    @property
    def egais_30(self):
        """
        Возвращает egais_30 модели MarkCodeInfo.

        :return: egais_30 модели MarkCodeInfo.
        :rtype: str
        """
        return self.__egais_30

    @egais_30.setter
    def egais_30(self, value):
        """
        Устанавливает egais_30 модели MarkCodeInfo.

        :param value: egais_30 модели MarkCodeInfo.
        :type value: str
        """
        if value is not None and len(value) > 14:
            raise ValueError("Invalid value for `egais_30`, length must be less than or equal to `14`")  # noqa: E501
        if value is not None and len(value) < 14:
            raise ValueError("Invalid value for `egais_30`, length must be greater than or equal to `14`")  # noqa: E501
        self.__egais_30 = value
