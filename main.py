from utility_classes import CustomResponse, OperationInfo
import utilities
import global_var

import cx_Oracle
import requests
import inspect
import configparser
import datetime
import time


settings = configparser.ConfigParser()
settings.read('settings.ini')
VERIFICATION_REQUEST_MAX_DURATION = int(settings.get('TIMINGS', 'VERIFICATION_REQUEST_MAX_DURATION'))
PAUSE_BETWEEN_VERIFICATION_REQUEST = int(settings.get('TIMINGS', 'PAUSE_BETWEEN_VERIFICATION_REQUEST'))


def do_verify(op_info: OperationInfo) -> int:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    response = CustomResponse(status_code=None, code=941, req_type='check')

    marker_timestamp = datetime.datetime.now()
    now = datetime.datetime.now()
    while (now - marker_timestamp).seconds < VERIFICATION_REQUEST_MAX_DURATION:
        try:
            token = utilities.auth(op_info)
            if token:
                global_var.log.debug('Token have been set')
                global_var.token = token
            else:
                global_var.log.debug('Not able to authenticate')
                return response.code
            response, runtime = utilities.send_verify_request(op_info)
            if response.state != 'Processing':
                global_var.log.debug(f'Function "do_verify": operation with id {op_info.inner_id} was finished')
                break
        except requests.RequestException:
            global_var.log.exception('Exception in "do_verify", not connected or exception in the request')
        except Exception:
            global_var.log.exception('Exception in "do_verify"')
        global_var.log.debug(f'Function "do_verify": sleeps {PAUSE_BETWEEN_VERIFICATION_REQUEST} secs')
        time.sleep(PAUSE_BETWEEN_VERIFICATION_REQUEST)
        now = datetime.datetime.now()

    op_info.verify_dt = datetime.datetime.now()
    saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
    global_var.log.debug(f'Function "do_verify": response code {response.code} saved into db in {saving_runtime}')
    return response.code


def do_replenishment(op_info: OperationInfo) -> int:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    start_timestamp = datetime.datetime.now()

    # Create payment

    if not op_info.create_dt or not op_info.external_id:
        response = CustomResponse(status_code=None, code=997, req_type='payment')
        try:
            response, runtime = utilities.send_replenishment_request(op_info)
            saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]  # to save op_info.create_dt
            global_var.log.debug(f'Function "do_replenishment": save op_info.create_dt/op_info.confirm_dt, '
                             f'response code {response.code} saved into db in {saving_runtime}')
            return response.code
        except cx_Oracle.DatabaseError as e:
            if e.args[0].code == 20666:
                global_var.log.debug(f'Function "do_replenishment": Operation code {op_info.inner_id} with '
                                 f'external operation number {op_info.external_id} was done and can not be overwritten')
            return
        except Exception:
            global_var.log.exception('Exception in "do_replenishment": Create payment')
            saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
            global_var.log.debug(f'Function "do_replenishment": top up error response code {response.code} '
                             f'saved into db in {saving_runtime}')
            return response.code

    # Confirm

    # Status
    response = CustomResponse(status_code=None, code=997, req_type='status')
    try:
        response, runtime = utilities.send_status_request(op_info)
        saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
        global_var.log.debug(f'Function "do_replenishment": check status stage - '
                         f'response code {response.code} saved into db in {saving_runtime}')
        return response.code
    except cx_Oracle.DatabaseError as e:
        if e.args[0].code == 20666:
            global_var.log.debug(f'Function "do_replenishment": Operation code {op_info.inner_id} with '
                                 f'external operation number {op_info.external_id} was done and can not be overwritten')
            return
    except Exception:
        saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
        global_var.log.debug(f'Function "do_replenishment": check status stage - '
                         f'response code {response.code} saved into db in {saving_runtime}')
        return response.code

    finish_timestamp = datetime.datetime.now()
    global_var.log.info(f'Function "do_replenishment" finished in {finish_timestamp - start_timestamp}')

    return response.code


def do_cancel(op_info: OperationInfo) -> int:
    global_var.log.debug(f'Start function {inspect.currentframe().f_code.co_name}')
    global_var.log.info(f"Trying to cancel payment {op_info.inner_id}")
    response = CustomResponse(status_code=None, code=997, req_type='cancel')
    try:
        response, runtime = utilities.send_cancel_request(op_info)
        saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
        global_var.log.debug(f'Function "do_cancel": check status stage - '
                         f'response code {response.code} saved into db in {saving_runtime}')
    except cx_Oracle.DatabaseError as e:
        if e.args[0].code == 20666:
            global_var.log.debug(f'Function "do_replenishment": Operation code {op_info.inner_id} with external operation'
                             f' number {op_info.external_id} was done and can not be overwritten')
            return
    except Exception:
        global_var.log.exception('Exception in "do_cancel"')
        saving_runtime = utilities.save_response_code_into_db(op_info, response.code)[-1]
        global_var.log.debug(f'Function "do_cancel": check status stage - '
                         f'response code {response.code} saved into db in {saving_runtime}')

    return response.code


def get_balance(op_info):
    pass
