"""Outil MCP : RÉCUPÉRATION du dossier patient (Agent 1 — Triage SIH).

Correspond à l'activité BPMN ``sih.recuperer_dossier_patient()``.

Lit le profil du patient dans la collection ``patients`` et son ordonnance
active dans ``prescriptions`` afin d'alimenter la porte « Données Patient
Valides ? » puis la demande d'expertise envoyée au Pharmacologue (Agent 2).
"""

import json

from journal import tracer
from mongo_mcp import get_collection, mcp


@mcp.tool()
@tracer("lecture")
def recuperer_dossier_patient(patient_id: str) -> str:
    """Récupère le dossier d'un patient et son ordonnance active.

    Renvoie le profil (allergies, pathologies, âge…) ainsi que les molécules
    prescrites, et indique si les données sont valides (`dossier_valide`) pour
    déclencher l'analyse pharmacologique.

    Args:
        patient_id: Identifiant du patient (ex : "P-1024").
    """
    try:
        patients = get_collection("patients")
        prescriptions = get_collection("prescriptions")

        patient = patients.find_one({"patient_id": patient_id}, {"_id": 0})
        if patient is None:
            return json.dumps(
                {
                    "dossier_valide": False,
                    "motif": f"Aucun patient trouvé pour l'identifiant '{patient_id}'.",
                },
                ensure_ascii=False,
            )

        # Ordonnance active du patient (statut != annulée).
        ordonnance = prescriptions.find_one(
            {"patient_id": patient_id, "statut": {"$in": ["en_attente", "soumise"]}},
            {"_id": 0},
        )

        molecules = ordonnance.get("molecules", []) if ordonnance else []

        # « Données Patient Valides ? » : profil présent + au moins une molécule.
        dossier_valide = bool(molecules) and patient.get("nom") is not None

        return json.dumps(
            {
                "dossier_valide": dossier_valide,
                "motif": None if dossier_valide else "Dossier incomplet (profil ou molécules manquants).",
                "patient": patient,
                "prescription_id": ordonnance.get("prescription_id") if ordonnance else None,
                "molecules": molecules,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erreur lors de la récupération du dossier patient : {str(e)}"
