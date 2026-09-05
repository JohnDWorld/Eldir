"""Schemas Claude credentials."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.schemas.common import EldirModel, TimestampedModel

ClaudeCredentialKind = Literal["oauth_token", "api_key"]

# Cf. app.schemas.git_credential : un secret collé depuis un navigateur
# arrive régulièrement avec un saut de ligne. On le retire à l'entrée.
SecretInput = Annotated[str, StringConstraints(strip_whitespace=True)]


# Préfixes connus d'Anthropic. Une valeur au préfixe inconnu passe sans
# broncher : le jour où le format change, Eldir ne doit pas bloquer.
_OAUTH_PREFIX = "sk-ant-oat"
_API_KEY_PREFIX = "sk-ant-api"


class ClaudeCredentialCreate(EldirModel):
    kind: ClaudeCredentialKind
    value: SecretInput = Field(min_length=8, max_length=4096)
    label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _kind_matches_value(self) -> "ClaudeCredentialCreate":
        """Refuse une clé API rangée en token OAuth, et l'inverse.

        Se tromper de mode ne se voit pas au moment de la saisie : la valeur
        est acceptée, chiffrée, puis injectée dans la mauvaise variable
        d'environnement. L'erreur ne remonte que plus tard, au milieu d'une
        session, sous la forme "401 OAuth access token is invalid".
        """
        if self.kind == "oauth_token" and self.value.startswith(_API_KEY_PREFIX):
            raise ValueError(
                "Cette valeur est une clé API Console (préfixe sk-ant-api). "
                "Choisis le mode « Clé API » plutôt que « Token Pro/Max »."
            )
        if self.kind == "api_key" and self.value.startswith(_OAUTH_PREFIX):
            raise ValueError(
                "Cette valeur est un token Pro/Max (préfixe sk-ant-oat). "
                "Choisis le mode « Token Pro/Max » plutôt que « Clé API »."
            )
        return self


class ClaudeCredentialRead(TimestampedModel):
    """Vue safe - JAMAIS le secret en clair."""

    id: str
    kind: ClaudeCredentialKind
    label: str | None
    is_active: bool
    last_validated_at: datetime | None
    masked_value: str  # ex. "sk-ant-…aB12" (4 derniers chars)


class ClaudeCredentialUpdate(EldirModel):
    label: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
