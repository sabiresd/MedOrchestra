"""
Tableau de bord web — Interoperable Agent Hub (Co-Pilote de validation d'ordonnances).

Sert une interface temps réel qui lit le vrai `journal_mcp.json` (et MongoDB)
et affiche :
  - les KPI et le résultat de chaque exécution (verdict APPROVED / CRITICAL_ALERT) ;
  - l'historique des appels d'outils, regroupés par `correlation_id` ;
  - une simulation animée du parcours BPMN (Agent 1 — Triage SIH ⇆ Agent 2 —
    Pharmacologue), les nœuds s'allumant au fil des appels réellement tracés.

Le front interroge les endpoints toutes les ~1,5 s → réactivité « en direct ».

Lancement :
    python dashboard.py
    -> http://127.0.0.1:8050   (configurable via DASH_HOST / DASH_PORT)
"""

import asyncio
import json
import os
import re
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from journal import JOURNAL_PATH

try:
    from mongo_mcp import get_collection
except Exception:  # pragma: no cover - la base peut être indisponible
    get_collection = None

HERE = Path(__file__).parent
GRAVITES_MAJEURES = {"majeure", "contre-indiquee", "contre_indiquee"}


def _load_journal():
    try:
        data = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _flag(texte, cle):
    """Extrait la valeur booléenne d'une clé JSON dans un résultat (même tronqué)."""
    if not texte:
        return None
    m = re.search(rf'"{cle}"\s*:\s*(true|false)', texte)
    return (m.group(1) == "true") if m else None


def _premier_arg(entree, cle):
    """Récupère un argument d'appel qu'il soit passé en dict ou en liste positionnelle."""
    args = entree.get("arguments")
    if isinstance(args, dict) and cle in args:
        return args[cle]
    if isinstance(args, list) and args:
        return args[0]
    return None


def _safe_json(texte):
    try:
        return json.loads(texte)
    except Exception:
        return None


def _details(entries):
    """Extrait les détails métier d'une exécution à partir des résultats tracés."""
    d = {
        "patient": None,
        "molecules": [],
        "risque_majeur": None,
        "interactions": [],
        "alternative": None,
        "action": None,
        "sms": None,
    }
    for e in entries:
        outil = e.get("outil")
        res = _safe_json(e.get("resultat"))
        if outil == "recuperer_dossier_patient" and res:
            d["patient"] = res.get("patient")
            d["molecules"] = res.get("molecules") or d["molecules"]
        elif outil == "analyser_interactions" and res:
            d["risque_majeur"] = res.get("risque_majeur")
            d["interactions"] = res.get("interactions_detectees") or d["interactions"]
            d["molecules"] = res.get("molecules_analysees") or d["molecules"]
        elif outil == "rechercher_alternative" and res:
            d["alternative"] = res
        elif outil == "bloquer_preparation_pilulier" and res:
            av = (res.get("avant") or {}).get("statut")
            ap = (res.get("apres") or {}).get("statut")
            d["action"] = {"type": "bloquee", "avant": av, "apres": ap,
                           "motif": (res.get("apres") or {}).get("motif_blocage")}
        elif outil == "valider_ordonnance" and res:
            av = (res.get("avant") or {}).get("statut")
            ap = (res.get("apres") or {}).get("statut")
            d["action"] = {"type": "validee", "avant": av, "apres": ap, "motif": None}
        elif outil == "envoyer_sms_medecin":
            d["sms"] = e.get("resultat")
    return d


def _segmenter(journal):
    """Découpe le journal en exécutions : une nouvelle commence à chaque
    recuperer_dossier_patient ou à chaque changement de correlation_id.
    (Gère aussi les runs AgenticAI qui partagent un même correlation_id de session.)"""
    segments = []
    cur = None
    for e in journal:
        cid = e.get("correlation_id", "sans-id")
        nouveau = (
            cur is None
            or e.get("outil") == "recuperer_dossier_patient"
            or cid != cur["_cid"]
        )
        if nouveau:
            cur = {"_cid": cid, "entries": []}
            segments.append(cur)
        cur["entries"].append(e)
    return segments


def _grouper_runs(journal):
    """Découpe le journal en exécutions et dérive le verdict + les détails."""
    resultat = []
    for idx, seg in enumerate(_segmenter(journal)):
        entries = seg["entries"]
        cid = seg["_cid"]
        outils = [e.get("outil") for e in entries]

        # Verdict dérivé des outils réellement appelés / des drapeaux tracés.
        if "bloquer_preparation_pilulier" in outils:
            verdict = "CRITICAL_ALERT"
        elif "valider_ordonnance" in outils:
            verdict = "APPROVED"
        elif "analyser_interactions" in outils:
            rm = any(
                _flag(e.get("resultat"), "risque_majeur")
                for e in entries
                if e.get("outil") == "analyser_interactions"
            )
            verdict = "CRITICAL_ALERT" if rm else "APPROVED"
        elif "recuperer_dossier_patient" in outils:
            dv = any(
                _flag(e.get("resultat"), "dossier_valide")
                for e in entries
                if e.get("outil") == "recuperer_dossier_patient"
            )
            verdict = "EN_COURS" if dv else "DOSSIER_INCOMPLET"
        else:
            verdict = "EN_COURS"

        # Contexte patient / ordonnance.
        patient_id = None
        prescription_id = None
        dossier_valide = None
        risque_majeur = None
        for e in entries:
            if e.get("outil") == "recuperer_dossier_patient":
                patient_id = patient_id or _premier_arg(e, "patient_id")
                dv = _flag(e.get("resultat"), "dossier_valide")
                if dv is not None:
                    dossier_valide = dv
                m = re.search(r'"prescription_id"\s*:\s*"([^"]+)"', e.get("resultat") or "")
                if m:
                    prescription_id = m.group(1)
            if e.get("outil") in ("valider_ordonnance", "bloquer_preparation_pilulier"):
                prescription_id = prescription_id or _premier_arg(e, "prescription_id")
            if e.get("outil") == "analyser_interactions":
                rm = _flag(e.get("resultat"), "risque_majeur")
                if rm is not None:
                    risque_majeur = rm

        resultat.append(
            {
                "run_id": f"{cid}#{idx}",
                "correlation_id": cid,
                "verdict": verdict,
                "patient_id": patient_id,
                "prescription_id": prescription_id,
                "dossier_valide": dossier_valide,
                "risque_majeur": risque_majeur,
                "debut": entries[0].get("date_heure"),
                "fin": entries[-1].get("date_heure"),
                "nb_appels": len(entries),
                "agents": sorted({e.get("agent") for e in entries if e.get("agent")}),
                "details": _details(entries),
                "entries": entries,
            }
        )

    # Le plus récent en premier (par ordre d'apparition dans le journal).
    resultat.reverse()
    return resultat


async def page(request):
    return FileResponse(HERE / "dashboard.html")


async def api_runs(request):
    journal = _load_journal()
    runs = _grouper_runs(journal)
    kpi = {
        "runs": len(runs),
        "critical": sum(r["verdict"] == "CRITICAL_ALERT" for r in runs),
        "approved": sum(r["verdict"] == "APPROVED" for r in runs),
        "appels": len(journal),
    }
    return JSONResponse({"kpi": kpi, "runs": runs})


async def api_journal(request):
    return JSONResponse(_load_journal())


async def api_stream(request):
    """Flux SSE : pousse chaque nouvel appel d'outil dès qu'il est tracé dans le
    journal → synchronisation en temps réel avec l'exécution (Langflow/AgenticAI)."""

    async def gen():
        last = len(_load_journal())
        yield "retry: 2000\nevent: hello\ndata: {}\n\n"
        while True:
            if await request.is_disconnected():
                break
            journal = _load_journal()
            if len(journal) < last:  # journal vidé -> on repart de zéro
                last = 0
                yield "event: reset\ndata: {}\n\n"
            if len(journal) > last:
                for e in journal[last:]:
                    yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
                last = len(journal)
            await asyncio.sleep(0.6)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def api_prescriptions(request):
    if get_collection is None:
        return JSONResponse([])
    try:
        docs = list(
            get_collection("prescriptions").find(
                {}, {"_id": 0, "prescription_id": 1, "patient_id": 1, "statut": 1, "molecules": 1}
            )
        )
        return JSONResponse(docs)
    except Exception as e:
        return JSONResponse({"erreur": str(e)}, status_code=200)


app = Starlette(
    routes=[
        Route("/", page),
        Route("/api/runs", api_runs),
        Route("/api/journal", api_journal),
        Route("/api/stream", api_stream),
        Route("/api/prescriptions", api_prescriptions),
    ]
)


if __name__ == "__main__":
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("DASH_PORT", "8050"))
    print(f"Tableau de bord : http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
