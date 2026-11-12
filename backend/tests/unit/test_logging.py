"""Le jeton de session ne finit pas dans les journaux d'uvicorn."""

from __future__ import annotations

import logging

import pytest
from app.core.logging import configure_logging


def test_le_jeton_d_une_websocket_est_masque(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging()
    configure_logging()  # deux fois : un seul filtre, pas deux
    assert len(logging.getLogger("uvicorn.error").filters) == 1

    with caplog.at_level(logging.INFO):
        logging.getLogger("uvicorn.error").info(
            '%s - "WebSocket %s" [accepted]', "1.2.3.4:5", "/ws/sessions/abc?token=eyJ.secret.sig"
        )
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "1.2.3.4:5", "GET", "/x?a=1&token=eyJ.s&b=2", "1.1", 200
        )

    assert "eyJ" not in caplog.text
    assert "/ws/sessions/abc?token=***" in caplog.text
    assert "/x?a=1&token=***&b=2" in caplog.text
    # Le formateur d'accès d'uvicorn dépaquette cinq arguments : la forme reste.
    assert len(caplog.records[-1].args) == 5
