import datetime
import requests
import configparser
import xmltodict
import time
import inspect
from typing import Callable
import logging
from logging.handlers import TimedRotatingFileHandler

import global_var
from utility_classes import OperationInfo, CustomResponse


settings = configparser.ConfigParser()
settings.read('settings.ini')
AUTHORIZATION_ATTEMPTS = int(settings.get('TIMINGS', 'AUTHORIZATION_ATTEMPTS'))
AUTHORIZATION_REQUESTS_MAX_DURATION = int(settings.get('TIMINGS', 'AUTHORIZATION_REQUESTS_MAX_DURATION'))
VERIFICATION_REQUEST_HTTP_TIMEOUT = int(settings.get('TIMINGS', 'VERIFICATION_REQUEST_HTTP_TIMEOUT'))
PAY_REQUEST_HTTP_TIMEOUT = int(settings.get('TIMINGS', 'PAY_REQUEST_HTTP_TIMEOUT'))
CONFIRM_REQUEST_HTTP_TIMEOUT = int(settings.get('TIMINGS', 'CONFIRM_REQUEST_HTTP_TIMEOUT'))
STATUS_REQUEST_HTTP_TIMEOUT = int(settings.get('TIMINGS', 'STATUS_REQUEST_HTTP_TIMEOUT'))
TRANSACTION_ID_REQUESTS_MAX_DURATION = int(settings.get('TIMINGS', 'TRANSACTION_ID_REQUESTS_MAX_DURATION'))
PAY_REQUESTS_MAX_DURATION = int(settings.get('TIMINGS', 'PAY_REQUESTS_MAX_DURATION'))
CHECK_STATUS_REQUESTS_MAX_DURATION = int(settings.get('TIMINGS', 'CHECK_STATUS_REQUESTS_MAX_DURATION'))
CONFIRM_OPERATION_REQUESTS_MAX_DURATION = int(settings.get('TIMINGS', 'CONFIRM_OPERATION_REQUESTS_MAX_DURATION'))
PAUSE_BETWEEN_TRANSACTION_ID_REQUEST = int(settings.get('TIMINGS', 'PAUSE_BETWEEN_TRANSACTION_ID_REQUEST'))
PAUSE_BETWEEN_PAY_REQUESTS = int(settings.get('TIMINGS', 'PAUSE_BETWEEN_PAY_REQUESTS'))
PAUSE_BETWEEN_CHECK_STATUS_REQUEST = int(settings.get('TIMINGS', 'PAUSE_BETWEEN_CHECK_STATUS_REQUEST'))
PAUSE_BETWEEN_CONFIRM_OPERATION_REQUEST = int(settings.get('TIMINGS', 'PAUSE_BETWEEN_CONFIRM_OPERATION_REQUEST'))


def runtime_decorator(func: Callable) -> Callable:
    def wrapper(*args, **kwargs) -> tuple:
        sdt = datetime.datetime.now()
        result = func(*args, **kwargs)
        fdt = datetime.datetime.now()
        runtime = fdt - sdt
        return result, runtime
    return wrapper


def auth(op_info: OperationInfo, via_proxy=True) -> str:
    token = None

    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    address = f"{get_provider_address(op_info)}user/login"
    payload = {
        "login": op_info.login,
        "password": op_info.password,
        "terminal": op_info.terminal,
    }
    if via_proxy is True:
        proxy = get_proxy_address(op_info)
    else:
        proxy = None

    for i in range(AUTHORIZATION_ATTEMPTS):
        try:
            response, runtime = request_factory(address, payload, headers={}, proxies=proxy, method="POST",
                                             timeout=AUTHORIZATION_REQUESTS_MAX_DURATION, req_type="auth")
            token = response.response_data.get('token')
            if token:
                global_var.log.debug(f'Function {inspect.currentframe().f_code.co_name}: Authorization successful')
                break
        except Exception:
            global_var.log.exception(f'Exception in {inspect.currentframe().f_code.co_name}')

    return token


def send_verify_request(op_info: OperationInfo) -> CustomResponse:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    req_type = 'check'
    address = f'{get_provider_address(op_info)}?action={req_type}&number={op_info.identification_number}'
    headers = {'Content-Type': 'application/xml', 'Authorization': global_var.token}

    response, runtime = request_factory(address, payload=None, headers=headers, method="GET",
                                        proxies=get_proxy_address(op_info), timeout=VERIFICATION_REQUEST_HTTP_TIMEOUT,
                                        req_type=req_type)

    global_var.log.debug(f'Function "send_verify_request": response data {response.response_data}, '
                     f'response status code {response.status_code}, received response in {runtime}')
    return response


def send_replenishment_request(op_info: OperationInfo) -> CustomResponse:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    response = None

    req_type = 'payment'
    amount = op_info.nominal/100
    date_now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    address = f'{get_provider_address(op_info)}?action={req_type}&number={op_info.identification_number}' \
              f'&amount={amount:0.2f}&receipt={op_info.inner_id}&date={date_now}'
    headers = {'Content-Type': 'application/xml', 'Authorization': global_var.token}

    try:
        response, runtime = cycle(
            request_factory,
            pause=PAUSE_BETWEEN_PAY_REQUESTS,
            max_duration=PAY_REQUESTS_MAX_DURATION,
            **{"address": address, "payload": None, "headers": headers, "method": "GET",
               "proxies": get_proxy_address(op_info), "timeout": PAY_REQUEST_HTTP_TIMEOUT, "req_type": req_type}
        )
        if response.state == 'Success':
            op_info.create_dt = op_info.commit_dt = datetime.datetime.now()
            op_info.external_id = response.response_data.get('authcode')
            global_var.log.debug(f'OpInfo: create_dt and commit_dt was set to {op_info.create_dt}, '
                             f'external_id was set to {op_info.external_id}')
    except Exception:
        global_var.log.exception(f'Exception in {inspect.currentframe().f_code.co_name}')

    global_var.log.debug(f'After ladle send_replenishment_request {response.response_data}, '
                     f'{response.status_code}')
    return response


def send_confirm_request(op_info: OperationInfo):
    pass


def send_status_request(op_info: OperationInfo) -> CustomResponse:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    response = None
    req_type = 'status'
    address = f'{get_provider_address(op_info)}?action={req_type}&receipt={op_info.inner_id}'
    headers = {'Content-Type': 'application/xml', 'Authorization': global_var.token}

    try:
        response, runtime = cycle(
            request_factory,
            pause=PAUSE_BETWEEN_CHECK_STATUS_REQUEST,
            max_duration=CHECK_STATUS_REQUESTS_MAX_DURATION,
            **{"address": address, "payload": None, "headers": headers, "method": "GET",
               "proxies": get_proxy_address(op_info), "timeout": STATUS_REQUEST_HTTP_TIMEOUT, "req_type": req_type}
        )
        global_var.log.debug(f'After check_status_operation ladle {response.response_data}, '
                         f'{response.status_code}')
    except Exception:
        global_var.log.exception(f'Exception in {inspect.currentframe().f_code.co_name}')

    return response


def send_cancel_request(op_info: OperationInfo) -> CustomResponse:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    req_type = 'cancel'
    address = f'{get_provider_address(op_info)}?action={req_type}&receipt={op_info.inner_id}'
    headers = {'Content-Type': 'application/xml', 'Authorization': global_var.token}

    response, runtime = request_factory(address, payload=None, headers=headers, method="GET",
                                        proxies=get_proxy_address(op_info), req_type=req_type)

    global_var.log.debug(f'Function "send_cancel_request": response data {response.response_data}, '
                     f'response status code {response.status_code}, received response in {runtime}')
    return response


def send_balance_request(op_info):
    pass


def get_provider_address(op_info: OperationInfo) -> str:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    address = ""
    if hasattr(op_info, 'provider_address'):
        address = op_info.provider_address
    if hasattr(op_info, 'address'):
        address = op_info.address
    return address


def get_proxy_address(op_info: OperationInfo) -> dict:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    proxy_address = None
    dict_ = {}
    try:
        proxy_name = global_var.config.get('Proxy', 'proxy_param')
    except KeyError:
        raise Exception('No connections via proxy, no proxy_name parameter found.')

    if hasattr(op_info, 'module_params'):
        if not op_info.module_params.get(proxy_name) or proxy_name not in op_info.module_params:
            proxy_address = None
        else:
            proxy_address = op_info.module_params[proxy_name]
    if hasattr(op_info, 'params'):
        if not op_info.params.get(proxy_name) or proxy_name not in op_info.params:
            proxy_address = None
        else:
            proxy_address = op_info.params[proxy_name]
    if proxy_address:
        dict_ = {'http': proxy_address, 'https': proxy_address}
    return dict_


@runtime_decorator
def cycle(func: Callable, pause: int=2, max_duration: int=30, *args, **kwargs) -> CustomResponse:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    marker_timestamp = datetime.datetime.now()
    now = datetime.datetime.now()
    response = None
    while (now - marker_timestamp).seconds < max_duration:
        try:
            response, runtime = func(*args, **kwargs)
            if response:
                if response.state != 'Processing':
                    return response
            global_var.log.debug(f'Ladle "{func.__name__}", cyclical get')
        except Exception:
            global_var.log.exception('Exception in ladle cycle')
        global_var.log.debug(f'Ladle sleeps {pause} secs')
        time.sleep(pause)
        now = datetime.datetime.now()
    global_var.log.error(f'Timeout max duration in ladle, cyclical: {func.__name__}')
    return response


@runtime_decorator
def request_factory(address: str, payload: dict=None, headers: dict=None, method: str='POST',
                    proxies: dict=None, timeout: int=30, verify: bool=False, req_type: str="") -> CustomResponse:

    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    headers_payload = ""
    if headers:
        headers_payload = ''

    logging_payload = ""
    if payload:
        logging_payload = payload

    global_var.log.debug(f'Req type: {req_type}, Request with arguments: '
                     f'URL: {address} Headers: {headers_payload} Payload: {logging_payload} '
                     f'Method: {method} Proxies: {proxies} Timeout: {timeout} Verify: {verify}')

    if method == 'POST':
        response = requests.post(address, data=payload, headers=headers, proxies=proxies, timeout=timeout,
                                 verify=verify)
    elif method == 'GET':
        response = requests.get(address, headers=headers, proxies=proxies, timeout=timeout, verify=verify)
    elif method == 'PUT':
        response = requests.put(address, data=payload, headers=headers, proxies=proxies, timeout=timeout, verify=verify)
    elif method == 'DELETE':
        response = requests.delete(address, headers=headers, proxies=proxies, timeout=timeout, verify=verify)
    else:
        raise Exception(f'"{method}" method is not supported. Only "POST", "GET", "PUT", "DELETE" methods are provided')

    data = parse_xml_data(response)
    custom_response = CustomResponse(response.status_code, data.get('code'), req_type)
    custom_response.response_data = data

    global_var.log.debug(f'Rec type: {req_type},'
                     f'Response content: {data} Response status code: {response.status_code}')

    return custom_response


def parse_xml_data(response: requests.Response) -> dict:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    data = None
    try:
        data = xmltodict.parse(response.text).get('response')
        global_var.log.debug(f'Parsed XML, received: {data}')
    except Exception:
        global_var.log.exception('Exception in "parse_xml_data"')
    return data


@runtime_decorator
def save_response_code_into_db(op_info: OperationInfo, response_code: int) -> None:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    # with glob.get_db_connection() as conn:
    #     op_info.save_to_db(conn, response_code)
    #     glob.release_db_connection(conn)
    print('Response code saved into DB', response_code)


@runtime_decorator
def save_balance_into_db(op_info: OperationInfo, balance: float, overdraft: float) -> None:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    # with glob.get_db_connection() as conn:
    #     op_info.save_to_db_ex(conn, balance, overdraft)
    print('Balance:', balance, ' Overdraft:', overdraft)


def create_logger() -> None:
    global_var.log = logging.getLogger('logger')
    log_name = "C://Users//root//PycharmProjects//payment_gateway//LOGS//log"
    handler = TimedRotatingFileHandler(log_name, when="midnight", interval=1)
    handler.suffix = "%Y%m%d"
    formatter = logging.Formatter('[%(asctime)s][%(threadName)s][%(funcName)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    global_var.log.addHandler(handler)
    global_var.log.addHandler(stream_handler)
    global_var.log.setLevel(logging.DEBUG)

