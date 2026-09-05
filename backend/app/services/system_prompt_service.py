"""SystemPromptService - prompts système éditables par l'utilisateur.

Le défaut vit dans `backend/app/data/system_prompts/{slug}.md` (en git,
mis à jour à chaque release d'Eldir).
L'override utilisateur est stocké en DB (table `system_prompt_overrides`).
Reset au défaut = suppression de la ligne.

Convention : un fichier `.md` peut avoir un frontmatter YAML simple :

    ---
    title: "Titre humain"
    description: "Une ligne d'aide UI"
    ---
    Contenu Markdown du prompt...

Le frontmatter est uniquement pour l'UI, pas envoyé à Claude.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import SystemPromptOverride

logger = get_logger(__name__)

# Dossier des prompts par défaut (versionnés en git)
_DEFAULTS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "data" / "system_prompts"


@dataclass(slots=True, frozen=True)
class SystemPromptRead:
    slug: str
    title: str
    description: str
    content: str
    is_overridden: bool
    default_content: str


def _parse_file(path: Path) -> tuple[dict[str, str], str]:
    """Sépare frontmatter YAML simple (clé: valeur) du contenu."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw
    try:
        end = raw.index("\n---\n", 4)
    except ValueError:
        return {}, raw
    header = raw[4:end]
    body = raw[end + 5 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in header.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


class SystemPromptService:
    """Stateless. Toutes les méthodes prennent une `AsyncSession` SQLA."""

    def _load_default(self, slug: str) -> tuple[dict[str, str], str]:
        path = _DEFAULTS_DIR / f"{slug}.md"
        if not path.is_file():
            raise NotFoundError(f"Prompt système '{slug}' introuvable (cherché : {path}).")
        return _parse_file(path)

    def list_available_slugs(self) -> list[str]:
        if not _DEFAULTS_DIR.is_dir():
            return []
        return sorted(p.stem for p in _DEFAULTS_DIR.glob("*.md"))

    async def list_all(self, db: AsyncSession) -> list[SystemPromptRead]:
        # Toutes les valeurs overridées
        result = await db.execute(select(SystemPromptOverride))
        overrides = {o.slug: o.content for o in result.scalars().all()}

        items: list[SystemPromptRead] = []
        for slug in self.list_available_slugs():
            meta, default_content = self._load_default(slug)
            content = overrides.get(slug, default_content)
            items.append(
                SystemPromptRead(
                    slug=slug,
                    title=meta.get("title", slug),
                    description=meta.get("description", ""),
                    content=content,
                    is_overridden=slug in overrides,
                    default_content=default_content,
                )
            )
        return items

    async def get(self, db: AsyncSession, slug: str) -> SystemPromptRead:
        meta, default_content = self._load_default(slug)
        result = await db.execute(
            select(SystemPromptOverride).where(SystemPromptOverride.slug == slug)
        )
        override = result.scalar_one_or_none()
        content = override.content if override is not None else default_content
        return SystemPromptRead(
            slug=slug,
            title=meta.get("title", slug),
            description=meta.get("description", ""),
            content=content,
            is_overridden=override is not None,
            default_content=default_content,
        )

    async def resolve(self, db: AsyncSession, slug: str) -> str:
        """Renvoie juste le contenu effectif. Appel le plus fréquent."""
        return (await self.get(db, slug)).content

    async def upsert(self, db: AsyncSession, slug: str, content: str) -> SystemPromptRead:
        # On vérifie que le slug existe en défaut - sinon on refuse
        # (pas de prompt fantôme sans contrepartie git)
        self._load_default(slug)

        result = await db.execute(
            select(SystemPromptOverride).where(SystemPromptOverride.slug == slug)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.content = content
        else:
            db.add(SystemPromptOverride(slug=slug, content=content))
        await db.flush()
        return await self.get(db, slug)

    async def reset(self, db: AsyncSession, slug: str) -> SystemPromptRead:
        """Supprime l'override - le défaut reprend la main."""
        result = await db.execute(
            select(SystemPromptOverride).where(SystemPromptOverride.slug == slug)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await db.delete(existing)
            await db.flush()
        return await self.get(db, slug)


system_prompt_service = SystemPromptService()
