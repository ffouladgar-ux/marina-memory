"""Deterministic compartment router.

No model, no API key, no cost: a scored lexicon (EN + FR) picks the
compartment. Policy is the important part, not the accuracy:

  * score <  THRESHOLD  -> `inbox`   (never guess, never drop)
  * score >= THRESHOLD  -> best compartment

A mis-filed note is cheap (she can refile, one line of Markdown).
A silently dropped note is expensive. Bias accordingly.
"""
from __future__ import annotations

import re
import unicodedata

COMPARTMENTS = ("business", "studies", "people", "personal", "health", "inbox")

STRONG, MEDIUM, WEAK = 3.0, 1.0, 0.5
THRESHOLD = 3.0  # one STRONG marker is enough; matches the parent system's tuning

LEXICON: dict[str, dict[str, list[str]]] = {
    "business": {
        "strong": ["client", "clients", "invoice", "facture", "contract", "contrat",
                   "invoice", "revenue", "chiffre d'affaires", "quote", "devis",
                   "proposal", "proposition", "siret", "company", "entreprise",
                   "freelance", "mission", "paid", "paiement", "billable",
                   "my business", "mon entreprise", "portfolio", "pitch",
                   "rate card", "interview confirmed", "owed"],
        "medium": ["price", "prix", "offer", "offre", "launch", "lancement", "brand",
                   "marque", "marketing", "sales", "ventes", "budget", "cost",
                   "tarif", "pricing", "meeting with a client", "deal",
                   "magazine", "editor at", "published", "article"],
        "weak": ["email", "mail", "linkedin", "site", "website", "logo", "tax", "tva"],
    },
    "studies": {
        "strong": ["journalist", "journaliste", "journalism", "journalisme",
                   "journalist school", "école de journalisme", "master", "degree",
                   "diplôme", "thesis", "mémoire", "exam", "examen", "concours",
                   "assignment", "devoir", "dissertation", "professor", "professeur",
                   "syllabus", "curriculum", "coursework", "grade", "note de cours",
                   "deadline for school", "école", "université", "university",
                   "internship report", "rapport de stage"],
        "medium": ["course", "cours", "class", "classe", "lecture", "student",
                   "étudiante", "study", "révision", "revise", "revision",
                   "bibliography", "reading list", "semester", "semestre", "exam prep",
                   "stage", "internship", "training", "formation"],
        "weak": ["read", "lire", "notes", "chapter", "chapitre", "book", "livre"],
    },
    "people": {
        "strong": ["my friend", "mon ami", "mon amie", "my mother", "ma mère",
                   "my father", "mon père", "my sister", "ma sœur", "my brother",
                   "mon frère", "birthday", "anniversaire de", "met with",
                   "rencontré", "her number", "his number", "son numéro",
                   "marina's", "mother-in-law", "mother in law",
                   "photographer", "photographe"],
        "medium": ["friend", "ami", "amie", "colleague", "collègue", "neighbour",
                   "voisin", "contact", "recommended by", "introduced me",
                   "classmate", "cameraman", "fixer"],
        "weak": ["number", "numéro", "phone", "téléphone", "address", "adresse"],
    },
    "personal": {
        "strong": ["my flat", "mon appartement", "my apartment", "rent", "loyer",
                   "insurance", "assurance", "my bank", "ma banque", "landlord",
                   "propriétaire", "moving", "déménagement", "holiday booked",
                   "vacances réservées", "my passport", "mon passeport",
                   "passport", "passeport", "visa",
                   "tax return", "déclaration d'impôts"],
        "medium": ["home", "maison", "travel", "voyage", "trip", "flight", "vol",
                   "train", "admin", "paperwork", "gym", "sport", "hobby", "hobbies",
                   "budget perso", "groceries", "courses",
                   "train to", "booked", "expires in", "renewal"],
        "weak": ["family", "famille", "visit", "weekend"],
    },
    "health": {
        "strong": ["diagnosis", "diagnostic", "symptom", "symptômes", "surgery",
                   "chirurgie", "medication", "médicament", "prescription",
                   "ordonnance", "doctor appointment", "chez le médecin",
                   "checkup", "blood test", "prise de sang", "migraine",
                   "therapy", "thérapie", "my memory", "ma mémoire",
                   "concentration", "attention", "fatigue", "burnout",
                   "anxiety", "anxiété", "sleep", "sommeil", "neurologist",
                   "the gp", "thyroid"],
        "medium": ["doctor", "médecin", "health", "santé", "pain", "douleur",
                   "allergy", "allergie", "meditation", "méditation", "stress",
                   "memory", "mémoire", "diet", "régime", "vitamins"],
        "weak": ["tired", "fatigué", "rest", "repos", "water", "eau"],
    },
}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def scores(text: str) -> dict[str, float]:
    n = _norm(text)
    out: dict[str, float] = {}
    for comp, tiers in LEXICON.items():
        s = 0.0
        for word in tiers["strong"]:
            if _norm(word) in n:
                s += STRONG
        for word in tiers["medium"]:
            if _norm(word) in n:
                s += MEDIUM
        for word in tiers["weak"]:
            if _norm(word) in n:
                s += WEAK
        if s:
            out[comp] = s
    return out


def route(text: str, explicit: str | None = None, default: str = "inbox") -> tuple[str, float]:
    """Return (compartment, score). Explicit always wins."""
    if explicit and explicit in COMPARTMENTS:
        return explicit, 99.0
    if explicit and explicit == "sources":
        return explicit, 99.0
    s = scores(text)
    if not s:
        return default, 0.0
    best = max(s, key=lambda k: s[k])
    if s[best] < THRESHOLD:
        return default, s[best]
    return best, s[best]
