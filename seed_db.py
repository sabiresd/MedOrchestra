"""Peuplement de la base `sih_mcp_db` (données de démonstration).

Insère des jeux de données cohérents avec les outils MCP et le cas d'usage
BPMN (Triage SIH ⇆ Pharmacologue) :

    - patients                     (profils : allergies, pathologies, âge…)
    - prescriptions                (ordonnances : molécules, statut, pilulier)
    - interactions_medicamenteuses (interactions connues + alternatives)

Le script est IDEMPOTENT : chaque document est inséré via un upsert sur sa clé
naturelle (`patient_id`, `prescription_id`, ou la paire de molécules). On peut
donc le relancer sans créer de doublons.

Lancement :
    python seed_db.py
"""

from mongo_mcp import get_collection, get_db

# --------------------------------------------------------------------------- #
# 1. Patients
# --------------------------------------------------------------------------- #
PATIENTS = [
    {
        "patient_id": "P-1024",
        "nom": "Bennani",
        "prenom": "Youssef",
        "age": 72,
        "sexe": "M",
        "allergies": ["Pénicilline"],
        "pathologies": ["Fibrillation auriculaire", "Hypertension"],
        "traitement_en_cours": ["Warfarine"],
        "medecin_referent": "dr.amrani@chu.example",
    },
    {
        "patient_id": "P-2048",
        "nom": "El Fassi",
        "prenom": "Salma",
        "age": 45,
        "sexe": "F",
        "allergies": [],
        "pathologies": ["Diabète type 2"],
        "traitement_en_cours": ["Metformine"],
        "medecin_referent": "dr.tazi@chu.example",
    },
    {
        "patient_id": "P-3072",
        "nom": "Ouhadi",
        "prenom": "Karim",
        "age": 60,
        "sexe": "M",
        "allergies": ["Sulfamides"],
        "pathologies": ["Hypercholestérolémie"],
        "traitement_en_cours": ["Simvastatine"],
        "medecin_referent": "dr.amrani@chu.example",
    },
]

# --------------------------------------------------------------------------- #
# 2. Prescriptions (ordonnances)
# --------------------------------------------------------------------------- #
PRESCRIPTIONS = [
    {
        # Cas CRITICAL_ALERT attendu : Warfarine + Aspirine = interaction majeure.
        "prescription_id": "ORD-5567",
        "patient_id": "P-1024",
        "medecin": "dr.amrani@chu.example",
        "date": "2026-07-10",
        "molecules": ["Warfarine", "Aspirine", "Oméprazole"],
        "statut": "en_attente",
        "preparation_pilulier": None,
    },
    {
        # Cas APPROVED attendu : pas d'interaction majeure.
        "prescription_id": "ORD-5568",
        "patient_id": "P-2048",
        "medecin": "dr.tazi@chu.example",
        "date": "2026-07-10",
        "molecules": ["Metformine", "Paracétamol"],
        "statut": "en_attente",
        "preparation_pilulier": None,
    },
    {
        # Cas CRITICAL_ALERT : Simvastatine + Clarithromycine = interaction majeure.
        "prescription_id": "ORD-5569",
        "patient_id": "P-3072",
        "medecin": "dr.amrani@chu.example",
        "date": "2026-07-10",
        "molecules": ["Simvastatine", "Clarithromycine"],
        "statut": "en_attente",
        "preparation_pilulier": None,
    },
]

# --------------------------------------------------------------------------- #
# 3. Interactions médicamenteuses (référentiel)
#    gravite ∈ {mineure, moderee, majeure, contre-indiquee}
#    (majeure / contre-indiquee => risque majeur pour l'outil analyser_interactions)
# --------------------------------------------------------------------------- #
INTERACTIONS = [
    {
        "molecule_a": "Aspirine",
        "molecule_b": "Warfarine",
        "gravite": "majeure",
        "alternative": "Paracétamol",
        "description": "Majoration du risque hémorragique (potentialisation des anticoagulants).",
    },
    {
        "molecule_a": "Oméprazole",
        "molecule_b": "Warfarine",
        "gravite": "moderee",
        "alternative": "Pantoprazole",
        "description": "L'oméprazole peut augmenter l'effet anticoagulant de la warfarine (INR à surveiller).",
    },
    {
        "molecule_a": "Aspirine",
        "molecule_b": "Oméprazole",
        "gravite": "mineure",
        "alternative": None,
        "description": "Interaction mineure sans conséquence clinique notable.",
    },
    {
        "molecule_a": "Clarithromycine",
        "molecule_b": "Simvastatine",
        "gravite": "contre-indiquee",
        "alternative": "Pravastatine",
        "description": "Risque majeur de rhabdomyolyse (inhibition du CYP3A4).",
    },
    {
        "molecule_a": "Metformine",
        "molecule_b": "Paracétamol",
        "gravite": "mineure",
        "alternative": None,
        "description": "Aucune interaction cliniquement significative.",
    },
    {
        "molecule_a": "Ibuprofène",
        "molecule_b": "Warfarine",
        "gravite": "majeure",
        "alternative": "Paracétamol",
        "description": "AINS + anticoagulant : risque hémorragique digestif accru.",
    },
]


def seed():
    db = get_db()
    print(f"Connexion à la base : {db.name}")

    # patients
    col = get_collection("patients")
    for p in PATIENTS:
        col.replace_one({"patient_id": p["patient_id"]}, p, upsert=True)
    print(f"  patients                     : {col.count_documents({})} documents")

    # prescriptions
    col = get_collection("prescriptions")
    for o in PRESCRIPTIONS:
        col.replace_one({"prescription_id": o["prescription_id"]}, o, upsert=True)
    print(f"  prescriptions                : {col.count_documents({})} documents")

    # interactions_medicamenteuses (clé = paire triée)
    col = get_collection("interactions_medicamenteuses")
    for i in INTERACTIONS:
        a, b = sorted([i["molecule_a"], i["molecule_b"]])
        i["molecule_a"], i["molecule_b"] = a, b
        col.replace_one({"molecule_a": a, "molecule_b": b}, i, upsert=True)
    print(f"  interactions_medicamenteuses : {col.count_documents({})} documents")

    print("Peuplement terminé.")


if __name__ == "__main__":
    seed()
