# Contrats des outils MCP — SIH Pharmaceutique

Documentation du **contrat** de chaque outil exposé par le serveur MCP
`SIH_Pharma_MCP` : paramètres d'entrée, valeur de sortie, et **permission**.

Les outils implémentent le cas d'usage BPMN à deux agents :

- **Agent 1 — Triage et Exécution (SIH)** : `recuperer_dossier_patient`,
  `valider_ordonnance`, `bloquer_preparation_pilulier`, `envoyer_sms_medecin`.
- **Agent 2 — Pharmacologue Expert** : `analyser_interactions`,
  `rechercher_alternative`.

Base de données : `sih_mcp_db` — collections `patients`, `prescriptions`,
`interactions_medicamenteuses`.

Chaque appel est tracé dans la console et dans `journal_mcp.json` (voir
[journal.py](journal.py)). La permission indiquée ci-dessous est aussi
enregistrée dans chaque entrée du journal.

## Niveaux de permission

| Permission | Signification | Effet |
|---|---|---|
| `lecture` | Lecture de la base locale | Non destructif |
| `ecriture` | Création / modification en base | Modifie les données |
| `suppression` | Suppression en base | **Destructif** |
| `lecture_externe` | Appel d'une API tierce (web) | Non destructif, sort du réseau local |
| `ecriture_externe` | Action tierce avec effet (envoi SMS/email) | **Effet visible à l'extérieur** |

---

# Agent 1 — Triage et Exécution (SIH)

## 1. `recuperer_dossier_patient` — Dossier patient + ordonnance

- **Fichier** : [outil_dossier_patient.py](outil_dossier_patient.py)
- **Permission** : `lecture`
- **BPMN** : `sih.recuperer_dossier_patient()`

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `patient_id` | `str` | oui | — | Identifiant du patient (ex : "P-1024") |

- **Sortie** : `str` — JSON (profil + molécules + validité du dossier).
  ```json
  {"dossier_valide": true,
   "motif": null,
   "patient": {"patient_id": "P-1024", "nom": "Doe", "allergies": ["Pénicilline"]},
   "prescription_id": "ORD-5567",
   "molecules": ["Warfarine", "Aspirine"]}
  ```

---

## 2. `valider_ordonnance` — Validation (verdict APPROVED)

- **Fichier** : [outil_valider_ordonnance.py](outil_valider_ordonnance.py)
- **Permission** : `ecriture`
- **BPMN** : `sih.valider_ordonnance()`

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `prescription_id` | `str` | oui | — | Identifiant de l'ordonnance (ex : "ORD-5567") |

- **Sortie** : `str` — JSON avec l'état **avant** et **après** (statut `validee`).

---

## 3. `bloquer_preparation_pilulier` — Blocage (verdict CRITICAL_ALERT)

- **Fichier** : [outil_bloquer_pilulier.py](outil_bloquer_pilulier.py)
- **Permission** : `ecriture`
- **BPMN** : `sih.bloquer_preparation_pilulier()`

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `prescription_id` | `str` | oui | — | Identifiant de l'ordonnance |
| `motif` | `str` | non | `""` | Raison du blocage (interaction majeure…) |

- **Sortie** : `str` — JSON avec l'état **avant** et **après** (statut `bloquee`).

---

## 4. `envoyer_sms_medecin` — Alerte au médecin prescripteur

- **Fichier** : [outil_sms_medecin.py](outil_sms_medecin.py)
- **Permission** : `ecriture_externe` (**envoie une vraie notification**)
- **BPMN** : `notif.envoyer_sms_medecin()`
- **Authentification** : SMTP (STARTTLS, port 587) via App Password, lu depuis
  le fichier `.env` (`SMTP_*`, `EMAIL_*`) — jamais codé en dur.

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `message` | `str` | oui | — | Corps de l'alerte (interaction, alternative…) |
| `medecin` | `str` | non | `EMAIL_TO` (.env) | Destinataire ; vide = valeur du `.env` |
| `prescription_id` | `str` | non | `""` | Ordonnance concernée (ajoutée à l'objet) |

- **Sortie** : `str` — message de confirmation.
  ```
  Alerte envoyée au médecin dr@chu.fr (ordonnance : ORD-5567).
  ```

---

# Agent 2 — Pharmacologue Expert

## 5. `analyser_interactions` — Analyse des interactions

- **Fichier** : [outil_interactions.py](outil_interactions.py)
- **Permission** : `lecture`
- **BPMN** : `pharma.analyser_interactions()`

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `molecules` | `list[str]` | oui | — | Molécules prescrites (ex : `["Warfarine", "Aspirine"]`) |

- **Sortie** : `str` — JSON (interactions + drapeau `risque_majeur`).
  ```json
  {"molecules_analysees": ["Warfarine", "Aspirine"],
   "risque_majeur": true,
   "interactions_detectees": [
     {"molecule_a": "Warfarine", "molecule_b": "Aspirine",
      "gravite": "majeure", "alternative": "Paracétamol"}]}
  ```

---

## 6. `rechercher_alternative` — Alternative thérapeutique

- **Fichier** : [outil_alternative.py](outil_alternative.py)
- **Permission** : `lecture`
- **BPMN** : `pharma.rechercher_alternative()`

| Paramètre | Type | Requis | Défaut | Description |
|---|---|---|---|---|
| `molecule` | `str` | oui | — | Molécule à remplacer (ex : "Aspirine") |
| `molecule_en_conflit` | `str` | non | `""` | Molécule en interaction (affine la recherche) |

- **Sortie** : `str` — JSON avec l'alternative recommandée.
  ```json
  {"molecule": "Aspirine", "alternative": "Paracétamol",
   "gravite": "majeure", "commentaire": "Risque hémorragique avec la Warfarine"}
  ```

---

## Format du journal (`journal_mcp.json`)

Le journal est un **tableau JSON indenté** (blocs lisibles), mis à jour à
chaque appel d'outil. Chaque entrée porte un `correlation_id` (partagé par tous
les appels d'un même traitement, pour relier Agent 1 et Agent 2) et l'`agent`
délégué qui a exécuté l'outil :

```json
[
  {
    "date_heure": "2026-07-10 13:15:04",
    "correlation_id": "21d113df79c0",
    "agent": "Agent 2 — Pharmacologue",
    "outil": "analyser_interactions",
    "permission": "lecture",
    "arguments": {
      "molecules": ["Warfarine", "Aspirine"]
    },
    "statut": "succes",
    "resultat": "{\"risque_majeur\": true, ...}"
  }
]
```

En cas d'échec, un champ `"erreur"` est ajouté à l'entrée.

- `correlation_id` : défini via `definir_correlation_id()`, sinon la variable
  d'environnement `MCP_CORRELATION_ID`, sinon un id de session.
- Le journal se vide avec `vider_journal()` (ou `python journal.py`).
