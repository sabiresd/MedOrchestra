"""
Journalisation (traçage) des appels d'outils MCP.

Chaque outil décoré par @tracer("<permission>", agent="<agent>") voit ses appels
enregistrés :
- dans la CONSOLE (visible dans le terminal du serveur et les traces Fusion AI) ;
- dans le fichier `journal_mcp.json` (tableau JSON lisible, en blocs indentés).

Une entrée contient :
    date_heure, correlation_id, agent, outil, permission, arguments, statut,
    resultat (+ erreur si échec).

- `correlation_id` : identifiant partagé par tous les appels d'un même
  traitement (une ordonnance), pour relier les actions de l'Agent 1 et de
  l'Agent 2. Il est défini via `definir_correlation_id()`, sinon lu depuis la
  variable d'environnement `MCP_CORRELATION_ID`, sinon un id de session.
- `agent` : l'agent délégué qui exécute l'outil (Agent 1 — Triage SIH ou
  Agent 2 — Pharmacologue), déclaré sur le décorateur `@tracer`.

Le fichier est réécrit (mis à jour) à chaque appel : le journal reste dynamique.
`vider_journal()` réinitialise le fichier à un tableau vide.
"""

import contextvars
import functools
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path(__file__).parent / "journal_mcp.json"
_TAILLE_MAX_RESULTAT = 400  # caractères conservés dans le résultat

# --------------------------------------------------------------------------- #
# Corrélation des requêtes
# --------------------------------------------------------------------------- #
# id de repli, commun à tous les appels non corrélés d'une même session serveur.
_ID_SESSION = uuid.uuid4().hex[:12]
_correlation_id = contextvars.ContextVar("correlation_id", default=None)


def definir_correlation_id(cid: str | None = None) -> str:
    """Fixe le correlation_id du traitement courant (en génère un si absent).

    À appeler au début d'un traitement (une ordonnance) : tous les appels
    d'outils qui suivent, quel que soit l'agent, porteront ce même id.
    """
    cid = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def correlation_id_courant() -> str:
    """Retourne le correlation_id actif (contextvar > env > id de session)."""
    return _correlation_id.get() or os.environ.get("MCP_CORRELATION_ID") or _ID_SESSION


def vider_journal() -> None:
    """Vide le journal : réécrit `journal_mcp.json` avec un tableau vide."""
    with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)


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


def tracer(permission: str = "inconnue", agent: str = "inconnu"):
    """Décorateur d'usine : trace l'appel d'un outil MCP.

    Args:
        permission: niveau de permission de l'outil
            (ex : "lecture", "ecriture", "suppression", "lecture_externe").
        agent: agent délégué qui exécute l'outil
            (ex : "Agent 1 — Triage SIH", "Agent 2 — Pharmacologue").
    """

    def decorateur(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            date_heure = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cid = correlation_id_courant()
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
                    "correlation_id": cid,
                    "agent": agent,
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
                    f"[MCP] {date_heure} | {cid} | {agent} | {func.__name__} | "
                    f"{permission} | {statut}",
                    flush=True,
                )
                # Trace fichier (journal_mcp.json)
                _ajouter_au_journal(entree)

        return wrapper

    return decorateur


if __name__ == "__main__":
    # `python journal.py` vide le journal.
    vider_journal()
    print(f"Journal vidé : {JOURNAL_PATH}")
