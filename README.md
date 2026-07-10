# MedOrchestra

**Orchestration multi-agents (A2A) pour la validation d'ordonnances hospitalières.**

MedOrchestra implémente un processus BPMN à deux agents qui collaborent via le
protocole **A2A (Agent-to-Agent)** pour sécuriser la préparation des piluliers
dans un Système d'Information Hospitalier (SIH) :

- **Agent 1 — Triage et Exécution (SIH)** : récupère et valide le dossier
  patient, délègue l'expertise pharmaceutique, puis applique le verdict.
- **Agent 2 — Pharmacologue Expert** : analyse les interactions
  médicamenteuses, propose une alternative en cas de risque majeur, et renvoie
  un verdict `APPROVED` ou `CRITICAL_ALERT`.

Les agents sont des flux **Langflow** (plateforme abafusion.ai) et s'appuient
sur un **serveur MCP** exposant des outils métier connectés à **MongoDB**.

---

## Architecture

```
                     A2A (discover / delegate)
   ┌───────────────────────┐   demande d'expertise   ┌──────────────────────────┐
   │  Agent 1 — Triage SIH  │ ─────────────────────▶ │  Agent 2 — Pharmacologue │
   │  (A2A_Triage_SIH)      │ ◀───────────────────── │  (A2A_Pharmacologue)     │
   └───────────┬────────────┘   rapport (verdict)    └─────────────┬────────────┘
               │                                                    │
               │  outils MCP                            outils MCP  │
               ▼                                                    ▼
        ┌───────────────────────────  Serveur MCP  ───────────────────────────┐
        │  recuperer_dossier_patient   valider_ordonnance                      │
        │  bloquer_preparation_pilulier  envoyer_sms_medecin                   │
        │  analyser_interactions        rechercher_alternative                 │
        └──────────────────────────────────┬───────────────────────────────────┘
                                            ▼
                                   MongoDB  `sih_mcp_db`
                       (patients · prescriptions · interactions_medicamenteuses)
```

### Déroulé du processus (BPMN)

1. **Ordonnance soumise** → Agent 1 appelle `recuperer_dossier_patient()`.
2. **Données patient valides ?**
   - Non → *Échec : dossier incomplet*.
   - Oui → Agent 1 envoie la **demande d'expertise** (molécules + profil) à
     l'Agent 2.
3. L'Agent 2 appelle `analyser_interactions()`.
   - **Risque majeur détecté ?**
     - Oui → `rechercher_alternative()` → rapport **`CRITICAL_ALERT`** + alternative.
     - Non → rapport **`APPROVED`**.
4. Agent 1 **analyse le verdict** :
   - `APPROVED` → `valider_ordonnance()` → *Traitement validé*.
   - `CRITICAL_ALERT` → `bloquer_preparation_pilulier()` + `envoyer_sms_medecin()`
     → *Ordonnance rejetée sûre*.

---

## Structure du dépôt

| Fichier / dossier | Rôle |
|---|---|
| `A2A_Triage_SIH.json` | Flux Langflow — **Agent 1** (orchestrateur) |
| `A2A_Pharmacologue.json` | Flux Langflow — **Agent 2** (expert) |
| `agent_cards/triage_sih.json` | Agent card de l'Agent 1 (A2A) |
| `agent_cards/pharmacologue.json` | Agent card de l'Agent 2 (A2A) |
| `mcp_server.py` | Point d'entrée du serveur MCP (SSE) |
| `mongo_mcp.py` | Connexion MongoDB + instance MCP partagée |
| `journal.py` | Traçage des appels d'outils (`journal_mcp.json`) |
| `seed_db.py` | Peuplement de la base de démonstration |
| `CONTRATS.md` | Contrat détaillé de chaque outil MCP |
| **Outils — Agent 1** | |
| `outil_dossier_patient.py` | `recuperer_dossier_patient` (lecture) |
| `outil_valider_ordonnance.py` | `valider_ordonnance` (écriture) |
| `outil_bloquer_pilulier.py` | `bloquer_preparation_pilulier` (écriture) |
| `outil_sms_medecin.py` | `envoyer_sms_medecin` (écriture externe, SMTP) |
| **Outils — Agent 2** | |
| `outil_interactions.py` | `analyser_interactions` (lecture) |
| `outil_alternative.py` | `rechercher_alternative` (lecture) |

---

## Base de données (`sih_mcp_db`)

| Collection | Clé | Champs principaux |
|---|---|---|
| `patients` | `patient_id` | `nom`, `age`, `allergies[]`, `pathologies[]`, `traitement_en_cours[]`, `medecin_referent` |
| `prescriptions` | `prescription_id` | `patient_id`, `molecules[]`, `statut`, `preparation_pilulier` |
| `interactions_medicamenteuses` | `(molecule_a, molecule_b)` | `gravite`, `alternative`, `description` |

`gravite ∈ {mineure, moderee, majeure, contre-indiquee}` — `majeure` et
`contre-indiquee` déclenchent un **risque majeur**.

---

## Outils MCP

| Outil | Agent | Permission | Correspondance BPMN |
|---|---|---|---|
| `recuperer_dossier_patient` | 1 | `lecture` | `sih.recuperer_dossier_patient()` |
| `valider_ordonnance` | 1 | `ecriture` | `sih.valider_ordonnance()` |
| `bloquer_preparation_pilulier` | 1 | `ecriture` | `sih.bloquer_preparation_pilulier()` |
| `envoyer_sms_medecin` | 1 | `ecriture_externe` | `notif.envoyer_sms_medecin()` |
| `analyser_interactions` | 2 | `lecture` | `pharma.analyser_interactions()` |
| `rechercher_alternative` | 2 | `lecture` | `pharma.rechercher_alternative()` |

Le contrat complet (paramètres, sorties, exemples) est documenté dans
[`CONTRATS.md`](CONTRATS.md). Chaque appel est tracé dans `journal_mcp.json`.

---

## Prérequis

- Python 3.10+
- Une base MongoDB (MongoDB Atlas ou instance locale)
- Un compte SMTP (App Password Gmail) pour la notification médecin

## Installation

```bash
git clone https://github.com/sabiresd/MedOrchestra.git
cd MedOrchestra

python -m venv .venv
# Windows : .venv\Scripts\activate   |   macOS/Linux : source .venv/bin/activate

pip install -r requirements.txt
```

## Configuration

Copiez `.env.example` en `.env` et renseignez vos valeurs (le fichier `.env`
est ignoré par Git et ne doit **jamais** être committé) :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `MONGODB_URI` | Chaîne de connexion MongoDB (avec identifiants) |
| `MONGODB_DB` | Nom de la base (défaut : `sih_mcp_db`) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USE_TLS` | Serveur SMTP |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Identifiants SMTP (App Password) |
| `EMAIL_FROM` / `EMAIL_TO` | Expéditeur / médecin destinataire par défaut |

## Utilisation

**1. Peupler la base de démonstration** (idempotent) :

```bash
python seed_db.py
```

**2. Lancer le serveur MCP** (transport SSE sur `http://127.0.0.1:8000/sse`) :

```bash
python mcp_server.py
```

**3. Importer les flux dans Langflow / abafusion.ai** :
importez `A2A_Triage_SIH.json` et `A2A_Pharmacologue.json`, puis connectez le
serveur MCP aux agents. Les agents se découvrent via l'action `discover` et
échangent la demande d'expertise via `delegate`.

## Tester le workflow

Le script `test_workflow.py` rejoue **toute la logique BPMN** (Agent 1 ⇆
Agent 2) en appelant réellement les outils MCP, avec un `correlation_id` par
ordonnance. Il ré-initialise la base et vide le journal à chaque exécution, il
est donc **rejouable** :

```bash
python test_workflow.py            # ordonnances de démo : CRITICAL_ALERT + APPROVED
python test_workflow.py P-1024     # un patient précis
python test_workflow.py --sms      # envoie réellement le SMS/e-mail médecin
```

En sortie, le journal `journal_mcp.json` montre, pour chaque appel, le
`correlation_id` (qui relie les actions d'un même traitement) et l'`agent`
délégué qui a exécuté l'outil :

```json
{
  "date_heure": "2026-07-10 12:01:15",
  "correlation_id": "21d113df79c0",
  "agent": "Agent 2 — Pharmacologue",
  "outil": "analyser_interactions",
  "permission": "lecture",
  "arguments": [["Warfarine", "Aspirine", "Oméprazole"]],
  "statut": "succes",
  "resultat": "{\"risque_majeur\": true, ...}"
}
```

Pour **vider le journal** manuellement :

```bash
python journal.py                  # réécrit journal_mcp.json avec []
```

Corréler des appels hors test : appelez `definir_correlation_id("mon-id")` en
début de traitement, ou exportez `MCP_CORRELATION_ID` avant de lancer le
serveur.

## Tableau de bord temps réel

`dashboard.py` sert une interface web (Starlette/uvicorn, **aucune dépendance
supplémentaire**) qui lit le vrai `journal_mcp.json` et MongoDB :

```bash
python dashboard.py      # -> http://127.0.0.1:8050  (DASH_HOST / DASH_PORT configurables)
```

Elle affiche :
- les **KPI** (ordonnances traitées, alertes critiques, traitements validés, appels MCP) ;
- une **simulation animée du parcours BPMN** (Agent 1 — Triage SIH ⇆ Agent 2 —
  Pharmacologue) : les nœuds s'allument au fil des appels réellement tracés,
  et le verdict (`APPROVED` / `CRITICAL_ALERT`) est rejoué en direct ;
- l'**historique** des exécutions regroupées par `correlation_id` (cliquables
  pour rejouer le parcours) ;
- l'**état des ordonnances** (`en_attente` / `validee` / `bloquee`) et le
  **journal** des appels d'outils en flux continu (rafraîchi toutes les ~1,5 s).

Pour la voir vivre : laisser le dashboard ouvert et lancer `python test_workflow.py`
(ou envoyer une demande depuis AgenticAI) — le parcours s'anime en temps réel.

### Exemple de bout en bout

L'ordonnance de démonstration **ORD-5567** (patient `P-1024` :
Warfarine + Aspirine + Oméprazole) déclenche le chemin critique :

```
dossier_valide = true
  → analyser_interactions  ⇒ risque_majeur = true  (Aspirine + Warfarine : majeure)
  → rechercher_alternative ⇒ Paracétamol
  → verdict CRITICAL_ALERT ⇒ bloquer_preparation_pilulier + envoyer_sms_medecin
```

L'ordonnance **ORD-5568** (`P-2048` : Metformine + Paracétamol) suit, elle, le
chemin `APPROVED` → `valider_ordonnance`.

---

## Traçabilité

Chaque appel d'outil est journalisé dans `journal_mcp.json` (date, outil,
permission, arguments, statut, résultat) via le décorateur `@tracer(...)` de
[`journal.py`](journal.py). Les niveaux de permission (`lecture`, `ecriture`,
`suppression`, `lecture_externe`, `ecriture_externe`) permettent d'auditer les
actions sensibles (écritures en base, envoi de notifications).

---

## Sécurité

- Les secrets (URI MongoDB, identifiants SMTP) sont lus depuis `.env`, **jamais**
  committés (voir `.gitignore`).
- Les outils à effet de bord (`ecriture`, `ecriture_externe`) sont explicitement
  marqués et tracés.
