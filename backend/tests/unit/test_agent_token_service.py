"""Jeton d'agent : longue durée, donc révocable.

Un jeton qu'on ne peut pas révoquer est un jeton qu'on ne peut pas émettre.
C'est l'unique raison d'être de la table : le JWT se vérifierait tout seul.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import create_access_token, decode_agent_token
from app.db.models import AgentToken
from app.services import agent_token_service as svc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def _emettre(db: AsyncSession, user_id: str = "u1", label: str = "eldir du village"):
    """Émet et valide : `authentifier` relit la table, comme le ferait une requête."""
    ligne, clair = await svc.emettre(db, user_id=user_id, label=label)
    await db.commit()
    return ligne, clair


async def test_un_jeton_emis_authentifie_son_utilisateur(db_session: AsyncSession) -> None:
    ligne, clair = await _emettre(db_session)
    assert clair, "le jeton en clair n'est rendu qu'une fois, à l'émission"
    user_id, label = await svc.authentifier(db_session, jeton=clair)
    assert user_id == "u1"
    assert label == "eldir du village"
    assert ligne.revoked_at is None


async def test_authentifier_note_le_dernier_usage(db_session: AsyncSession) -> None:
    """C'est ce qui permet à John de repérer un jeton qui ne sert plus."""
    ligne, clair = await _emettre(db_session)
    assert ligne.last_used_at is None
    await svc.authentifier(db_session, jeton=clair)
    assert ligne.last_used_at is not None


async def test_un_jeton_vit_des_mois(db_session: AsyncSession) -> None:
    """Sans durée explicite, `create_access_token` retombe sur l'heure de la
    connexion et l'agent perdrait l'accès au bout d'une heure."""
    _, clair = await _emettre(db_session)
    expire = datetime.fromtimestamp(decode_agent_token(clair)["exp"], UTC)
    assert expire > datetime.now(UTC) + timedelta(days=300)


async def test_un_jeton_revoque_est_refuse(db_session: AsyncSession) -> None:
    ligne, clair = await _emettre(db_session, label="à couper")
    await svc.revoquer(db_session, user_id="u1", token_id=ligne.id)
    await db_session.commit()
    with pytest.raises(AuthenticationError):
        await svc.authentifier(db_session, jeton=clair)


async def test_un_jwt_de_session_ordinaire_n_ouvre_pas_la_porte(
    db_session: AsyncSession,
) -> None:
    ordinaire = create_access_token("u1")
    with pytest.raises(AuthenticationError):
        await svc.authentifier(db_session, jeton=ordinaire)


@pytest.mark.parametrize("extra", [{}, {"kind": "session"}])
async def test_seul_un_jeton_de_kind_agent_ouvre_la_porte(
    db_session: AsyncSession, extra: dict[str, str]
) -> None:
    """Même sujet, même `jti` vivant : seul le `kind` manque ou diffère. Sans ce
    refus, tout jeton de connexion pourrait porter un `jti` et valoir jeton
    d'agent, donc la révocation ne protégerait rien."""
    ligne, _ = await _emettre(db_session)
    pas_agent = create_access_token("u1", extra_claims={"jti": ligne.jti, **extra})
    with pytest.raises(AuthenticationError, match="pas un jeton d'agent"):
        await svc.authentifier(db_session, jeton=pas_agent)


async def test_un_jeton_inconnu_en_base_est_refuse(db_session: AsyncSession) -> None:
    """Un jti forgé avec la bonne clé mais absent de la table ne passe pas :
    la table est la liste blanche, pas un simple journal."""
    forge = create_access_token("u1", extra_claims={"kind": "agent", "jti": "inexistant"})
    with pytest.raises(AuthenticationError, match="invalide ou révoqué"):
        await svc.authentifier(db_session, jeton=forge)


async def test_un_jeton_sans_jti_est_refuse_comme_incomplet(db_session: AsyncSession) -> None:
    sans_jti = create_access_token("u1", extra_claims={"kind": "agent"})
    with pytest.raises(AuthenticationError, match="incomplet"):
        await svc.authentifier(db_session, jeton=sans_jti)


async def test_le_jti_d_un_autre_utilisateur_ne_se_rejoue_pas(db_session: AsyncSession) -> None:
    """Le `jti` seul ne suffit pas : le sujet signé doit être le propriétaire de
    la ligne. Sinon, connaître un `jti` permettrait d'usurper un autre compte."""
    ligne, _ = await _emettre(db_session, user_id="u1")
    usurpe = create_access_token("u2", extra_claims={"kind": "agent", "jti": ligne.jti})
    with pytest.raises(AuthenticationError, match="invalide ou révoqué"):
        await svc.authentifier(db_session, jeton=usurpe)


async def test_revoquer_est_refuse_pour_un_autre_utilisateur(db_session: AsyncSession) -> None:
    ligne, clair = await _emettre(db_session, user_id="u1")
    with pytest.raises(NotFoundError):
        await svc.revoquer(db_session, user_id="u2", token_id=ligne.id)
    await db_session.commit()
    assert await svc.authentifier(db_session, jeton=clair) == ("u1", "eldir du village")


async def test_revoquer_un_jeton_inconnu_leve(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await svc.revoquer(db_session, user_id="u1", token_id="inexistant")


async def test_revoquer_deux_fois_garde_la_premiere_date(db_session: AsyncSession) -> None:
    """On garde la trace de la vraie coupure, pas de la dernière tentative."""
    ligne, _ = await _emettre(db_session)
    await svc.revoquer(db_session, user_id="u1", token_id=ligne.id)
    premiere = ligne.revoked_at
    assert premiere is not None
    await svc.revoquer(db_session, user_id="u1", token_id=ligne.id)
    assert ligne.revoked_at == premiere


async def test_lister_ne_rend_que_ses_jetons_du_plus_recent_au_plus_ancien(
    db_session: AsyncSession,
) -> None:
    ancien, _ = await _emettre(db_session, label="ancien")
    await _emettre(db_session, label="récent")
    await _emettre(db_session, user_id="u2", label="d'un autre")
    await svc.revoquer(db_session, user_id="u1", token_id=ancien.id)
    lignes = await svc.lister(db_session, user_id="u1")
    # Le révoqué reste listé : on garde la trace.
    assert [ligne.label for ligne in lignes] == ["récent", "ancien"]


async def test_le_libelle_est_nettoye(db_session: AsyncSession) -> None:
    ligne, _ = await _emettre(db_session, label="  eldir du village  ")
    assert ligne.label == "eldir du village"


@pytest.mark.parametrize("label", ["", "   ", "x" * 81])
async def test_un_libelle_vide_ou_trop_long_est_refuse(
    db_session: AsyncSession, label: str
) -> None:
    with pytest.raises(ValidationError):
        await svc.emettre(db_session, user_id="u1", label=label)


async def test_un_jti_ne_peut_pas_etre_porte_par_deux_lignes(db_session: AsyncSession) -> None:
    """`authentifier` suppose un `jti` unique : à deux, la liste blanche serait ambiguë."""
    ligne, _ = await _emettre(db_session)
    db_session.add(AgentToken(user_id="u1", label="doublon", jti=ligne.jti))
    with pytest.raises(IntegrityError):
        await db_session.flush()
