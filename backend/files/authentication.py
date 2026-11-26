import re

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

USER_ID_HEADER = 'UserId'
_USER_ID_PATTERN = re.compile(r'^[\w.@+-]{1,255}$')


class HeaderUser:
    """Minimal authenticated principal identified only by the UserId header."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, user_id):
        self.user_id = user_id
        self.pk = user_id

    def __str__(self):
        return self.user_id


class UserIdHeaderAuthentication(BaseAuthentication):
    """
    Identifies the caller from the `UserId` request header.

    This is identification, not authentication: in production this would sit
    behind a gateway that validates a real credential and injects the header.
    """

    def authenticate(self, request):
        user_id = request.headers.get(USER_ID_HEADER, '').strip()
        if not user_id:
            raise AuthenticationFailed(f'{USER_ID_HEADER} header is required')
        if not _USER_ID_PATTERN.match(user_id):
            raise AuthenticationFailed(
                f'{USER_ID_HEADER} must be 1-255 characters: letters, digits, or . @ + - _'
            )
        return HeaderUser(user_id), None

    def authenticate_header(self, request):
        # Makes DRF return 401 (not 403) when the header is missing.
        return USER_ID_HEADER
