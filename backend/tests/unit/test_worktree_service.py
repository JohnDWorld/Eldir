"""Tests unitaires WorktreeService."""

from __future__ import annotations

from app.services.worktree_service import _inject_token, slugify


def test_slugify_basic() -> None:
    assert slugify("owner/repo-name") == "owner-repo-name"
    assert slugify("Eldir/Mon Projet 1") == "eldir-mon-projet-1"
    assert slugify("--double--dashes--") == "double-dashes"


def test_slugify_empty_fallback() -> None:
    assert slugify("@@@@") == "repo"
    assert slugify("") == "repo"


def test_inject_token_https() -> None:
    url = _inject_token("https://github.com/owner/repo.git", "ghp_abc")
    assert url == "https://x-access-token:ghp_abc@github.com/owner/repo.git"


def test_inject_token_ssh_passthrough() -> None:
    # On ne touche pas aux URL SSH (git@github.com:...).
    assert (
        _inject_token("git@github.com:owner/repo.git", "ghp_abc") == "git@github.com:owner/repo.git"
    )
