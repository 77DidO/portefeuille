from __future__ import annotations

import base64
import os
from typing import Tuple

from cryptography.fernet import Fernet
from hashlib import sha256

from app.core.config import settings


def _derive_key(secret: str) -> bytes:
    digest = sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    return Fernet(_derive_key(settings.app_secret))


def encrypt(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(value: str) -> str:
    return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
