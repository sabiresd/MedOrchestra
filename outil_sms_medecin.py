"""Outil MCP : NOTIFICATION du médecin (Agent 1 — Triage SIH).

Correspond à l'activité BPMN ``notif.envoyer_sms_medecin()``, déclenchée en cas
de ``CRITICAL_ALERT`` pour prévenir le médecin prescripteur qu'une interaction
majeure a été détectée et que le pilulier est bloqué.

La notification est acheminée par le canal SMTP déjà configuré (passerelle
e-mail → SMS), dont les paramètres sont lus depuis le fichier .env (jamais
codés en dur) : SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
SMTP_USE_TLS, EMAIL_FROM, EMAIL_TO (destinataire médecin par défaut).
"""

import os
import smtplib
from email.message import EmailMessage

from journal import tracer
from mongo_mcp import mcp  # importe mongo_mcp -> load_dotenv() déjà exécuté

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USERNAME)
MEDECIN_PAR_DEFAUT = os.environ.get("EMAIL_TO", "")


@mcp.tool()
@tracer("ecriture_externe")
def envoyer_sms_medecin(message: str, medecin: str = "", prescription_id: str = "") -> str:
    """Envoie une alerte au médecin prescripteur (CRITICAL_ALERT).

    Args:
        message: Corps de l'alerte (interaction détectée, alternative proposée…).
        medecin: Adresse/numéro du médecin. Si vide, la valeur EMAIL_TO du
            fichier .env est utilisée.
        prescription_id: Identifiant de l'ordonnance concernée (ajouté à l'objet).
    """
    dest = medecin or MEDECIN_PAR_DEFAUT
    if not SMTP_PASSWORD:
        return "Erreur : SMTP_PASSWORD manquant (à définir dans le fichier .env)."
    if not dest:
        return "Erreur : aucun destinataire (fournir 'medecin' ou EMAIL_TO)."

    sujet = "ALERTE PHARMACO — CRITICAL_ALERT"
    if prescription_id:
        sujet += f" (ordonnance {prescription_id})"

    try:
        courriel = EmailMessage()
        courriel["From"] = EMAIL_FROM
        courriel["To"] = dest
        courriel["Subject"] = sujet
        courriel.set_content(message)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as serveur:
            if SMTP_USE_TLS:
                serveur.starttls()
            serveur.login(SMTP_USERNAME, SMTP_PASSWORD)
            serveur.send_message(courriel)

        return f"Alerte envoyée au médecin {dest} (ordonnance : {prescription_id or 'N/A'})."
    except Exception as e:
        return f"Erreur lors de l'envoi de l'alerte au médecin : {str(e)}"
