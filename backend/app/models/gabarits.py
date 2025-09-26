from __future__ import annotations

from sqlalchemy import JSON, Column, Integer, String, Text

from .base import Base


class Gabarit(Base):
    __tablename__ = "gabarits"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    contenu = Column(Text, nullable=False)
    metadonnees = Column("metadata", JSON, nullable=True)
