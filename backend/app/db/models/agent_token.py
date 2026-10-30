"""Jeton longue durée d'un agent externe branché sur Eldir.

Le jeton lui-même est un JWT signé par la clé de l'instance : il se vérifie
sans la base. Cette table existe pour une seule raison, la révocation. Un
agent tourne en continu et ne peut pas se reconnecter derrière un formulaire,
donc son jeton vit des mois ; sans moyen de le couper, on ne pourrait pas
l'émettre. Le `jti` est la liste blanche, pas un journal.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class AgentToken(UUIDPrimaryKey, TimestampMixin, Base):
    """Une ligne par jeton émis, y compris révoqué (on garde la trace)."""

    __tablename__ = "agent_tokens"
    __table_args__ = (
        UniqueConstraint("jti", name="uq_agent_tokens_jti"),
        # Un seul jeton vivant par libellé : c'est le libellé qui dit qui a
        # décidé, dans les pings comme dans le fil, et la révocation est par
        # jeton. Partielle, pour que réémettre après révocation garde le même
        # nom (c'est le geste de secours documenté quand un jeton a fuité).
        Index(
            "uq_agent_tokens_user_label_vivant",
            "user_id",
            "label",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    # CASCADE comme partout ailleurs : supprimer un utilisateur coupe ses jetons.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Nom donné par John, affiché dans l'origine des messages dispatchés :
    # en relisant son historique il doit savoir lequel des cerveaux a parlé.
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    # Pas d'`index=True` : la contrainte d'unicité du `__table_args__` crée déjà
    # l'index qui sert la recherche par `jti`.
    jti: Mapped[str] = mapped_column(String(36), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
