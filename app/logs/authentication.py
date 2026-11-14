
import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class LogShiftAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate log producers using the X-API-Key request header.
    """

    def authenticate(self, request):
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            raise AuthenticationFailed("API key is required.")

        expected_key = settings.LOGSHIFT_INGEST_API_KEY

        if not expected_key:
            raise AuthenticationFailed(
                "API key authentication is not configured."
            )

        if not secrets.compare_digest(provided_key, expected_key):
            raise AuthenticationFailed("Invalid API key.")

        return (None, provided_key)

    def authenticate_header(self, request):
        return "X-API-Key"
