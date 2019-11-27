
class OperationInfo:
    def __init__(self, nominal: float, identification_number: str, login: str, password: str, terminal: str) -> None:
        self.identification_number = identification_number
        self.nominal = nominal
        self.login = login
        self.password = password
        self.terminal = terminal
        self.inner_id = None
        self.external_id = None
        self.verify_dt = None
        self.create_dt = None
        self.commit_dt = None

    provider_address = 'https://some-url.there/'
    address = 'https://some-url.there/'


class CustomResponse:
    def __init__(self, status_code: int=None, code: int=None, req_type: str=None) -> None:
        self.status_code = status_code
        self.code = code
        self.req_type = req_type
        self.response_data = None
        self.__state = 'Processing'

    @property
    def state(self):
        if self.req_type == 'check':
            if self.code == 0:
                self.__state = 'Success'
            if self.code in (1, 2):
                self.__state = 'Failed'

        if self.req_type == 'payment':
            if self.code == 0:
                self.__state = 'Success'
            if self.code in (1, 2, 3, 4, 5):
                self.__state = 'Failed'

        if self.req_type == 'confirm':
            if self.code == 0:
                self.__state = 'Success'
            if self.code in (1, 2, 3, 4, 5):
                self.__state = 'Failed'

        if self.req_type == 'status':
            if self.code == 0:
                self.__state = 'Success'
            if self.code in (4, 6, 7):
                self.__state = 'Failed'

        if self.req_type == 'cancel':
            if self.code == 0:
                self.__state = 'Success'
            if self.code == 9:
                self.__state = 'Failed'

        return self.__state

