"""Outil MCP : VALIDATION d'une ordonnance (Agent 1 — Triage SIH).

Correspond à l'activité BPMN ``sih.valider_ordonnance()``, déclenchée quand le
Pharmacologue (Agent 2) renvoie le verdict ``APPROVED``. Marque l'ordonnance
comme validée dans la collection ``prescriptions`` (« Processus Clos :
Traitement Validé »).
"""

import json

from journal import tracer
from mongo_mcp import get_collection, mcp


@mcp.tool()
@tracer("ecriture", agent="Agent 1 — Triage SIH")
def valider_ordonnance(prescription_id: str) -> str:
    """Valide une ordonnance (verdict APPROVED du pharmacologue).

    Passe le statut de l'ordonnance à ``validee`` et autorise la préparation
    du pilulier. Renvoie l'état AVANT et APRÈS.

    Args:
        prescription_id: Identifiant de l'ordonnance (ex : "ORD-5567").
    """
    try:
        prescriptions = get_collection("prescriptions")

        avant = prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})
        if avant is None:
            return f"Aucune ordonnance trouvée pour l'identifiant '{prescription_id}'."

        prescriptions.update_one(
            {"prescription_id": prescription_id},
            {"$set": {"statut": "validee", "preparation_pilulier": True}},
        )

        apres = prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})

        return json.dumps(
            {"statut": "validee", "avant": avant, "apres": apres},
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erreur lors de la validation de l'ordonnance : {str(e)}"
