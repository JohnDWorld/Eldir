"""OllamaSettings - singleton avec les préférences user-level pour Ollama.

L'URL et le modèle par défaut viennent de l'env (Settings du backend).
Cette table sert uniquement aux préférences MUTABLES depuis l'UI :
- expose_to_sessions : le sub-agent 'mask-data' doit-il être injecté
  automatiquement dans chaque template de session ?

Singleton : on a UNE seule ligne (id='singleton'), comme SetupState.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class OllamaSettings(TimestampMixin, Base):
    """Singleton. id fixé à 'singleton'."""

    __tablename__ = "ollama_settings"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="singleton")
    # Si True, on injecte automatiquement le sub-agent 'mask-data' dans
    # chaque session Claude pour exposer Ollama comme outil délégable.
    expose_to_sessions: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
