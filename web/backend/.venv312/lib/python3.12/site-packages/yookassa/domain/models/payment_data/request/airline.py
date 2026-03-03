# -*- coding: utf-8 -*-
import datetime
import re

from yookassa.domain.common import BaseObject


class Airline(BaseObject):
    """
    Объект с данными для %[продажи авиабилетов](/developers/payment-acceptance/scenario-extensions/airline-tickets). Используется только для платежей банковской картой.
    """  # noqa: E501

    __booking_reference = None
    """Номер бронирования. Обязателен, если не передан `ticket_number`."""  # noqa: E501

    __ticket_number = None
    """Уникальный номер билета. Если при создании платежа вы уже знаете номер билета, тогда `ticket_number` — обязательный параметр. Если не знаете, тогда вместо `ticket_number` необходимо передать `booking_reference` с номером бронирования."""  # noqa: E501

    __passengers = None
    """Список пассажиров."""  # noqa: E501

    __legs = None
    """Список перелетов."""  # noqa: E501

    @property
    def booking_reference(self):
        """
        Возвращает booking_reference модели Airline.

        :return: booking_reference модели Airline.
        :rtype: str
        """
        return self.__booking_reference

    @booking_reference.setter
    def booking_reference(self, value):
        """
        Устанавливает booking_reference модели Airline.

        :param value: booking_reference модели Airline.
        :type value: str
        """
        cast_value = str(value)
        if cast_value and len(cast_value) <= 20:
            self.__booking_reference = cast_value
        else:
            raise ValueError('Invalid booking_reference value')

    @property
    def ticket_number(self):
        """
        Возвращает ticket_number модели Airline.

        :return: ticket_number модели Airline.
        :rtype: str
        """
        return self.__ticket_number

    @ticket_number.setter
    def ticket_number(self, value):
        """
        Устанавливает ticket_number модели Airline.

        :param value: ticket_number модели Airline.
        :type value: str
        """
        cast_value = str(value)
        if re.match('^[0-9]{1,150}$', cast_value):
            self.__ticket_number = cast_value
        else:
            raise ValueError('Invalid ticket_number value')

    @property
    def passengers(self):
        """
        Возвращает passengers модели Airline.

        :return: passengers модели Airline.
        :rtype: list[Passenger]
        """
        return self.__passengers

    @passengers.setter
    def passengers(self, value):
        """
        Устанавливает passengers модели Airline.

        :param value: passengers модели Airline.
        :type value: list[Passenger]
        """
        if isinstance(value, list):
            if len(value) > 500:
                raise ValueError("Invalid value for `passengers`, number of items must be less than or equal to `500`")  # noqa: E501

            passengers = []
            for passengerData in value:
                if isinstance(passengerData, dict):
                    passengers.append(Passenger(passengerData))
                elif isinstance(passengerData, Passenger):
                    passengers.append(passengerData)
                else:
                    raise TypeError('Invalid passengers data type in airline.passengers')

            self.__passengers = passengers
        else:
            raise TypeError('Invalid passengers value type in airline')

    @property
    def legs(self):
        """
        Возвращает legs модели Airline.

        :return: legs модели Airline.
        :rtype: list[Leg]
        """
        return self.__legs

    @legs.setter
    def legs(self, value):
        """
        Устанавливает legs модели Airline.

        :param value: legs модели Airline.
        :type value: list[Leg]
        """
        if isinstance(value, list):
            if len(value) > 4:
                raise ValueError("Invalid value for `legs`, number of items must be less than or equal to `4`")  # noqa: E501

            legs = []
            for legData in value:
                if isinstance(legData, dict):
                    legs.append(Leg(legData))
                elif isinstance(legData, Leg):
                    legs.append(legData)
                else:
                    raise TypeError('Invalid legs data type in airline.passengers')

            self.__legs = legs
        else:
            raise TypeError('Invalid legs value type in airline')


class Passenger(BaseObject):
    """
    Информация о пассажире.
    """  # noqa: E501

    __first_name = None
    """Имя пассажира. Необходимо использовать латинские буквы, например SERGEI."""  # noqa: E501

    __last_name = None
    """Фамилия пассажира. Необходимо использовать латинские буквы, например IVANOV."""  # noqa: E501

    @property
    def first_name(self):
        """
        Возвращает first_name модели Passenger.

        :return: first_name модели Passenger.
        :rtype: str
        """
        return self.__first_name

    @first_name.setter
    def first_name(self, value):
        """
        Устанавливает first_name модели Passenger.

        :param value: first_name модели Passenger.
        :type value: str
        """
        cast_value = str(value)
        if cast_value and len(cast_value) <= 64:
            self.__first_name = cast_value
        else:
            raise ValueError('Invalid passengers first_name value')

    @property
    def last_name(self):
        """
        Возвращает last_name модели Passenger.

        :return: last_name модели Passenger.
        :rtype: str
        """
        return self.__last_name

    @last_name.setter
    def last_name(self, value):
        """
        Устанавливает last_name модели Passenger.

        :param value: last_name модели Passenger.
        :type value: str
        """
        cast_value = str(value)
        if cast_value and len(cast_value) <= 64:
            self.__last_name = cast_value
        else:
            raise ValueError('Invalid passengers last_name value')


class Leg(BaseObject):
    """
    Информация о перелете.
    """  # noqa: E501

    __departure_airport = None
    """Код аэропорта вылета по справочнику [IATA](https://www.iata.org/publications/Pages/code-search.aspx), например LED."""  # noqa: E501

    __destination_airport = None
    """Код аэропорта прилета по справочнику [IATA](https://www.iata.org/publications/Pages/code-search.aspx), например AMS."""  # noqa: E501

    __departure_date = None
    """Дата вылета в формате YYYY-MM-DD по стандарту [ISO 8601:2004](http://www.iso.org/iso/catalogue_detail?csnumber=40874)."""  # noqa: E501

    @property
    def departure_airport(self):
        """
        Возвращает departure_airport модели Leg.

        :return: departure_airport модели Leg.
        :rtype: str
        """
        return self.__departure_airport

    @departure_airport.setter
    def departure_airport(self, value):
        """
        Устанавливает departure_airport модели Leg.

        :param value: departure_airport модели Leg.
        :type value: str
        """
        if re.match('^[A-Z]{3}$', value):
            self.__departure_airport = value
        else:
            raise ValueError('Invalid departure_airport value')

    @property
    def destination_airport(self):
        """
        Возвращает destination_airport модели Leg.

        :return: destination_airport модели Leg.
        :rtype: str
        """
        return self.__destination_airport

    @destination_airport.setter
    def destination_airport(self, value):
        """
        Устанавливает destination_airport модели Leg.

        :param value: destination_airport модели Leg.
        :type value: str
        """
        if re.match('^[A-Z]{3}$', value):
            self.__destination_airport = value
        else:
            raise ValueError('Invalid destination_airport value')

    @property
    def departure_date(self):
        """
        Возвращает departure_date модели Leg.

        :return: departure_date модели Leg.
        :rtype: date
        """
        return self.__departure_date

    @departure_date.setter
    def departure_date(self, value):
        """
        Устанавливает departure_date модели Leg.

        :param value: departure_date модели Leg.
        :type value: date
        """
        try:
            datetime.datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Incorrect data format, should be YYYY-MM-DD")

        self.__departure_date = value
