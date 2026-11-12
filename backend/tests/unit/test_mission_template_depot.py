"""Ce qu'Eldir dépose dans un worktree est caché à git."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from app.services import mission_template_service as module
from app.services.mission_template_service import InlineSubAgent, mission_template_service


async def test_les_skills_et_sub_agents_deposes_sont_exclus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = SimpleNamespace(name="lint", description="d", content="c")
    agent = InlineSubAgent(name="relecteur", description="d", system_prompt="p")
    modele = SimpleNamespace(skills=[skill], sub_agents=[agent])
    exclus: list[str] = []

    async def get(*_a: Any, **_k: Any) -> Any:
        return modele

    async def exclure(_chemin: Path, motifs: list[str]) -> None:
        exclus.extend(motifs)

    monkeypatch.setattr(mission_template_service, "get", get)
    monkeypatch.setattr(module.worktree_service, "exclure_localement", exclure)
    await mission_template_service.materialize_to_worktree(
        None,  # type: ignore[arg-type]
        project_id="p",
        user_id="u",
        worktree_path=tmp_path,
        extra_sub_agents=[
            InlineSubAgent(name="mask-data", description="d", system_prompt="p"),
            InlineSubAgent(name="relecteur", description="d", system_prompt="p"),
        ],
    )

    assert (tmp_path / ".claude/skills/lint/SKILL.md").exists()
    assert exclus == [
        "/.claude/skills/lint/",
        "/.claude/agents/mask-data.md",
        "/.claude/agents/relecteur.md",
    ]
