"""Outil MCP : ANALYSE des interactions médicamenteuses (Agent 2 — Pharmacologue).

Correspond à l'activité BPMN ``pharma.analyser_interactions()``. Compare les
molécules prescrites deux à deux avec la collection
``interactions_medicamenteuses`` et détecte la présence d'un risque majeur
(porte « Risque Majeur Détecté ? »).
"""

import json
from itertools import combinations

from journal import tracer
from mongo_mcp import get_collection, mcp


@mcp.tool()
@tracer("lecture")
def analyser_interactions(molecules: list[str]) -> str:
    """Analyse les interactions entre les molécules prescrites.

    Interroge la collection ``interactions_medicamenteuses`` pour chaque paire
    de molécules et renvoie les interactions connues, leur gravité, ainsi que
    le drapeau ``risque_majeur`` (vrai si au moins une interaction est de
    gravité « majeure » / « contre-indiquee »).

    Args:
        molecules: Liste des molécules prescrites (ex : ["Warfarine", "Aspirine"]).
    """
    try:
        collection = get_collection("interactions_medicamenteuses")

        graves = {"majeure", "contre-indiquee", "contre_indiquee"}
        interactions = []

        for a, b in combinations(sorted(set(molecules)), 2):
            doc = collection.find_one(
                {
                    "$or": [
                        {"molecule_a": a, "molecule_b": b},
                        {"molecule_a": b, "molecule_b": a},
                    ]
                },
                {"_id": 0},
            )
            if doc:
                interactions.append(doc)

        risque_majeur = any(
            str(i.get("gravite", "")).lower() in graves for i in interactions
        )

        return json.dumps(
            {
                "molecules_analysees": molecules,
                "risque_majeur": risque_majeur,
                "interactions_detectees": interactions,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erreur lors de l'analyse des interactions : {str(e)}"
