"""Le jeton de session ne finit pas dans les journaux d'uvicorn."""

from __future__ import annotations

import logging

from app.core.logging import MasqueJeton, configure_logging


def _ligne(nom: str, message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(nom, logging.INFO, __file__, 1, message, args, None)


def test_le_jeton_d_une_websocket_est_masque() -> None:
    configure_logging()
    configure_logging()  # deux fois : un seul filtre, pas deux
    for nom in ("uvicorn.error", "uvicorn.access"):
        filtres = logging.getLogger(nom).filters
        assert sum(isinstance(f, MasqueJeton) for f in filtres) == 1, nom

    # Les WebSocket passent par `uvicorn.error`.
    ws = _ligne(
        "uvicorn.error",
        '%s - "WebSocket %s" [accepted]',
        "1.2.3.4:5",
        "/ws/sessions/abc?token=eyJ.secret.sig",
    )
    assert logging.getLogger("uvicorn.error").filter(ws)
    assert ws.getMessage() == '1.2.3.4:5 - "WebSocket /ws/sessions/abc?token=***" [accepted]'

    acces = _ligne(
        "uvicorn.access",
        '%s - "%s %s HTTP/%s" %d',
        "1.2.3.4:5",
        "GET",
        "/x?a=1&token=eyJ.s&b=2",
        "1.1",
        200,
    )
    assert logging.getLogger("uvicorn.access").filter(acces)
    assert "/x?a=1&token=***&b=2" in acces.getMessage()
    # Le formateur d'accès d'uvicorn dépaquette cinq arguments : la forme reste.
    assert isinstance(acces.args, tuple) and len(acces.args) == 5
