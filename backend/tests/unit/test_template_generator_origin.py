"""Le prompt de génération d'un Mission Template vient d'Eldir, pas de John.

`send_message` signe « John » tout message dont on ne dit pas l'origine. Le prompt
d'analyse qu'Eldir envoie à sa propre session de génération ne doit pas finir dans
le fil sous le nom de John.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from typing import Any

import pytest
from app.core.constants import MESSAGE_ORIGIN_ELDIR
from app.core.exceptions import EldirError
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.template_generator_service import TemplateGeneratorService


class _ManagerEspion(SessionManager):
    """Note à qui et sous quelle origine on écrit, sans démarrer de SDK."""

    def __init__(self) -> None:
        super().__init__(event_bus=EventBus(redis=None))  # type: ignore[arg-type]
        self.recus: list[tuple[str, str]] = []

    async def send_message(  # type: ignore[override]
        self, session_id: str, content: str, *, origin: str, place_reservee: bool = False
    ) -> None:
        self.recus.append((session_id, origin))


class _BusQuiFinitLeTour:
    """Publie tout de suite le STOP : `_run_generation` n'attend pas son délai."""

    async def subscribe(self, _session_id: str) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "stop", "data": {}}


async def test_le_prompt_de_generation_est_signe_eldir() -> None:
    manager = _ManagerEspion()
    generator = TemplateGeneratorService(manager=manager, event_bus=_BusQuiFinitLeTour())  # type: ignore[arg-type]

    # Le bus n'a rien publié d'autre que le STOP : pas de bloc <preset>, donc le
    # résultat est refusé. C'est sans importance ici, seul l'envoi est regardé.
    with pytest.raises(EldirError):
        await generator._run_generation("s1", "munin")

    assert manager.recus == [("s1", MESSAGE_ORIGIN_ELDIR)]


def test_send_message_n_a_pas_d_origine_par_defaut() -> None:
    """Un défaut `user` signerait « John » tout appel qui oublie de dire qui parle."""
    origine = inspect.signature(SessionManager.send_message).parameters["origin"]
    assert origine.default is inspect.Parameter.empty
