"""Configuration du logging structuré (structlog)."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure structlog + stdlib logging pour toute l'application."""
    settings = get_settings()
    level = logging.DEBUG if settings.app_debug else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    # httpx journalise chaque requête en INFO, URL complète comprise. Celle d'un
    # abonné au ping de fin de tour peut porter un jeton.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.is_dev:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def journaliser_le_refus(
    logger: structlog.stdlib.BoundLogger,
    evenement: str,
    *,
    methode: str,
    chemin: str,
    status: int,
    **champs: Any,
) -> None:
    """Trace le refus d'une API appelée en sortie.

    Les journaux de requêtes d'`httpx` sont muselés juste au-dessus : sans cette
    ligne, un refus d'une API distante ne laisse aucune trace côté serveur, et
    l'exception levée n'est tracée nulle part non plus. Le chemin, jamais l'URL
    complète : l'URL de base ou ses paramètres peuvent porter un jeton.

    Le logger est passé par l'appelant, pas pris ici : chaque module garde le
    sien, et c'est celui-là que ses tests observent.
    """
    logger.warning(evenement, methode=methode, chemin=chemin, status=status, **champs)
