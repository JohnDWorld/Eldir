"""Schémas de la mémoire des agents : les préférences qu'ils ont écrites dans le
prompt du superviseur, avec les bornes qui s'y appliquent."""

from __future__ import annotations

from app.schemas.common import EldirModel


class AgentMemoryEntry(EldirModel):
    # Le nom du jeton qui a écrit la ligne : posé par Eldir, jamais lu dans le texte.
    agent: str
    text: str
    # La ligne telle que stockée dans le prompt. C'est elle qui désigne l'entrée
    # pour la retirer : un rang se décalerait si la liste a bougé entre-temps.
    line: str


class AgentMemoryRead(EldirModel):
    entries: list[AgentMemoryEntry]
    # Les bornes que `remember` applique, lues sur ses constantes : l'interface
    # ne les recopie pas.
    max_entries: int
    max_length: int


class AgentMemoryForget(EldirModel):
    line: str
