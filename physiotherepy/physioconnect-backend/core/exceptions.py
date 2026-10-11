"""One consistent error shape for the whole API:

    {"error": {"code": "SLOT_TAKEN", "message": "...", "details": {...}}}

The frontend can then always read `error.code` (for logic) and
`error.message` (to show the user).
"""
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class ApiError(APIException):
    """Raise this anywhere in a view/service to return a clean error."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'ERROR'
    default_detail = 'Something went wrong.'

    def __init__(self, code=None, message=None, status_code=None, details=None):
        self.code = code or self.default_code
        self.message = message or self.default_detail
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=self.message, code=self.code)


def slot_taken():
    return ApiError('SLOT_TAKEN', 'This slot was just booked by someone else. Please pick another time.', 409)


def invalid_slot(message='That time is not available for this doctor.'):
    return ApiError('INVALID_SLOT', message, 422)


def business_rule(code, message):
    """A request that is well-formed but not allowed right now."""
    return ApiError(code, message, 422)


_CODES = {
    400: 'VALIDATION_ERROR',
    401: 'NOT_AUTHENTICATED',
    403: 'PERMISSION_DENIED',
    404: 'NOT_FOUND',
    405: 'METHOD_NOT_ALLOWED',
    429: 'TOO_MANY_REQUESTS',
}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None  # real server bug -> Django shows a 500

    if isinstance(exc, ApiError):
        response.data = {'error': {'code': exc.code, 'message': exc.message, 'details': exc.details}}
        return response

    code = _CODES.get(response.status_code, 'ERROR')
    data = response.data
    if response.status_code == 400:
        message = 'Please check the details you entered.'
        details = data
    else:
        message = data.get('detail', 'Request failed.') if isinstance(data, dict) else str(data)
        details = {}
    response.data = {'error': {'code': code, 'message': str(message), 'details': details}}
    return response
