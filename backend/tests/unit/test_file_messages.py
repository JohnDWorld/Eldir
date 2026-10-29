"""Plafond de la file d'attente d'une session.

`message_lock` sérialise déjà les tours : un second message attend la fin du
premier, il n'est pas perdu. Ce qui manquait est une borne. Un agent parti en
boucle empilerait des centaines de consignes que personne ne relira, et la
mémoire du conteneur avec. Au-delà du plafond, le refus doit être lisible par
l'agent, pas un 500.
"""

from __future__ import annotations

import pytest
from app.core.exceptions import SessionQueueFullError
from app.services.session_manager import ActiveSession


def _session() -> ActiveSession:
    return ActiveSession(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")


def test_une_session_neuve_a_une_file_vide() -> None:
    assert _session().en_attente == 0


def test_le_plafond_refuse_le_message_de_trop() -> None:
    active = _session()
    active.en_attente = 3
    with pytest.raises(SessionQueueFullError) as exc:
        active.reserver_place(plafond=3)
    assert "3" in exc.value.message, "le refus doit dire le plafond atteint"
    assert active.en_attente == 3, "un refus ne consomme pas de place"


def test_sous_le_plafond_la_place_est_prise_et_rendue() -> None:
    active = _session()
    active.reserver_place(plafond=3)
    assert active.en_attente == 1
    active.rendre_place()
    assert active.en_attente == 0


def test_rendre_une_place_deja_rendue_n_ouvre_pas_la_vanne() -> None:
    """Sinon un double appel ferait passer le compteur sous zéro et le
    plafond laisserait entrer plus de messages qu'il n'en autorise."""
    active = _session()
    active.rendre_place()
    assert active.en_attente == 0
