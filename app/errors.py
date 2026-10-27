class DomainError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def require(condition, status, code, message):
    if not condition:
        raise DomainError(status, code, message)
