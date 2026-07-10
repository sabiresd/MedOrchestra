"""
Serveur MCP (mode HTTP/SSE) — point d'entrée du Système d'Information
Hospitalier (SIH) pharmaceutique.

Il expose les outils du cas d'usage BPMN (Triage SIH ⇆ Pharmacologue Expert),
chacun défini dans son propre fichier. Importer un module suffit à enregistrer
son outil sur l'instance `mcp` partagée.

Agent 1 — Triage et Exécution (SIH) :
    - recuperer_dossier_patient      -> outil_dossier_patient.py    (lecture)
    - valider_ordonnance             -> outil_valider_ordonnance.py (écriture)
    - bloquer_preparation_pilulier   -> outil_bloquer_pilulier.py   (écriture)
    - envoyer_sms_medecin            -> outil_sms_medecin.py        (écriture externe, SMTP)

Agent 2 — Pharmacologue Expert :
    - analyser_interactions          -> outil_interactions.py       (lecture)
    - rechercher_alternative         -> outil_alternative.py        (lecture)

Base de données MongoDB : `sih_mcp_db`
    (collections : patients, prescriptions, interactions_medicamenteuses).

Tous les appels d'outils sont tracés dans la console et dans journal_mcp.json
(voir journal.py). Le contrat de chaque outil est documenté dans CONTRATS.md.

Lancement :
    python mcp_server.py

Le serveur écoute sur http://127.0.0.1:8000 (endpoint SSE : /sse).
"""

from mongo_mcp import mcp

# L'import de chaque module enregistre son outil sur `mcp`.
# Agent 1 — Triage et Exécution (SIH)
import outil_dossier_patient  # noqa: F401
import outil_valider_ordonnance  # noqa: F401
import outil_bloquer_pilulier  # noqa: F401
import outil_sms_medecin  # noqa: F401
# Agent 2 — Pharmacologue Expert
import outil_interactions  # noqa: F401
import outil_alternative  # noqa: F401

if __name__ == "__main__":
    # On garde uniquement le transport="sse"
    mcp.run(transport="sse")
