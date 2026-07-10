"""
Module partagé : instance MCP + connexion MongoDB (Système d'Information
Hospitalier).

Tous les fichiers d'outils (outil_dossier_patient.py, outil_interactions.py,
outil_alternative.py, outil_valider_ordonnance.py, outil_bloquer_pilulier.py)
importent `mcp` et `get_collection()` depuis ce module, pour éviter de
dupliquer la configuration de connexion.

Base de données : `sih_mcp_db`
    - patients                    (profils patients : allergies, pathologies…)
    - prescriptions               (ordonnances : molécules, statut, pilulier)
    - interactions_medicamenteuses (interactions connues + alternatives)

La chaîne de connexion est lue depuis la variable d'environnement MONGODB_URI
si elle existe, sinon la valeur par défaut ci-dessous est utilisée.
"""

import os

import certifi
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

# Charge le fichier .env (config SMTP, éventuellement MONGODB_URI). Ce module
# étant importé en premier, les variables sont disponibles pour tous les outils.
load_dotenv()

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sabir_fusion:GenAIOT2026@cluster0.snap5mi.mongodb.net/?appName=Cluster0",
)

# Nom de la base du Système d'Information Hospitalier.
DB_NAME = os.environ.get("MONGODB_DB", "sih_mcp_db")

# Instance unique du serveur MCP, partagée par tous les outils.
mcp = FastMCP("SIH_Pharma_MCP")


def get_db():
    """Retourne la base MongoDB `sih_mcp_db`.

    La connexion est créée à l'appel (et non au démarrage) pour que le serveur
    ne plante pas si MongoDB est momentanément indisponible.
    """
    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=2000,
        tlsCAFile=certifi.where(),
    )
    return client[DB_NAME]


def get_collection(nom: str):
    """Retourne une collection de `sih_mcp_db`.

    Args:
        nom: Nom de la collection (``patients``, ``prescriptions`` ou
            ``interactions_medicamenteuses``).
    """
    return get_db()[nom]
