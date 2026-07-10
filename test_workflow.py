"""Test bout-en-bout du workflow BPMN (Agent 1 — Triage SIH ⇆ Agent 2 — Pharmacologue).

Rejoue la logique d'orchestration en appelant réellement les outils MCP sur la
base `sih_mcp_db`, avec un `correlation_id` par ordonnance. Chaque appel est
tracé dans `journal_mcp.json` (agent délégué + correlation_id).

Usage :
    python test_workflow.py                 # rejoue les ordonnances de démo (sans envoi SMS)
    python test_workflow.py ORD-5567        # une ordonnance précise (via son patient)
    python test_workflow.py --sms           # envoie réellement le SMS/e-mail médecin (CRITICAL_ALERT)

Prérequis : avoir peuplé la base (`python seed_db.py`).
"""

import json
import sys

from journal import definir_correlation_id, vider_journal, JOURNAL_PATH
from seed_db import seed

# Outils MCP (les objets exposés par FastMCP). On appelle la fonction sous-jacente.
from outil_dossier_patient import recuperer_dossier_patient
from outil_interactions import analyser_interactions
from outil_alternative import rechercher_alternative
from outil_valider_ordonnance import valider_ordonnance
from outil_bloquer_pilulier import bloquer_preparation_pilulier
from outil_sms_medecin import envoyer_sms_medecin

GRAVITES_MAJEURES = {"majeure", "contre-indiquee", "contre_indiquee"}


def appeler(outil, *args, **kwargs):
    """Appelle un outil MCP qu'il soit exposé comme fonction ou comme objet Tool."""
    fonction = getattr(outil, "fn", None) or outil
    return fonction(*args, **kwargs)


def traiter_ordonnance(patient_id: str, envoyer_sms: bool = False) -> None:
    """Déroule le processus BPMN complet pour un patient."""
    cid = definir_correlation_id()
    print(f"\n{'='*70}\nCORRELATION_ID = {cid}  |  patient = {patient_id}\n{'='*70}")

    # --- Agent 1 : récupération + validation du dossier ---------------------
    dossier = json.loads(appeler(recuperer_dossier_patient, patient_id))
    if not dossier.get("dossier_valide"):
        print(f"[Agent 1] Dossier INVALIDE -> {dossier.get('motif')}")
        print("Résultat : Échec (dossier incomplet).")
        return

    prescription_id = dossier["prescription_id"]
    molecules = dossier["molecules"]
    print(f"[Agent 1] Dossier valide. Ordonnance {prescription_id} : {molecules}")
    print("[Agent 1] -> délègue l'expertise à l'Agent 2 (Pharmacologue).")

    # --- Agent 2 : analyse des interactions --------------------------------
    analyse = json.loads(appeler(analyser_interactions, molecules))
    risque = analyse["risque_majeur"]
    print(f"[Agent 2] Interactions détectées : {len(analyse['interactions_detectees'])}"
          f" | risque_majeur = {risque}")

    if risque:
        # Agent 2 : recherche d'une alternative pour l'interaction majeure.
        maj = next(
            i for i in analyse["interactions_detectees"]
            if str(i.get("gravite", "")).lower() in GRAVITES_MAJEURES
        )
        alt = json.loads(appeler(rechercher_alternative, maj["molecule_a"], maj["molecule_b"]))
        verdict = "CRITICAL_ALERT"
        print(f"[Agent 2] VERDICT = {verdict} | {maj['molecule_a']} + {maj['molecule_b']}"
              f" ({maj['gravite']}) -> alternative : {alt.get('alternative')}")

        # --- Agent 1 : exécution du verdict critique -----------------------
        print(f"[Agent 1] <- rapport reçu. Application du verdict {verdict}.")
        appeler(bloquer_preparation_pilulier, prescription_id,
                motif=f"{maj['molecule_a']}+{maj['molecule_b']} ({maj['gravite']})")
        message = (
            f"Ordonnance {prescription_id} BLOQUÉE. Interaction {maj['molecule_a']} + "
            f"{maj['molecule_b']} ({maj['gravite']}). Alternative proposée : "
            f"{alt.get('alternative')}."
        )
        if envoyer_sms:
            print("[Agent 1] " + appeler(envoyer_sms_medecin, message=message,
                                         prescription_id=prescription_id))
        else:
            print("[Agent 1] (SMS médecin simulé — relancer avec --sms pour un envoi réel)")
        print("Résultat : Ordonnance rejetée sûre.")
    else:
        verdict = "APPROVED"
        print(f"[Agent 2] VERDICT = {verdict}")
        print(f"[Agent 1] <- rapport reçu. Application du verdict {verdict}.")
        appeler(valider_ordonnance, prescription_id)
        print("Résultat : Traitement validé.")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    envoyer_sms = "--sms" in sys.argv[1:]

    # Patients de démonstration (voir seed_db.py) : critique + approuvé.
    patients = args or ["P-1024", "P-2048"]

    # Ré-initialise l'état des ordonnances pour que le test soit rejouable
    # (le workflow modifie le statut : en_attente -> validee / bloquee).
    print("Ré-initialisation de la base (seed)…")
    seed()

    print("\nVidage du journal…")
    vider_journal()

    for patient_id in patients:
        traiter_ordonnance(patient_id, envoyer_sms=envoyer_sms)

    # Affichage du journal corrélé.
    print(f"\n{'#'*70}\nJOURNAL ({JOURNAL_PATH.name})\n{'#'*70}")
    with open(JOURNAL_PATH, encoding="utf-8") as f:
        print(f.read())


if __name__ == "__main__":
    main()
