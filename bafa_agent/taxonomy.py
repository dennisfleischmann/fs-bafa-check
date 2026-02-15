from __future__ import annotations

from typing import Dict, List, Optional


def default_component_taxonomy() -> Dict[str, List[str]]:
    return {
        "aussenwand": ["aussenwand", "fassade", "wdvs", "wanddaemmung"],
        "dach": ["dach", "steildach", "flachdach", "aufsparrendaemmung"],
        "ogd": ["oberste geschossdecke", "ogd"],
        "fenster": ["fenster", "uw", "fenstertausch"],
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
    return " ".join(value.strip().lower().split())


def map_term(term: str, taxonomy: Dict[str, List[str]]) -> Optional[str]:
    token = normalize_token(term)
    for key, synonyms in taxonomy.items():
        if token == key:
            return key
        for synonym in synonyms:
            if synonym in token:
                return key
    return None


def map_component(term: str) -> Optional[str]:
    return map_term(term, default_component_taxonomy())


def map_cost_category(term: str) -> Optional[str]:
    return map_term(term, default_cost_taxonomy())
