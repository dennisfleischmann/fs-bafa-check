from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .utils import env_bool

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
MIN_CONFIDENCE_DEFAULT = 0.58


@dataclass(frozen=True)
class IntentEntry:
    item_code: str
    component: str
    measure_id: str
    category: str
    aliases: Tuple[str, ...]

    @property
    def embedding_text(self) -> str:
        return f"{self.item_code} {self.component} " + " ".join(self.aliases)


@dataclass
class SemanticMatch:
    item_code: str
    component: str
    measure_id: str
    category: str
    confidence: float
    method: str
    lexical_score: float
    embedding_score: Optional[float] = None


CATALOG: Tuple[IntentEntry, ...] = (
    IntentEntry(
        item_code="fenster_element",
        component="fenster",
        measure_id="envelope_fenster",
        category="material",
        aliases=(
            "fenster",
            "fenstertausch",
            "uw wert",
            "dreifachglas",
            "waermeschutzglas",
        ),
    ),
    IntentEntry(
        item_code="einbaufuge_daemmung",
        component="fenster",
        measure_id="envelope_fenster",
        category="material",
        aliases=(
            "daemmung der einbaufuge",
            "einbaufuge",
            "anschlussfuge",
            "fensteranschlussfuge",
            "fensteranschlussfugen",
            "pu schaum",
        ),
    ),
    IntentEntry(
        item_code="fugen_abdichtung",
        component="fenster",
        measure_id="envelope_fenster",
        category="montage",
        aliases=(
            "abdichtung der fugen",
            "fugenabdichtung",
            "fugendichtheit",
            "kompriband",
            "versiegelung",
            "schlagregendichter anschluss",
            "schlagregendicht",
            "anschluss aussen",
        ),
    ),
    IntentEntry(
        item_code="absturzsicherung_fenster",
        component="fenster",
        measure_id="envelope_fenster",
        category="montage",
        aliases=(
            "absturzsicherung in bestehende fensterfassade",
            "absturzsicherung fenster",
            "absturzsicherung",
        ),
    ),
    IntentEntry(
        item_code="fensterbank",
        component="fenster",
        measure_id="envelope_fenster",
        category="material",
        aliases=(
            "fensterbank",
            "fensterbaenke",
            "fensterbank liefern und montieren",
        ),
    ),
    IntentEntry(
        item_code="aussenwand_daemmung",
        component="aussenwand",
        measure_id="envelope_aussenwand",
        category="material",
        aliases=(
            "aussenwanddaemmung",
            "fassadendaemmung",
            "wdvs",
            "wanddaemmung",
            "fassade",
        ),
    ),
)

def _normalize_text(text: str) -> str:
    value = text.lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _stem_token(token: str) -> str:
    for suffix in ("innen", "ungen", "chen", "lich", "keit", "heit", "ung", "en", "er", "es", "e", "n", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _tokenize(text: str) -> Tuple[str, ...]:
    normalized = _normalize_text(text)
    tokens = [match.group(0) for match in TOKEN_PATTERN.finditer(normalized)]
    stemmed = [_stem_token(token) for token in tokens]
    return tuple(token for token in stemmed if len(token) >= 2)


def _alias_similarity(text_normalized: str, text_tokens: set[str], alias: str) -> float:
    alias_normalized = _normalize_text(alias)
    alias_tokens = set(_tokenize(alias_normalized))
    if not alias_tokens:
        return 0.0
    if alias_normalized and alias_normalized in text_normalized:
        return min(1.0, 0.86 + (0.02 * min(len(alias_tokens), 5)))

    overlap = len(text_tokens.intersection(alias_tokens))
    if overlap == 0:
        return 0.0

    precision = overlap / max(1, len(alias_tokens))
    recall = overlap / max(1, len(text_tokens))
    return (precision * 0.7) + (recall * 0.3)


def _lexical_rank(text: str) -> List[Tuple[IntentEntry, float]]:
    text_normalized = _normalize_text(text)
    text_tokens = set(_tokenize(text_normalized))
    ranked: List[Tuple[IntentEntry, float]] = []
    for entry in CATALOG:
        best = 0.0
        for alias in entry.aliases:
            best = max(best, _alias_similarity(text_normalized, text_tokens, alias))
        ranked.append((entry, best))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _embedding_enabled() -> bool:
    if not env_bool("BAFA_SEMANTIC_USE_EMBEDDINGS", default=False):
        return False
    return bool(os.getenv("OPENAI_API_KEY"))


@lru_cache(maxsize=1)
def _embedding_client() -> object | None:
    if not _embedding_enabled():
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        return None


@lru_cache(maxsize=256)
def _embed(text: str) -> Tuple[float, ...]:
    client = _embedding_client()
    if client is None:
        return tuple()
    model = os.getenv("BAFA_EMBEDDING_MODEL", "text-embedding-3-small")
    try:
        response = client.embeddings.create(model=model, input=text)
    except Exception:
        return tuple()
    if not getattr(response, "data", None):
        return tuple()
    vector = response.data[0].embedding
    return tuple(float(x) for x in vector)


def _embedding_rank(text: str) -> Dict[str, float]:
    query_embedding = list(_embed(_normalize_text(text)))
    if not query_embedding:
        return {}
    scores: Dict[str, float] = {}
    for entry in CATALOG:
        entry_embedding = list(_embed(entry.embedding_text))
        if not entry_embedding:
            continue
        scores[entry.item_code] = _cosine_similarity(query_embedding, entry_embedding)
    return scores


def _min_confidence() -> float:
    raw = os.getenv("BAFA_SEMANTIC_MIN_CONFIDENCE")
    if not raw:
        return MIN_CONFIDENCE_DEFAULT
    try:
        return float(raw)
    except ValueError:
        return MIN_CONFIDENCE_DEFAULT


def match_offer_line(text: str) -> Optional[SemanticMatch]:
    ranked = _lexical_rank(text)
    if not ranked:
        return None
    top_entry, lexical_top = ranked[0]
    method = "lexical"
    confidence = lexical_top
    embedding_score = None

    if _embedding_enabled() and lexical_top < 0.85:
        embedding_scores = _embedding_rank(text)
        if embedding_scores:
            method = "hybrid"
            embed_top = embedding_scores.get(top_entry.item_code, 0.0)
            embedding_score = embed_top
            confidence = max(lexical_top, (lexical_top * 0.65) + (embed_top * 0.35))
            embed_best_code = max(embedding_scores, key=embedding_scores.get)
            if embed_best_code != top_entry.item_code and embedding_scores.get(embed_best_code, 0.0) > confidence:
                fallback = next((entry for entry in CATALOG if entry.item_code == embed_best_code), None)
                if fallback is not None:
                    top_entry = fallback
                    confidence = embedding_scores[embed_best_code]
                    lexical_top = next((score for entry, score in ranked if entry.item_code == embed_best_code), 0.0)
                    embedding_score = confidence
                    method = "embedding"

    if confidence < _min_confidence():
        return None

    return SemanticMatch(
        item_code=top_entry.item_code,
        component=top_entry.component,
        measure_id=top_entry.measure_id,
        category=top_entry.category,
        confidence=round(confidence, 4),
        method=method,
        lexical_score=round(lexical_top, 4),
        embedding_score=round(embedding_score, 4) if embedding_score is not None else None,
    )
