"""Lecture du compte rendu `<cr>` d'une session enfant.

Le protocole enfant impose un bloc de fin de tour :

    <cr>
    FAIT: ...
    FICHIERS: ...
    RESTE: ...
    BLOCAGE: ...   (facultatif)
    PRET: oui|non
    </cr>

C'est le seul endroit où l'agent dit ce qu'il attend. Les fonctions vivent
ici, et pas dans un service, parce que le gestionnaire de sessions et le
service de sessions en ont tous les deux besoin : les mettre dans l'un des
deux créait un cycle d'imports.
"""

from __future__ import annotations

import re

from app.core.constants import (
    SESSION_STATE_BLOCKED,
    SESSION_STATE_IDLE,
    SESSION_STATE_WAITING_INPUT,
)

# Le dernier bloc gagne : le superviseur ne relit que le dernier passage, ce
# qui garde sa relecture à coût constant.
_CR_RE: re.Pattern[str] = re.compile(r"<cr>(.*?)</cr>", re.DOTALL | re.IGNORECASE)
_CR_MAX_CHARS = 4_000

_BLOCAGE_RE: re.Pattern[str] = re.compile(
    r"^[^\S\n]*BLOCAGE[^\S\n]*:(.*)$", re.IGNORECASE | re.MULTILINE
)
# Le protocole demande « aucun » quand rien ne bloque : la ligne est remplie,
# mais ce n'est pas un blocage. La valeur entière est comparée, pas son début :
# « aucun accès à la base » en est un.
_SANS_BLOCAGE = frozenset({"", "aucun", "aucune", "rien", "néant", "none", "non", "-"})
_PRET_OUI_RE: re.Pattern[str] = re.compile(
    r"^[^\S\n]*PRET[^\S\n]*:[^\S\n]*oui", re.IGNORECASE | re.MULTILINE
)


def extract_cr(text: str) -> str | None:
    """Renvoie le contenu du dernier bloc <cr> d'un texte, ou None."""
    matches = _CR_RE.findall(text)
    if not matches:
        return None
    cr = matches[-1].strip()
    return cr[:_CR_MAX_CHARS] if cr else None


def state_after_turn(cr: str | None) -> str:
    """État d'une session quand son tour se termine.

    - `BLOCAGE:` renseigné (autrement que par « aucun ») : la session est
      bloquée, John doit trancher ;
    - `PRET: oui` : le travail attend sa relecture et sa publication ;
    - sinon la session dort.

    Sans cette lecture, `blocked` et `waiting_input` n'étaient émis nulle
    part : les compteurs « bloquées » et « à toi » du dashboard restaient à
    zéro quoi qu'il arrive, et une session arrêtée net sur un blocage
    ressemblait à une session terminée.
    """
    if cr is None:
        return SESSION_STATE_IDLE
    if any(
        valeur.strip().strip("\"'«».").strip().lower() not in _SANS_BLOCAGE
        for valeur in _BLOCAGE_RE.findall(cr)
    ):
        return SESSION_STATE_BLOCKED
    if _PRET_OUI_RE.search(cr):
        return SESSION_STATE_WAITING_INPUT
    return SESSION_STATE_IDLE
