"""Ce qu'une session voit de l'environnement du backend.

Une session tourne en `bypassPermissions` sur des consignes qui peuvent venir
d'un utilisateur de La Boutique : tout ce qu'elle lit dans son environnement
est à portée d'une injection de prompt. Le pire n'est pas le jeton Git, c'est
`JWT_SECRET` : il suffit à se forger un jeton de connexion et à s'autoriser la
publication sans qu'aucune commande git ne passe devant le hook.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings, env_a_masquer_pour_cli, get_settings
from app.core.constants import ENV_VAR_CREDENTIEL_PAR_KIND
from app.core.exceptions import AuthenticationError
from app.core.security import decode_session_token
from jose import jwt

# Les secrets dont la fuite donne le plus : forger un jeton, déchiffrer les
# credentials Git stockés, parler à la base directement.
SECRETS_CRITIQUES = ("JWT_SECRET", "ENCRYPTION_KEY", "DATABASE_URL")


def env_vu_par_la_session(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Reproduit la fusion que fait le SDK : `options.env` par-dessus l'hérité.

    C'est l'ordre de `subprocess_cli.py` (`{**inherited_env, **options.env}`),
    et c'est ce qui rend le masque nécessaire : le SDK ne remplace pas
    l'environnement du backend, il le complète.
    """
    import os

    return {**os.environ, **env_a_masquer_pour_cli()}


def test_les_secrets_critiques_sont_vides_pour_la_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for nom in SECRETS_CRITIQUES:
        monkeypatch.setenv(nom, "valeur-sensible-du-backend")

    vu = env_vu_par_la_session(monkeypatch)

    for nom in SECRETS_CRITIQUES:
        assert vu[nom] == "", f"{nom} reste lisible par la session"


def test_une_session_ne_peut_pas_forger_un_jeton_de_connexion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le test que John demande : le secret lu par la session n'ouvre rien.

    On joue l'attaque complète. La session lit `JWT_SECRET` dans son
    environnement, signe un jeton de connexion (aucun claim `kind`, donc
    accepté par `decode_session_token`) et le présente à l'API. Avec le vrai
    secret ce jeton passerait et vaudrait un `allow_publish`.
    """
    vrai_secret = get_settings().jwt_secret.get_secret_value()
    monkeypatch.setenv("JWT_SECRET", vrai_secret)

    secret_vu = env_vu_par_la_session(monkeypatch)["JWT_SECRET"]
    assert secret_vu != vrai_secret

    forge = jwt.encode({"sub": "1"}, secret_vu or "vide", algorithm="HS256")
    with pytest.raises(AuthenticationError):
        decode_session_token(forge)


def test_le_credential_claude_passe_quand_meme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans lui le CLI de la session ne s'authentifie pas : c'est l'exception."""
    for nom in ENV_VAR_CREDENTIEL_PAR_KIND.values():
        monkeypatch.setenv(nom, "credential-claude")

    vu = env_vu_par_la_session(monkeypatch)

    for nom in ENV_VAR_CREDENTIEL_PAR_KIND.values():
        assert vu[nom] == "credential-claude"


def test_le_masque_ne_touche_pas_ce_qui_fait_tourner_la_toolchain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`PATH` et `HOME` ne sont pas des champs de Settings : la session en a besoin."""
    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    monkeypatch.setenv("HOME", "/home/eldir")

    vu = env_vu_par_la_session(monkeypatch)

    assert vu["PATH"] == "/usr/local/bin:/usr/bin"
    assert vu["HOME"] == "/home/eldir"


def test_tout_secret_de_settings_est_masque(monkeypatch: pytest.MonkeyPatch) -> None:
    """La garde qui survit à l'ajout d'un secret dans la configuration.

    Le masque se dérive des champs de `Settings`, donc un secret ajouté demain
    est couvert sans qu'on y pense. Ce test le vérifie plutôt que de recopier
    une liste qui dériverait.
    """
    secrets = [
        nom for nom, champ in Settings.model_fields.items() if "SecretStr" in str(champ.annotation)
    ]
    assert secrets, "aucun SecretStr trouvé : le test ne vérifie plus rien"

    for nom in secrets:
        monkeypatch.setenv(nom.upper(), "secret")

    vu = env_vu_par_la_session(monkeypatch)

    fuites = [
        nom
        for nom in secrets
        if nom.upper() not in ENV_VAR_CREDENTIEL_PAR_KIND.values() and vu[nom.upper()] != ""
    ]
    assert not fuites, f"secrets lisibles par une session : {fuites}"


def test_le_masque_suit_la_casse_reelle_de_lenvironnement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings` est insensible à la casse, le masque doit l'être aussi.

    Un `jwt_secret` en minuscules dans l'environnement est lu par Settings
    exactement comme `JWT_SECRET`. Masquer la seule forme majuscule laisserait
    donc le secret lisible.
    """
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("jwt_secret", "secret-en-minuscules")

    assert env_vu_par_la_session(monkeypatch)["jwt_secret"] == ""
