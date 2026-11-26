from rest_framework import status
from rest_framework.exceptions import APIException, Throttled
from rest_framework.views import exception_handler as drf_exception_handler

CALL_LIMIT_MESSAGE = 'Call Limit Reached'
STORAGE_QUOTA_MESSAGE = 'Storage Quota Exceeded'


class StorageQuotaExceeded(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = STORAGE_QUOTA_MESSAGE
    default_code = 'storage_quota_exceeded'


def api_exception_handler(exc, context):
    """
    Wrap DRF's handler so every error that carries a single message comes back
    as {"error": "<message>"}, matching the API's existing error shape.
    Field-level validation errors keep DRF's {"field": ["msg"]} structure.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, Throttled):
        response.data = {'error': CALL_LIMIT_MESSAGE}
    elif isinstance(response.data, dict) and set(response.data) == {'detail'}:
        response.data = {'error': str(response.data['detail'])}
    return response
