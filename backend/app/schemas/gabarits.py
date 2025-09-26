from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class GabaritBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nom: str
    description: str | None = None
    contenu: str
    metadonnees: dict[str, Any] | None = None


class GabaritCreate(GabaritBase):
    pass


class GabaritUpdate(BaseModel):
    nom: str | None = None
    description: str | None = None
    contenu: str | None = None
    metadonnees: dict[str, Any] | None = None


class GabaritResponse(GabaritBase):
    id: int
