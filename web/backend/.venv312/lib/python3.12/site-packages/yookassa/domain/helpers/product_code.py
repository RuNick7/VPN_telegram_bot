# coding: utf-8
import re
from typing import Optional, Union, Dict, List


class ProductCode:
    """Класс для формирования тега 1162 на основе кода в формате Data Matrix."""  # noqa: E501

    PREFIX_DATA_MATRIX = '444D'
    """Код типа маркировки DataMatrix"""  # noqa: E501

    PREFIX_UNKNOWN = '0000'
    """Код типа маркировки UNKNOWN"""  # noqa: E501

    PREFIX_EAN_8 = '4508'
    """Код типа маркировки EAN_8"""  # noqa: E501

    PREFIX_EAN_13 = '450D'
    """Код типа маркировки EAN_13"""  # noqa: E501

    PREFIX_ITF_14 = '4909'
    """Код типа маркировки ITF_14"""  # noqa: E501

    PREFIX_FUR = '5246'
    """Код типа маркировки FUR"""  # noqa: E501

    PREFIX_EGAIS_20 = 'C514'
    """Код типа маркировки EGAIS_20"""  # noqa: E501

    PREFIX_EGAIS_30 = 'C51E'
    """Код типа маркировки EGAIS_30"""  # noqa: E501

    TYPE_UNKNOWN = 'unknown'
    """Тип маркировки UNKNOWN"""  # noqa: E501

    TYPE_EAN_8 = 'ean_8'
    """Тип маркировки EAN_8"""  # noqa: E501

    TYPE_EAN_13 = 'ean_13'
    """Тип маркировки EAN_13"""  # noqa: E501

    TYPE_ITF_14 = 'itf_14'
    """Тип маркировки ITF_14"""  # noqa: E501

    TYPE_GS_10 = 'gs_10'
    """Тип маркировки GS_10"""  # noqa: E501

    TYPE_GS_1M = 'gs_1m'
    """Тип маркировки GS_1M"""  # noqa: E501

    TYPE_SHORT = 'short'
    """Тип маркировки SHORT"""  # noqa: E501

    TYPE_FUR = 'fur'
    """Тип маркировки FUR"""  # noqa: E501

    TYPE_EGAIS_20 = 'egais_20'
    """Тип маркировки EGAIS_20"""  # noqa: E501

    TYPE_EGAIS_30 = 'egais_30'
    """Тип маркировки EGAIS_30"""  # noqa: E501

    AI_GTIN = '01'
    """Идентификатор применения (идентификационный номер единицы товара)"""  # noqa: E501

    AI_SERIAL = '21'
    """Идентификатор применения (серийный номер)"""  # noqa: E501

    AI_SUM = '8005'
    """Дополнительный идентификатор применения (цена единицы измерения товара)"""  # noqa: E501

    MAX_PRODUCT_CODE_LENGTH = 30
    """Максимальная длина последовательности для кода продукта unknown"""  # noqa: E501

    MAX_MARK_CODE_LENGTH = 32
    """Максимальная длина последовательности для кода маркировки типа unknown"""  # noqa: E501

    _prefix = None
    """Код типа маркировки"""  # noqa: E501

    _type = None
    """Тип маркировки"""  # noqa: E501

    _gtin = None
    """Глобальный номер товарной продукции в единой международной базе товаров GS1 https://ru.wikipedia.org/wiki/GS1. Пример: 04630037591316"""  # noqa: E501

    _serial = None
    """Серийный номер товара. Пример: sgEKKPPcS25y5"""  # noqa: E501

    _app_identifiers = None
    """Массив дополнительных идентификаторов применения."""  # noqa: E501

    _result = None
    """Сформированный тег 1162. Формат: hex([prefix]+gtin+serial). Пример: 04 36 03 BE F5 14 73  67  45  4b  4b  50  50  63  53  32  35  79  35"""  # noqa: E501

    _mark_code_info = None
    """Сформированный код товара (тег в 54 ФЗ — 1163)."""  # noqa: E501

    _use_prefix = False
    """Флаг использования кода типа маркировки."""  # noqa: E501

    def __init__(self, code_data_matrix, use_prefix=True):
        """
        Инициализация объекта ProductCode.

        :param code_data_matrix: Строка, расшифрованная из QR-кода
        :param use_prefix: Нужен ли код типа маркировки в результате (True/False или строка с префиксом)
        """
        self._prepare_prefix(use_prefix)

        if code_data_matrix and self._parse_code_matrix_data(code_data_matrix):
            self._result = self.calc_result()

    def __str__(self) -> str:
        """Приведение объекта к строке."""
        return self.get_result()

    @property
    def prefix(self) -> Optional[str]:
        """Возвращает код типа маркировки."""
        return self._prefix

    @prefix.setter
    def prefix(self, value: Union[int, str, None]):
        """Устанавливает код типа маркировки."""
        if value is None or value == '':
            self._prefix = None
            return

        if isinstance(value, int):
            value = hex(value)[2:]
        self._prefix = value.zfill(4).upper()

    @property
    def type(self) -> Optional[str]:
        """Возвращает тип маркировки."""
        return self._type

    @type.setter
    def type(self, value: str):
        """Устанавливает тип маркировки."""
        self._type = value

    @property
    def gtin(self) -> Optional[str]:
        """Возвращает глобальный номер товарной продукции."""
        return self._gtin

    @gtin.setter
    def gtin(self, value: Optional[str]):
        """Устанавливает глобальный номер товарной продукции."""
        self._gtin = value if value not in (None, '') else None

    @property
    def serial(self) -> Optional[str]:
        """Возвращает серийный номер товара."""
        return self._serial

    @serial.setter
    def serial(self, value: Optional[str]):
        """Устанавливает серийный номер товара."""
        self._serial = value if value not in (None, '') else None

    @property
    def app_identifiers(self) -> Optional[List[str]]:
        """Возвращает массив дополнительных идентификаторов применения."""
        return self._app_identifiers

    @app_identifiers.setter
    def app_identifiers(self, value: Optional[List[str]]):
        """Устанавливает массив дополнительных идентификаторов применения."""
        self._app_identifiers = value

    @property
    def use_prefix(self) -> bool:
        """Возвращает флаг использования кода типа маркировки."""
        return self._use_prefix

    @use_prefix.setter
    def use_prefix(self, value: bool):
        """Устанавливает флаг использования кода типа маркировки."""
        self._use_prefix = value

    def get_result(self) -> str:
        """Возвращает сформированный тег 1162."""
        if not self._result:
            self._result = self.calc_result()
        return self._result

    def get_mark_code_info(self) -> Optional[Dict]:
        """Возвращает сформированный код товара (тег в 54 ФЗ — 1163)."""
        return self._mark_code_info

    def set_mark_code_info(self, value: Union[Dict, str]):
        """Устанавливает код товара (тег в 54 ФЗ — 1163)."""
        if isinstance(value, str):
            self._mark_code_info = {self.type: value}
        elif isinstance(value, dict):
            self._mark_code_info = value

    def calc_result(self) -> str:
        """Формирует тег 1162."""
        result = ''

        if not self.validate():
            return result

        if self.use_prefix:
            result = self.prefix if self.prefix else self.PREFIX_DATA_MATRIX

        if self.type == self.TYPE_EAN_8 or self.type == self.TYPE_EAN_13 or self.type == self.TYPE_ITF_14:
            result += self._num_to_hex(self.gtin)
        elif self.type in (self.TYPE_FUR, self.TYPE_EGAIS_20, self.TYPE_EGAIS_30, self.TYPE_UNKNOWN):
            result += self._str_to_hex(self.gtin)
        elif self.type == self.TYPE_SHORT:
            result += self._num_to_hex(self.gtin)
            result += self._str_to_hex(self.serial)
        elif self.type in (self.TYPE_GS_1M, self.TYPE_GS_10):
            result += self._num_to_hex(self.gtin)
            result += self._str_to_hex(self.serial)
            if sum_value := self._get_ai_value(self.AI_SUM):
                result += self._str_to_hex(sum_value)

        return self._chunk_str(result)

    def validate(self) -> bool:
        """Проверяет заполненность необходимых свойств."""
        if not self.type:
            return False

        if self.type in (
                self.TYPE_EAN_8, self.TYPE_EAN_13, self.TYPE_ITF_14,
                self.TYPE_FUR, self.TYPE_EGAIS_20, self.TYPE_EGAIS_30,
                self.TYPE_UNKNOWN
        ):
            return self.gtin is not None
        elif self.type in (self.TYPE_GS_10, self.TYPE_GS_1M, self.TYPE_SHORT):
            return self.gtin is not None and self.serial is not None
        else:
            return False

    def _prepare_prefix(self, use_prefix: Union[bool, str]):
        """Устанавливает prefix и use_prefix в зависимости от входящего параметра."""
        if use_prefix:
            self.use_prefix = True
            if isinstance(use_prefix, (str, int)):
                self.prefix = use_prefix
            else:
                self.prefix = self.PREFIX_UNKNOWN
        else:
            self.use_prefix = False
            self.prefix = None

    def _parse_code_matrix_data(self, code_data_matrix: str) -> bool:
        """Извлекает данные из строки QR-кода и устанавливает свойства."""
        data = self._parse_scan_string(code_data_matrix)
        if not data:
            data = {'type': self.TYPE_UNKNOWN, 'code': code_data_matrix}

        self._fill_data(data)
        return self.validate()

    def _fill_data(self, data: Dict):
        """Заполняет поля объекта из массива данных."""
        self.type = data['type']
        self.prefix = self._get_prefix_by_type(data['type'])

        if self.type in (self.TYPE_EAN_8, self.TYPE_EAN_13, self.TYPE_ITF_14, self.TYPE_FUR, self.TYPE_EGAIS_30):
            self.gtin = data['match1']
            self.set_mark_code_info(self.gtin)
        elif self.type == self.TYPE_EGAIS_20:
            self.gtin = data['match2']
            self.set_mark_code_info(self.gtin)
        elif self.type == self.TYPE_SHORT:
            self.gtin = data['match1']
            self.serial = data['match2']
            self.set_mark_code_info(f"{self.AI_GTIN}{self.gtin}{self.AI_SERIAL}{self.serial}")
        elif self.type in (self.TYPE_GS_1M, self.TYPE_GS_10):
            self.gtin = data['match1']
            if data.get('split') and len(data['split']) > 1:
                self.serial = data['split'].pop(0)
                self.app_identifiers = data['split']
            else:
                self.serial = data['match2']
            self.set_mark_code_info(f"{self.AI_GTIN}{self.gtin}{self.AI_SERIAL}{self.serial}")
        elif self.type == self.TYPE_UNKNOWN:
            self.gtin = data['code'][:self.MAX_PRODUCT_CODE_LENGTH] if len(data['code']) > self.MAX_PRODUCT_CODE_LENGTH else data['code']
            self.serial = data['code'][:self.MAX_MARK_CODE_LENGTH] if len(data['code']) > self.MAX_MARK_CODE_LENGTH else data['code']
            self.set_mark_code_info(self.serial)

    def _parse_scan_string(self, code: str) -> Optional[Dict]:
        """Анализирует строку сканера и возвращает данные."""
        for code_type, rule in self._get_mark_code_rules().items():
            if rule.get('length') and len(code) != rule['length']:
                continue

            match = re.match(rule['pattern'], code)
            if not match:
                continue

            if rule['matches'][0] and not match.group(1):
                continue
            if rule['matches'][1] and not match.group(2):
                continue

            split = None
            if rule.get('split') and match.group(2):
                split = re.split(rule['split'], match.group(2))

            return {
                'type': code_type,
                'code': code,
                'rules': rule['matches'],
                'match1': match.group(1) if rule['matches'][0] else None,
                'match2': match.group(2) if rule['matches'][1] else None,
                'split': split
            }
        return None

    def _get_mark_code_rules(self) -> Dict:
        """Возвращает правила определения типа маркировки."""
        return {
            self.TYPE_GS_1M: {
                'pattern': r'^01(\d{14})21(.+)((91(.+)92(.+))|(93[\w!"%&\'()*+,-./_:;=<>?]{4}(.*)))$',
                'matches': [True, True],
                'split': r'\x1d'
            },
            self.TYPE_GS_10: {
                'pattern': r'^01(\d{14})21(.+)$',
                'matches': [True, True],
                'split': r'\x1d'
            },
            self.TYPE_SHORT: {
                'length': 29,
                'pattern': r'^(\d{14})(.+)$',
                'matches': [True, True]
            },
            self.TYPE_EGAIS_20: {
                'length': 68,
                'pattern': r'^(.{8})(.{33})(.+)$',
                'matches': [False, True]
            },
            self.TYPE_EGAIS_30: {
                'length': 150,
                'pattern': r'^(.{14})(.+)$',
                'matches': [True, False]
            },
            self.TYPE_ITF_14: {
                'length': 14,
                'pattern': r'^(0\d{13})$',
                'matches': [True, False]
            },
            self.TYPE_EAN_13: {
                'length': 13,
                'pattern': r'^(\d{13})$',
                'matches': [True, False]
            },
            self.TYPE_EAN_8: {
                'length': 8,
                'pattern': r'^(\d{8})$',
                'matches': [True, False]
            },
            self.TYPE_FUR: {
                'length': 20,
                'pattern': r'^((\w{2})-(\d{6})-(\w{10}))$',
                'matches': [True, False]
            }
        }

    def _get_ai_value(self, app_identifier: str) -> Optional[str]:
        """Возвращает значение идентификатора применения."""
        if not self.app_identifiers:
            return None

        for item in self.app_identifiers:
            if item.startswith(app_identifier):
                return item[len(app_identifier):]
        return None

    def _get_prefix_by_type(self, code_type: Optional[str] = None) -> str:
        """Возвращает префикс кода товара по типу маркировки."""
        if not code_type:
            code_type = self.type

        prefix_map = {
            self.TYPE_UNKNOWN: self.PREFIX_UNKNOWN,
            self.TYPE_EAN_8: self.PREFIX_EAN_8,
            self.TYPE_EAN_13: self.PREFIX_EAN_13,
            self.TYPE_ITF_14: self.PREFIX_ITF_14,
            self.TYPE_GS_10: self.PREFIX_DATA_MATRIX,
            self.TYPE_GS_1M: self.PREFIX_DATA_MATRIX,
            self.TYPE_SHORT: self.PREFIX_DATA_MATRIX,
            self.TYPE_FUR: self.PREFIX_FUR,
            self.TYPE_EGAIS_20: self.PREFIX_EGAIS_20,
            self.TYPE_EGAIS_30: self.PREFIX_EGAIS_30
        }

        return prefix_map.get(code_type, self.PREFIX_UNKNOWN)

    def _chunk_str(self, string: str) -> str:
        """Разбивает строку на пары символов с пробелами."""
        return ' '.join([string[i:i + 2] for i in range(0, len(string), 2)]).upper()

    def _num_to_hex(self, number: str) -> str:
        """Конвертирует число в шестнадцатеричный вид."""
        return self._base_convert(number).zfill(12)

    def _base_convert(self, num_str: str, from_base: int = 10, to_base: int = 16) -> str:
        """Конвертирует число между системами счисления."""
        chars = '0123456789abcdefghijklmnopqrstuvwxyz'
        to_string = chars[:to_base]

        number = [chars.index(c) for c in num_str]
        result = ''

        while number:
            divide = 0
            temp = []

            for digit in number:
                divide = divide * from_base + digit
                if divide >= to_base:
                    temp.append(divide // to_base)
                    divide %= to_base
                elif temp:
                    temp.append(0)

            number = temp
            result = to_string[divide] + result

        return result

    def _str_to_hex(self, string: str) -> str:
        """Конвертирует строку в шестнадцатеричный вид."""
        return ''.join(f"{ord(c):02x}" for c in string)

    def _hex_to_str(self, hex_str: str) -> str:
        """Конвертирует шестнадцатеричную строку в обычную (для тестирования)."""
        return ''.join(chr(int(hex_str[i:i + 2], 16)) for i in range(0, len(hex_str), 2))
