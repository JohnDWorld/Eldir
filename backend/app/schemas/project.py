"""Schemas Project."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import EldirModel, TimestampedModel

ProviderName = Literal["github", "forgejo"]


class ProjectCreateFromRepo(EldirModel):
    """Payload pour cloner un repo existant et en faire un projet Eldir."""

    provider: ProviderName
    repo_full_name: str = Field(min_length=3, max_length=255)  # owner/repo
    display_name: str | None = Field(default=None, max_length=120)


class ProjectRead(TimestampedModel):
    id: str
    name: str
    slug: str
    provider: ProviderName
    repo_full_name: str
    default_branch: str
    workspace_path: str | None


class ProjectSummary(EldirModel):
    """Vue compacte pour la liste mobile (D1 Mission Control)."""

    id: str
    name: str
    slug: str
    provider: ProviderName
    branch: str
    active_sessions: int = 0
    last_activity_at: str | None = None


class RemoteRepoRead(EldirModel):
    """Repo distant retourné par GitProvider.list_repos."""

    full_name: str
    default_branch: str
    clone_url: str
    description: str | None
    is_private: bool


class RemoteRepoCreate(EldirModel):
    """Payload pour créer un nouveau repo distant (et le projet associé)."""

    provider: ProviderName
    name: str = Field(min_length=1, max_length=120)
    private: bool = True
    description: str | None = Field(default=None, max_length=512)
    create_project: bool = True
