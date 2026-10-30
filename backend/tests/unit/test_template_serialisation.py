"""La sérialisation d'un Mission Template ne perd aucun champ.

`_serialize_template` recopie le modèle champ par champ. Un champ ajouté au
modèle et au schéma, mais oublié ici, fait lever une erreur de validation à
l'exécution : la route rend 500 alors que toute la suite reste verte, parce
qu'aucun test ne construisait la réponse. C'est arrivé en ajoutant
`source_externe`, et c'est mypy qui l'a vu, pas les tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.v1.mission_templates import _serialize_template
from app.db.models import MissionTemplate
from app.schemas.mission_template import MissionTemplateRead
from pydantic import BaseModel

# Les champs du schéma de lecture qui ne viennent pas du modèle.
HORS_MODELE = frozenset({"skills", "sub_agents"})


def brut(valeur: object) -> object:
    """Ramène une valeur du schéma à ce que le modèle stocke.

    `collect_commands` est une liste de dicts en base et une liste de
    `CollectEntry` dans le schéma : comparer sans normaliser échouerait sur un
    champ correctement câblé, et exempter ce champ cacherait le jour où il
    cesse de l'être.
    """
    if isinstance(valeur, list):
        return [brut(v) for v in valeur]
    if isinstance(valeur, BaseModel):
        return valeur.model_dump()
    return valeur


def test_la_serialisation_ne_perd_aucun_champ_du_modele() -> None:
    template = MissionTemplate(
        id="t1",
        project_id="p1",
        system_prompt="prompt",
        model="claude-sonnet-5",
        allowed_tools=["Read", "Bash"],
        setup_commands=["make setup"],
        collect_commands=[{"fichier": "a.log", "commande": "ssh m cat /a.log"}],
        remote_host="machine-du-projet",
        source_externe=True,
        source_preset="python",
        # Les timestamps viennent du mixin, pas remplis sur un objet transitoire.
        created_at=datetime(2026, 10, 30, tzinfo=UTC),
        updated_at=datetime(2026, 10, 30, tzinfo=UTC),
    )

    lu = _serialize_template(template)

    attendus = set(MissionTemplateRead.model_fields) - HORS_MODELE
    assert attendus, "le schéma n'a plus de champ : le test ne vérifie plus rien"
    for nom in attendus:
        if not hasattr(template, nom):
            continue
        assert brut(getattr(lu, nom)) == getattr(template, nom), nom


def test_chaque_champ_du_schema_vient_du_modele_ou_est_declare_a_part() -> None:
    """Garde l'exemption honnête : un champ nouveau doit être câblé, pas exempté.

    Sans ce test, agrandir `HORS_MODELE` serait un moyen silencieux de faire
    passer le test voisin sans câbler le champ.
    """
    inconnus = {
        nom
        for nom in MissionTemplateRead.model_fields
        if nom not in HORS_MODELE and not hasattr(MissionTemplate, nom)
    }
    assert not inconnus, f"champs du schéma absents du modèle : {inconnus}"
