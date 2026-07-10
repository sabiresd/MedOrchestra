"""Outil MCP : RECHERCHE d'une alternative thérapeutique (Agent 2 — Pharmacologue).

Correspond à l'activité BPMN ``pharma.rechercher_alternative()``, déclenchée
lorsqu'un risque majeur est détecté. Propose une molécule de substitution à
partir de la collection ``interactions_medicamenteuses`` afin d'alimenter le
payload ``CRITICAL_ALERT + Alternative``.
"""

import json

from journal import tracer
from mongo_mcp import get_collection, mcp


@mcp.tool()
@tracer("lecture", agent="Agent 2 — Pharmacologue")
def rechercher_alternative(molecule: str, molecule_en_conflit: str = "") -> str:
    """Recherche une alternative thérapeutique à une molécule à risque.

    Cherche dans ``interactions_medicamenteuses`` une interaction impliquant la
    molécule (et, si fournie, celle en conflit) et renvoie l'alternative
    recommandée.

    Args:
        molecule: Molécule à remplacer (ex : "Aspirine").
        molecule_en_conflit: Molécule avec laquelle l'interaction survient
            (optionnel, affine la recherche).
    """
    try:
        collection = get_collection("interactions_medicamenteuses")

        requete = {"$or": [{"molecule_a": molecule}, {"molecule_b": molecule}]}
        if molecule_en_conflit:
            requete = {
                "$or": [
                    {"molecule_a": molecule, "molecule_b": molecule_en_conflit},
                    {"molecule_a": molecule_en_conflit, "molecule_b": molecule},
                ]
            }

        doc = collection.find_one(requete, {"_id": 0})
        if doc is None:
            return json.dumps(
                {
                    "molecule": molecule,
                    "alternative": None,
                    "motif": "Aucune interaction/alternative référencée pour cette molécule.",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "molecule": molecule,
                "alternative": doc.get("alternative"),
                "gravite": doc.get("gravite"),
                "commentaire": doc.get("description") or doc.get("commentaire"),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erreur lors de la recherche d'une alternative : {str(e)}"
