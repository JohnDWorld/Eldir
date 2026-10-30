"""Schemas Git credentials (PAT GitHub, PAT Forgejo)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, HttpUrl, StringConstraints

from app.schemas.common import EldirModel, TimestampedModel

GitProviderName = Literal["github", "forgejo"]

# Un copier-coller de token ramène très souvent un \n ou une espace en fin.
# Stocké tel quel, le secret partirait dans l'en-tête `Authorization` et
# GitHub répondrait "401 Bad credentials" sans plus d'explication.
SecretInput = Annotated[str, StringConstraints(strip_whitespace=True)]


class GitCredentialCreate(EldirModel):
    provider: GitProviderName
    token: SecretInput = Field(min_length=8, max_length=2048)
    base_url: HttpUrl | None = None  # uniquement pour Forgejo
    label: str | None = Field(default=None, max_length=120)
    # Renseigné, le jeton ne sert qu'à ce projet. Restreins-le aussi côté
    # provider (PAT fine-grained GitHub, jeton par dépôt Forgejo) : Eldir
    # choisit lequel employer, il ne peut pas réduire la portée du secret.
    project_id: str | None = Field(default=None, max_length=36)


class GitCredentialRead(TimestampedModel):
    id: str
    provider: GitProviderName
    base_url: str | None
    label: str | None
    masked_token: str
    project_id: str | None
