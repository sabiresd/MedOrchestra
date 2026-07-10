"""Outil MCP : BLOCAGE de la préparation du pilulier (Agent 1 — Triage SIH).

Correspond à l'activité BPMN ``sih.bloquer_preparation_pilulier()``, déclenchée
quand le Pharmacologue (Agent 2) renvoie le verdict ``CRITICAL_ALERT``. Empêche
la préparation du pilulier dans la collection ``prescriptions`` (« Processus
Clos : Ordonnance Rejetée Sûre »).
"""

import json

from journal import tracer
from mongo_mcp import get_collection, mcp


@mcp.tool()
@tracer("ecriture", agent="Agent 1 — Triage SIH")
def bloquer_preparation_pilulier(prescription_id: str, motif: str = "") -> str:
    """Bloque la préparation du pilulier (verdict CRITICAL_ALERT).

    Passe le statut de l'ordonnance à ``bloquee`` et interdit la préparation
    du pilulier. Renvoie l'état AVANT et APRÈS.

    Args:
        prescription_id: Identifiant de l'ordonnance (ex : "ORD-5567").
        motif: Raison du blocage (interaction majeure détectée, alerte…).
    """
    try:
        prescriptions = get_collection("prescriptions")

        avant = prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})
        if avant is None:
            return f"Aucune ordonnance trouvée pour l'identifiant '{prescription_id}'."

        prescriptions.update_one(
            {"prescription_id": prescription_id},
            {
                "$set": {
                    "statut": "bloquee",
                    "preparation_pilulier": False,
                    "motif_blocage": motif or "Risque majeur détecté (CRITICAL_ALERT).",
                }
            },
        )

        apres = prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})

        return json.dumps(
            {"statut": "bloquee", "avant": avant, "apres": apres},
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erreur lors du blocage du pilulier : {str(e)}"
