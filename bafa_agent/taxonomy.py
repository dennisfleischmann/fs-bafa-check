from __future__ import annotations

import re
from typing import Dict, List, Optional


def default_component_taxonomy() -> Dict[str, List[str]]:
    return {
        "aussenwand": ["aussenwand", "fassade", "fassadendaemmung", "wdvs", "wanddaemmung"],
        "dach": ["dach", "steildach", "flachdach", "aufsparrendaemmung"],
        "ogd": ["oberste geschossdecke", "ogd"],
        "fenster": [
            "fenster",
            "uw",
            "fenstertausch",
            "einbaufuge",
            "anschlussfuge",
            "fensteranschlussfuge",
            "kompriband",
            "versiegelung",
            "schlagregendicht",
        ],
        "kellerdecke": ["kellerdecke", "bodenplatte"],
    }


def default_cost_taxonomy() -> Dict[str, List[str]]:
    return {
        "material": ["material", "daemmung", "platten", "profil"],
        "montage": ["montage", "einbau", "installation", "arbeit"],
        "geruest": ["geruest", "geruestbau"],
        "entsorgung": ["entsorgung", "abtransport"],
        "planung": ["planung", "beratung"],
        "wartung": ["wartung", "service"],
        "finanzierung": ["kredit", "zinsen", "finanzierung"],
        "eigenleistung": ["eigenleistung", "selbstleistung"],
    }


def normalize_token(value: str) -> str:
    token = value.strip().lower()
    token = token.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    token = re.sub(r"[^a-z0-9]+", " ", token)
    return " ".join(token.split())


def map_term(term: str, taxonomy: Dict[str, List[str]]) -> Optional[str]:
    token = normalize_token(term)
    if not token:
        return None

    best_key: Optional[str] = None
    best_score = 0
    for key, synonyms in taxonomy.items():
        normalized_key = normalize_token(key)
        score = 0
        if token == normalized_key:
            score += 100

        if normalized_key and normalized_key in token:
            score += max(1, len(normalized_key))

        for synonym in synonyms:
            normalized_synonym = normalize_token(synonym)
            if not normalized_synonym:
                continue
            if normalized_synonym in token:
                score += max(1, len(normalized_synonym))
            synonym_tokens = set(normalized_synonym.split())
            token_tokens = set(token.split())
            overlap = len(synonym_tokens.intersection(token_tokens))
            score += overlap * 2

        if score > best_score:
            best_score = score
            best_key = key

    if best_score <= 0:
        return None
    return best_key


def map_component(term: str) -> Optional[str]:
    return map_term(term, default_component_taxonomy())


def map_cost_category(term: str) -> Optional[str]:
    return map_term(term, default_cost_taxonomy())
