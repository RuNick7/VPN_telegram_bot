# -*- coding: utf-8 -*-
import requests
from base64 import b64encode
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from yookassa import Configuration
from yookassa.domain.common import RequestObject, UserAgent
from yookassa.domain.exceptions import ApiError, BadRequestError, ForbiddenError, NotFoundError, \
    ResponseProcessingError, TooManyRequestsError, UnauthorizedError, InternalServerError, \
    GoneError


class ApiClient:
    """
    Класс клиента API.
    """  # noqa: E501

    def __init__(self):
        self.configuration = Configuration.instantiate()
        self.endpoint = Configuration.api_endpoint()
        self.shop_id = self.configuration.account_id
        self.shop_password = self.configuration.secret_key
        self.auth_token = self.configuration.auth_token
        self.timeout = self.configuration.timeout
        self.max_attempts = self.configuration.max_attempts

        self.user_agent = UserAgent()
        if self.configuration.agent_framework:
            self.user_agent.framework = self.configuration.agent_framework
        if self.configuration.agent_cms:
            self.user_agent.cms = self.configuration.agent_cms
        if self.configuration.agent_module:
            self.user_agent.module = self.configuration.agent_module

    def request(self, method="", path="", query_params=None, headers=None, body=None):
        """
        Подготовка запроса.

        :param method: HTTP метод
        :param path: URL запроса
        :param query_params: Массив GET параметров запроса
        :param headers: Массив заголовков запроса
        :param body: Тело запроса
        :rtype: str
        """
        if isinstance(body, RequestObject):
            body.validate()
            body = dict(body)

        request_headers = self.prepare_request_headers(headers)

        try:
            raw_response = self.execute(body, method, path, query_params, request_headers)
        except Exception as e:
            self.__handle_error(e.response)

        if raw_response.status_code != 200:
            self.__handle_error(raw_response)

        return raw_response.json()

    def execute(self, body, method, path, query_params, request_headers):
        """
        Выполнение запроса.

        :param body: Тело запроса
        :param method: HTTP метод
        :param path: URL запроса
        :param query_params: Массив GET параметров запроса
        :param request_headers: Массив заголовков запроса
        :return: Response
        """
        session = self.get_session()
        self.log_request(body, method, path, query_params, request_headers)

        raw_response = session.request(
            method,
            self.endpoint + path,
            params=query_params,
            headers=request_headers,
            json=body,
            verify=self.configuration.verify
        )

        session.close()
        self.log_response(raw_response.content, self.get_response_info(raw_response), raw_response.headers)

        return raw_response

    def get_session(self):
        """
        Получение сессии.

        :return: Session
        """
        session = requests.Session()
        retries = Retry(total=self.max_attempts,
                        backoff_factor=self.timeout / 1000,
                        allowed_methods=['POST'],
                        status_forcelist=[202])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    def prepare_request_headers(self, headers):
        """
        Подготовка заголовков запроса.

        :param headers: Массив заголовков запроса
        :return: dict[str, str]
        """
        request_headers = {'Content-type': 'application/json'}
        if self.auth_token is not None:
            auth_headers = {"Authorization": "Bearer " + self.auth_token}
        else:
            auth_headers = {"Authorization": self.basic_auth(self.shop_id, self.shop_password)}

        request_headers.update(auth_headers)

        request_headers.update({"YM-User-Agent": self.user_agent.get_header_string()})

        if isinstance(headers, dict):
            request_headers.update(headers)
        return request_headers

    @staticmethod
    def basic_auth(username, password):
        """
        Формирование токена для Basic авторизации.

        :param username: ShopId магазина
        :param password: Секретный ключ магазина
        :return: str
        """
        token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
        return f'Basic {token}'

    @staticmethod
    def __handle_error(raw_response):
        """
        Выбрасывает исключение по коду ошибки.
        """
        http_code = raw_response.status_code
        if http_code == BadRequestError.HTTP_CODE:
            raise BadRequestError(raw_response.json())
        elif http_code == ForbiddenError.HTTP_CODE:
            raise ForbiddenError(raw_response.json())
        elif http_code == NotFoundError.HTTP_CODE:
            raise NotFoundError(raw_response.json())
        elif http_code == TooManyRequestsError.HTTP_CODE:
            raise TooManyRequestsError(raw_response.json())
        elif http_code == UnauthorizedError.HTTP_CODE:
            raise UnauthorizedError(raw_response.json())
        elif http_code == ResponseProcessingError.HTTP_CODE:
            raise ResponseProcessingError(raw_response.json())
        elif http_code == InternalServerError.HTTP_CODE:
            raise InternalServerError(raw_response.json())
        elif http_code == GoneError.HTTP_CODE:
            raise GoneError(raw_response.json())
        else:
            raise ApiError(raw_response.json())

    @staticmethod
    def get_response_info(response):
        """
        Получение информации из ответа.

        :param response: Объект ответа
        :return: dict[str, Any]
        """
        return {
            "apparent_encoding": response.apparent_encoding,
            "cookies": response.cookies,
            "elapsed": response.elapsed,
            "encoding": response.encoding,
            "is_permanent_redirect": response.is_permanent_redirect,
            "is_redirect": response.is_redirect,
            "ok": response.ok,
            "raise_for_status": response.raise_for_status(),
            "reason": response.reason,
            "status_code": response.status_code,
            "url": response.url,
        }

    def log_request(self, body, method, path, query_params, headers):
        """
        Логирование запроса.

        :param body: Тело запроса
        :param method: HTTP метод
        :param path: URL запроса
        :param query_params: Массив GET параметров запроса
        :param headers: Массив заголовков запроса
        """
        if Configuration.logger:
            context = {}
            if query_params:
                context['_params'] = query_params
            if body:
                context['_body'] = body
            if headers:
                context['_headers'] = headers

            message = 'Send request: {} {} '.format(str(method), self.endpoint + path)
            Configuration.logger.info(message, context=context)

    @staticmethod
    def log_response(body, info, headers):
        """
        Логирование ответа.

        :param body: Тело ответа
        :param info: Массив с данными ответа
        :param headers: Массив заголовков ответа
        """
        if Configuration.logger:
            context = {}
            if body:
                context['_body'] = body
            if headers:
                context['_headers'] = headers

            message = 'Response with code [{}] received.'.format(info['status_code'])
            Configuration.logger.info(message, context=context)
