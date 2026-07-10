"""
Journalisation (traçage) des appels d'outils MCP.

Chaque outil décoré par @tracer("<permission>") voit ses appels enregistrés :
- dans la CONSOLE (visible dans le terminal du serveur et les traces Fusion AI) ;
- dans le fichier `journal_mcp.json` (tableau JSON lisible, en blocs indentés).

Une entrée reste volontairement concise :
    date_heure, outil, permission, arguments, statut, resultat (+ erreur si échec).
Le fichier est réécrit (mis à jour) à chaque appel : le journal reste dynamique.
"""

import functools
import json
import os
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path(__file__).parent / "journal_mcp.json"
_TAILLE_MAX_RESULTAT = 400  # caractères conservés dans le résultat


def _tronquer(valeur) -> str:
    texte = valeur if isinstance(valeur, str) else str(valeur)
    if len(texte) > _TAILLE_MAX_RESULTAT:
        return texte[:_TAILLE_MAX_RESULTAT] + "…"
    return texte


def _ajouter_au_journal(entree: dict) -> None:
    """Ajoute une entrée au tableau JSON et réécrit le fichier (format indenté)."""
    try:
        if JOURNAL_PATH.exists():
            with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
                donnees = json.load(f)
            if not isinstance(donnees, list):
                donnees = []
        else:
            donnees = []
    except Exception:
        donnees = []

    donnees.append(entree)

    # Écriture ATOMIQUE : on écrit dans un fichier temporaire puis on remplace,
    # pour que le journal ne soit jamais laissé vide (0 octet) en cas d'incident.
    try:
        temp = JOURNAL_PATH.with_suffix(".json.tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, JOURNAL_PATH)
    except Exception:
        pass  # la journalisation ne doit jamais casser l'outil


def tracer(permission: str = "inconnue"):
    """Décorateur d'usine : trace l'appel d'un outil MCP et sa permission.

    Args:
        permission: niveau de permission de l'outil
            (ex : "lecture", "ecriture", "suppression", "lecture_externe").
    """

    def decorateur(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            date_heure = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            statut, erreur, resultat = "succes", None, None
            try:
                resultat = func(*args, **kwargs)
                return resultat
            except Exception as e:
                statut, erreur = "erreur", str(e)
                raise
            finally:
                entree = {
                    "date_heure": date_heure,
                    "outil": func.__name__,
                    "permission": permission,
                    "arguments": kwargs if kwargs else (list(args) if args else {}),
                    "statut": statut,
                    "resultat": _tronquer(resultat) if statut == "succes" else None,
                }
                if erreur:
                    entree["erreur"] = erreur

                # Trace console (terminal serveur / Fusion AI)
                print(
                    f"[MCP] {date_heure} | {func.__name__} | {permission} | {statut}",
                    flush=True,
                )
                # Trace fichier (journal_mcp.json)
                _ajouter_au_journal(entree)

        return wrapper

    return decorateur
