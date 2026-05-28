from __future__ import annotations

import base64
import binascii
import secrets

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


ADMIN_AUTH_ERROR_DETAIL = {
    "code": "ADMIN_AUTH_REQUIRED",
    "message": "Admin authentication required",
}


def require_admin_auth(request: Request) -> None:
    settings = get_settings()
    if not settings.is_admin_auth_enabled():
        return

    expected_password = settings.admin_password
    supplied_password = _password_from_request(request)
    if not expected_password or not supplied_password:
        raise _unauthorized()
    if not secrets.compare_digest(supplied_password, expected_password):
        raise _unauthorized()


def _password_from_request(request: Request) -> str | None:
    header_password = request.headers.get("X-Admin-Password")
    if header_password:
        return header_password
    return _password_from_basic_auth(request.headers.get("Authorization"))


def _password_from_basic_auth(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, credentials = value.partition(" ")
    if scheme.casefold() != "basic" or not credentials:
        return None
    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    _, separator, password = decoded.partition(":")
    if not separator:
        return None
    return password


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ADMIN_AUTH_ERROR_DETAIL,
        headers={"WWW-Authenticate": "Basic"},
    )
