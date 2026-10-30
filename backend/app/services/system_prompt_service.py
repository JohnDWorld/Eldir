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
from typing import Any, Final, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.models import SystemPromptOverride

logger = get_logger(__name__)

_CONFLIT = (
    "Ce prompt a changé depuis que tu l'as ouvert (un agent y a peut-être écrit "
    "une préférence). Rien n'a été écrit : recharge la page pour voir le texte à "
    "jour, puis refais ta modification."
)

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

    async def upsert(
        self, db: AsyncSession, slug: str, content: str, *, lu: str | None = None
    ) -> SystemPromptRead:
        """Écrit le contenu d'un prompt.

        `lu` est le texte que l'appelant avait sous les yeux. Fourni, l'écriture
        est conditionnée dessus et lève `ConflictError` si quelqu'un a écrit
        entre-temps. Sans lui, c'est un écrasement inconditionnel.

        Pourquoi la condition : l'outil `remember` du superviseur écrit dans le
        prompt des préférences par un `UPDATE ... WHERE content = lu`, pour que
        deux écrivains simultanés ne se perdent pas l'un l'autre. Un éditeur
        ouvert trente secondes plus tôt qui sauvegarde sans condition efface la
        ligne qu'un agent vient d'écrire, alors que l'agent a reçu « Noté ».
        Même protocole des deux côtés, sinon la symétrie manque.

        Raises:
            ConflictError: `lu` est fourni et le contenu a changé depuis.
        """
        # On vérifie que le slug existe en défaut - sinon on refuse
        # (pas de prompt fantôme sans contrepartie git)
        _, defaut = self._load_default(slug)

        if lu is None:
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

        result = await db.execute(
            select(SystemPromptOverride).where(SystemPromptOverride.slug == slug)
        )
        existing = result.scalar_one_or_none()
        # Égalité sur le texte rogné : les deux écrivains rognent ce qu'ils
        # écrivent, mais le défaut lu dans le fichier garde son saut de ligne
        # final. Sans ce rognage, la première sauvegarde d'un prompt jamais
        # surchargé serait refusée par un 409 que recharger ne résout pas.
        actuel = existing.content if existing is not None else defaut
        if actuel.strip() != lu.strip():
            raise ConflictError(_CONFLIT)

        if existing is None:
            try:
                db.add(SystemPromptOverride(slug=slug, content=content))
                await db.flush()
            except IntegrityError as exc:  # un autre a créé la ligne entre-temps
                raise ConflictError(_CONFLIT) from exc
            return await self.get(db, slug)

        # Conditionnée sur le texte exact qu'on vient de lire : deux écrivains
        # sur la même ligne sans condition, et le second écrase le premier en
        # silence, les deux croyant avoir réussi.
        resultat = await db.execute(
            update(SystemPromptOverride)
            .where(SystemPromptOverride.slug == slug)
            .where(SystemPromptOverride.content == actuel)
            .values(content=content),
            execution_options={"synchronize_session": False},
        )
        if cast("CursorResult[Any]", resultat).rowcount != 1:
            raise ConflictError(_CONFLIT)
        # L'objet chargé porte encore l'ancien texte : sans ça, c'est lui que
        # `get` rendrait, et l'appelant lirait sa propre écriture de travers.
        db.expire(existing)
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
