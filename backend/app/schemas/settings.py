from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel


class SettingResponse(BaseModel):
    key: str
    value: Optional[str]
    updated_at: datetime

    class Config:
        orm_mode = True


class SettingsPayload(BaseModel):
    data: Dict[str, str]
