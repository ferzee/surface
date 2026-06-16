import base64
import binascii
import hashlib
import hmac
import json
import os
import time

from django.conf import settings


def _secret():
    return getattr(settings, 'SURFACE_TOKEN_SECRET', 'surface-dev-key-2024').encode()


def create_token(user_id):
    payload_bytes = json.dumps({'u': user_id, 'e': int(time.time() * 1000) + 30 * 24 * 60 * 60 * 1000}).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b'=').decode()
    sig = base64.urlsafe_b64encode(
        hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    ).rstrip(b'=').decode()
    return f'{payload}.{sig}'


def verify_token(token):
    if not token:
        return None
    try:
        dot = token.rfind('.')
        if dot < 0:
            return None
        payload, sig = token[:dot], token[dot + 1:]
        expected = base64.urlsafe_b64encode(
            hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        if not hmac.compare_digest(expected, sig):
            return None
        padded = payload + '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        if data['e'] < time.time() * 1000:
            return None
        return data['u']
    except Exception:
        return None


def hash_password(pw):
    salt = binascii.hexlify(os.urandom(16)).decode()
    h = hashlib.pbkdf2_hmac('sha512', pw.encode(), salt.encode(), 100000, 64)
    return f'{salt}:{binascii.hexlify(h).decode()}'


def check_password(pw, stored):
    parts = stored.split(':', 1)
    if len(parts) != 2:
        return False
    salt, expected_hash = parts
    h = hashlib.pbkdf2_hmac('sha512', pw.encode(), salt.encode(), 100000, 64)
    return hmac.compare_digest(binascii.hexlify(h).decode(), expected_hash)
