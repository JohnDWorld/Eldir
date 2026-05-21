"""Override utilisateur d'un system prompt fourni par Eldir.

Le défaut vit dans `backend/app/data/system_prompts/{slug}.md` (en git,
mis à jour à chaque release). Si l'utilisateur édite, on stocke ici
uniquement l'override - le reset au défaut = supprimer la ligne.
"""

from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class SystemPromptOverride(UUIDPrimaryKey, TimestampMixin, Base):
    """Une ligne par prompt système customisé par l'utilisateur."""

    __tablename__ = "system_prompt_overrides"
    __table_args__ = (UniqueConstraint("slug", name="uq_system_prompt_overrides_slug"),)

    # Identifiant du prompt (ex "template_generator"). Slug filesystem-safe.
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
