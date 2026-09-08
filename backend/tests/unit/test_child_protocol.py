"""Protocole enfant : extraction du <cr> et refus de publication.

Deux briques minuscules mais critiques : si l'extraction du <cr> casse, le
superviseur relit du vide ; si le refus casse, un agent publie sans validation.
"""

from __future__ import annotations

from app.services.session_manager import _denies_publish, _publish_denial
from app.services.session_service import extract_cr


def test_extract_cr_prend_le_dernier_bloc() -> None:
    text = "blabla\n<cr>\nFAIT: v1\n</cr>\nsuite\n<cr>FAIT: v2</cr>"
    assert extract_cr(text) == "FAIT: v2"


def test_extract_cr_multiligne() -> None:
    cr = extract_cr("réponse\n\n<cr>\nFAIT: a\nFICHIERS: b.py\nPRET: oui\n</cr>")
    assert cr is not None
    assert cr.splitlines() == ["FAIT: a", "FICHIERS: b.py", "PRET: oui"]


def test_extract_cr_absent_ou_vide() -> None:
    assert extract_cr("aucun compte rendu ici") is None
    assert extract_cr("<cr>   </cr>") is None


def test_denies_publish_bloque_push_commit_et_pr() -> None:
    for command in (
        "git push origin main",
        "git commit -m 'wip'",
        "git status && git push",
        "git -C /tmp/repo push",
        "gh pr create --fill",
        "glab mr create",
        "GIT_AUTHOR_NAME=x git commit --amend",
    ):
        assert _denies_publish("Bash", {"command": command}), command


def test_denies_publish_laisse_passer_la_lecture() -> None:
    for command in (
        "git status",
        "git diff --stat",
        "git log --oneline -5",
        "pytest -q",
        "gh repo view",
    ):
        assert not _denies_publish("Bash", {"command": command}), command


def test_denies_publish_ignore_les_autres_outils() -> None:
    assert not _denies_publish("Read", {"file_path": "git push"})
    assert not _denies_publish("Bash", None)


def test_publication_autorisee_laisse_passer_commit_et_push() -> None:
    for command in (
        "git commit -m 'feat: x'",
        "git push -u origin claude/abc",
        "gh pr create --fill",
    ):
        assert _publish_denial("Bash", {"command": command}, publish_allowed=True) is None, command
        assert _publish_denial("Bash", {"command": command}, publish_allowed=False) is not None, (
            command
        )


def test_push_force_refuse_meme_autorise() -> None:
    for command in (
        "git push --force origin main",
        "git push -f origin claude/abc",
        "git push --force-with-lease",
        "git push --mirror autre-remote",
    ):
        assert _publish_denial("Bash", {"command": command}, publish_allowed=True) is not None, (
            command
        )
