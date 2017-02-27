"""
errors and exceptions
"""
from sanic.exceptions import SanicException


class RateLimitExceeded(SanicException):
    status_code = 429

    def __init__(self, message=None):
        message = message or 'too many requests'
        super().__init__(message)
