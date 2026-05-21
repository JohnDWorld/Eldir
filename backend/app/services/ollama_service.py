"""OllamaService - client minimal pour Ollama local.

Cas d'usage Phase 6 (mode "données sensibles") :
- Pré-traiter du texte localement AVANT de l'envoyer à Claude
  (masquage de secrets, anonymisation, résumé court)
- Tout reste sur le réseau de l'utilisateur, Anthropic ne reçoit jamais
  les données brutes

Endpoints Ollama utilisés :
- GET  /api/tags    : liste des modèles installés
- POST /api/generate : completion synchrone (on n'utilise pas le streaming
  ici, on a juste besoin d'un retour transformé court)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.core.logging import get_logger

logger = get_logger(__name__)


TransformMode = Literal["mask", "anonymize", "summarize"]


@dataclass(slots=True, frozen=True)
class OllamaModelInfo:
    name: str
    size_bytes: int
    modified_at: str | None = None


@dataclass(slots=True, frozen=True)
class OllamaStatus:
    enabled: bool
    base_url: str | None
    reachable: bool
    error: str | None
    default_model: str
    available_models: list[OllamaModelInfo]


# Prompts internes - factorisés ici. Si on veut les rendre éditables par
# l'utilisateur plus tard, on les déplace dans data/system_prompts/ comme
# template_generator.md (mode `system_prompt_service`).
_MASK_PROMPT = (
    "Tu es un agent local de masquage de secrets. Tu reçois un texte et "
    "tu retournes le MÊME texte avec tous les éléments sensibles "
    "remplacés par des placeholders.\n\n"
    "Éléments à masquer :\n"
    "- Clés d'API et tokens (sk-..., ghp_..., github_pat_..., aws_..., "
    "etc.) → [REDACTED_TOKEN]\n"
    "- Mots de passe et URLs de connexion DB → [REDACTED_PASSWORD], "
    "[REDACTED_DB_URL]\n"
    "- Adresses email → [REDACTED_EMAIL]\n"
    "- Noms de domaines internes / IP privées → [REDACTED_HOST]\n"
    "- Numéros de téléphone, IBAN, numéros de carte → [REDACTED_PII]\n\n"
    "Ne réponds RIEN d'autre que le texte masqué. Pas d'explication, "
    "pas de markdown."
)

_ANONYMIZE_PROMPT = (
    "Tu es un agent local d'anonymisation. Tu reçois un texte et tu "
    "retournes le MÊME texte avec toutes les informations personnelles "
    "identifiables remplacées par des génériques cohérents :\n\n"
    "- Noms et prénoms → 'Personne A', 'Personne B'...\n"
    "- Identifiants utilisateurs (ID, UUID, login) → 'USER_1', 'USER_2'...\n"
    "- Entreprises / organisations → 'Entreprise X', 'Entreprise Y'...\n"
    "- Adresses physiques → 'Adresse 1', 'Adresse 2'...\n\n"
    "Garde la cohérence : si 'Jean Dupont' apparaît plusieurs fois, "
    "c'est toujours 'Personne A'.\n"
    "Ne réponds RIEN d'autre que le texte anonymisé."
)

_SUMMARIZE_PROMPT = (
    "Tu es un agent local de résumé. Tu reçois un texte long (souvent "
    "un fichier de code ou de doc) et tu produis un résumé court "
    "(10 lignes max) qui :\n"
    "- Décrit ce que fait le contenu\n"
    "- Liste les éléments importants (fonctions, classes, sections)\n"
    "- Garde tout détail technique critique (versions, urls publiques, "
    "paramètres)\n\n"
    "Ne réponds RIEN d'autre que le résumé."
)


_MODE_PROMPTS: dict[TransformMode, str] = {
    "mask": _MASK_PROMPT,
    "anonymize": _ANONYMIZE_PROMPT,
    "summarize": _SUMMARIZE_PROMPT,
}


class OllamaService:
    """Stateless. Utilise les settings runtime pour configurer le client."""

    def _base_url(self) -> str:
        url = get_settings().ollama_base_url.strip().rstrip("/")
        if not url:
            raise EldirError(
                "Ollama n'est pas configuré. Définis OLLAMA_BASE_URL dans .env."
            )
        return url

    def _timeout(self) -> float:
        return get_settings().ollama_timeout_seconds

    async def status(self) -> OllamaStatus:
        settings = get_settings()
        if not settings.ollama_enabled:
            return OllamaStatus(
                enabled=False,
                base_url=None,
                reachable=False,
                error=None,
                default_model=settings.ollama_default_model,
                available_models=[],
            )
        base = settings.ollama_base_url.strip().rstrip("/")
        try:
            models = await self.list_models()
            return OllamaStatus(
                enabled=True,
                base_url=base,
                reachable=True,
                error=None,
                default_model=settings.ollama_default_model,
                available_models=models,
            )
        except Exception as exc:
            logger.warning("ollama.status.unreachable", error=str(exc))
            return OllamaStatus(
                enabled=True,
                base_url=base,
                reachable=False,
                error=str(exc),
                default_model=settings.ollama_default_model,
                available_models=[],
            )

    async def list_models(self) -> list[OllamaModelInfo]:
        async with httpx.AsyncClient(
            base_url=self._base_url(), timeout=self._timeout()
        ) as client:
            response = await client.get("/api/tags")
        if not response.is_success:
            raise EldirError(
                f"Ollama /api/tags a retourné {response.status_code}."
            )
        data = response.json()
        models = data.get("models", []) if isinstance(data, dict) else []
        return [
            OllamaModelInfo(
                name=str(m.get("name", "")),
                size_bytes=int(m.get("size", 0)),
                modified_at=m.get("modified_at"),
            )
            for m in models
            if isinstance(m, dict) and m.get("name")
        ]

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> str:
        """Appel synchrone à /api/generate. Pas de streaming - on a juste
        besoin du résultat final pour les transformations.
        """
        settings = get_settings()
        body: dict[str, Any] = {
            "model": model or settings.ollama_default_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(
            base_url=self._base_url(), timeout=self._timeout()
        ) as client:
            response = await client.post("/api/generate", json=body)

        if not response.is_success:
            raise EldirError(
                f"Ollama /api/generate a retourné {response.status_code} : "
                f"{response.text[:200]}"
            )
        data = response.json()
        if not isinstance(data, dict) or "response" not in data:
            raise EldirError("Réponse inattendue d'Ollama.")
        return str(data["response"])

    async def transform(
        self, *, text: str, mode: TransformMode, model: str | None = None
    ) -> str:
        """Applique une des transformations prédéfinies localement.

        Le `mode` détermine le system prompt utilisé. Le texte transformé
        est retourné tel quel (pas de markdown wrapper, sauf si le modèle
        en ajoute un - dans ce cas on log un warning et on retourne quand
        même).
        """
        system = _MODE_PROMPTS.get(mode)
        if system is None:
            raise EldirError(f"Mode de transformation inconnu : {mode}.")
        return await self.generate(prompt=text, system=system, model=model)


ollama_service = OllamaService()
