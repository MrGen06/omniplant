import base64
import hashlib
import json
import os
import time

from cryptography.fernet import Fernet, InvalidToken


AUTH_COOKIE_NAME = "omniplant_auth"
AUTH_COOKIE_MAX_AGE_SECONDS = 120 * 60


def _get_fernet():
    secret = (
        os.getenv("AUTH_COOKIE_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("STREAMLIT_COOKIE_SECRET")
        or "replace-this-cookie-secret-in-production"
    )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encode_cookie_payload(access_token, user_info):
    payload = {
        "access_token": access_token,
        "user_info": user_info or {},
        "expires_at": int(time.time()) + AUTH_COOKIE_MAX_AGE_SECONDS,
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return _get_fernet().encrypt(raw_payload).decode("utf-8")


def _decode_cookie_payload(cookie_value):
    if not cookie_value:
        return None

    try:
        raw_payload = _get_fernet().decrypt(cookie_value.encode("utf-8"))
        payload = json.loads(raw_payload.decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError, TypeError, ValueError):
        return None

    if payload.get("expires_at", 0) < int(time.time()):
        return None

    if not payload.get("access_token"):
        return None

    return payload


def read_auth_cookie(cookie_controller):
    return _decode_cookie_payload(cookie_controller.get(AUTH_COOKIE_NAME))


def write_auth_cookie(cookie_controller, access_token, user_info):
    cookie_value = _encode_cookie_payload(access_token, user_info)
    cookie_controller.set(
        AUTH_COOKIE_NAME,
        cookie_value,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
    )


def clear_auth_cookie(cookie_controller):
    try:
        cookie_controller.remove(AUTH_COOKIE_NAME)
    except AttributeError:
        cookie_controller.set(AUTH_COOKIE_NAME, "", max_age=0)
