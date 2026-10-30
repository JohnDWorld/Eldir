"""Schemas SystemPrompt (prompts Eldir éditables par l'utilisateur)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import EldirModel


class SystemPromptRead(EldirModel):
    slug: str
    title: str
    description: str
    content: str
    is_overridden: bool
    default_content: str


class SystemPromptWrite(EldirModel):
    content: str = Field(min_length=1)
    # Le texte que l'éditeur avait sous les yeux. Fourni, l'écriture est
    # conditionnée dessus et refusée en 409 si quelqu'un a écrit entre-temps :
    # sans ça, une sauvegarde manuelle efface sans trace la préférence qu'un
    # agent vient d'enregistrer, alors qu'il a reçu « Noté ». Optionnel, pour
    # qu'un appel en ligne de commande puisse encore écraser volontairement.
    base_content: str | None = None
