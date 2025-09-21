from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class TokenPayload(BaseModel):
    sub: str
    exp: int


class LoginRequest(BaseModel):
    username: constr(strip_whitespace=True, min_length=1)
    password: constr(strip_whitespace=True, min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: constr(min_length=8)
