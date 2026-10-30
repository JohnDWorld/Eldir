"""Tests unitaires WorktreeService."""

from __future__ import annotations

from app.services.worktree_service import slugify


def test_slugify_basic() -> None:
    assert slugify("owner/repo-name") == "owner-repo-name"
    assert slugify("Eldir/Mon Projet 1") == "eldir-mon-projet-1"
    assert slugify("--double--dashes--") == "double-dashes"


def test_slugify_empty_fallback() -> None:
    assert slugify("@@@@") == "repo"
    assert slugify("") == "repo"


# Le jeton n'est plus injecté dans les URL : il passe par un credential helper,
# et les tests de cette garde vivent dans `test_jeton_git.py`.
