from __future__ import annotations

import html as html_lib
import re
import shutil
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from .models import Manifest, ManifestDocument
from .utils import read_json, safe_slug, sha256_file, utc_now_iso, write_json

BAFA_OVERVIEW_URL = (
    "https://www.bafa.de/DE/Energie/Effiziente_Gebaeude/Foerderprogramm_im_Ueberblick/"
    "foerderprogramm_im_ueberblick_node.html"
)


def default_source_registry() -> List[Dict[str, Any]]:
    return [
        {
            "doc_id": "beg_em_richtlinie",
            "title": "BEG EM Richtlinie",
            "source_url": "",
            "local_path": "conversion.txt",
            "version_hint": "BAnz AT 29.12.2023 B1",
            "valid_from": "2023-12-21",
            "priority": 100,
            "module_tags": ["envelope", "heating"],
            "normative": True,
        },
        {
            "doc_id": "infoblatt_sanieren",
            "title": "Infoblatt foerderfaehige Massnahmen",
            "source_url": "",
            "local_path": "conversion.txt",
            "version_hint": "10.0",
            "valid_from": "2025-07-01",
            "priority": 80,
            "module_tags": ["envelope", "heating"],
            "normative": False,
        },
        {
            "doc_id": "merkblatt_antragstellung",
            "title": "Allgemeines Merkblatt Antragstellung",
            "source_url": "",
            "local_path": "conversion.txt",
            "version_hint": "2025-02",
            "valid_from": "2025-02-01",
            "priority": 60,
            "module_tags": ["envelope", "heating", "bonus"],
            "normative": False,
        },
    ]


def bafa_source_registry(source_url: str = BAFA_OVERVIEW_URL) -> List[Dict[str, Any]]:
    """
    Build BAFA source registry.

    Strategy:
    1) Try to scrape current PDF links from BAFA overview page.
    2) Fallback to known stable BAFA download paths from the provided page snippet.
    """
    links = _extract_bafa_pdf_links(source_url)
    return [
        {
            "doc_id": "beg_em_richtlinie",
            "title": "BEG EM Richtlinie",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_richtline_beg_em", "beg_richtlinie_beg_em"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_richtline_beg_em_20231221_PDF.pdf"
                    "?__blob=publicationFile&v=2"
                ),
                source_url=source_url,
            ),
            "filename": "beg_em_richtlinie.pdf",
            "version_hint": "BAnz AT 29.12.2023 B1",
            "valid_from": "2023-12-21",
            "priority": 100,
            "module_tags": ["envelope", "heating"],
            "normative": True,
        },
        {
            "doc_id": "infoblatt_sanieren",
            "title": "Infoblatt foerderfaehige Massnahmen und Leistungen - Sanieren",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_infoblatt_foerderfaehige_kosten"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_infoblatt_foerderfaehige_kosten.pdf"
                    "?__blob=publicationFile&v=12"
                ),
                source_url=source_url,
            ),
            "filename": "beg_infoblatt_sanieren.pdf",
            "version_hint": "Infoblatt Sanieren",
            "valid_from": None,
            "priority": 80,
            "module_tags": ["envelope", "heating"],
            "normative": False,
        },
        {
            "doc_id": "merkblatt_antragstellung",
            "title": "Allgemeines Merkblatt Antragstellung",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_merkblatt_allgemein_antragstellung"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_merkblatt_allgemein_antragstellung.pdf"
                    "?__blob=publicationFile&v=10"
                ),
                source_url=source_url,
            ),
            "filename": "beg_merkblatt_antragstellung.pdf",
            "version_hint": "Merkblatt Antragstellung",
            "valid_from": None,
            "priority": 60,
            "module_tags": ["envelope", "heating", "bonus"],
            "normative": False,
        },
        {
            "doc_id": "merkblatt_zusatzantrag_bonus",
            "title": "Merkblatt Zusatzantrag Einkommensbonus",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_merkblatt_allgemein_zusatzantrag"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_merkblatt_allgemein_zusatzantrag.pdf"
                    "?__blob=publicationFile&v=3"
                ),
                source_url=source_url,
            ),
            "filename": "beg_merkblatt_zusatzantrag_bonus.pdf",
            "version_hint": "Merkblatt Zusatzantrag",
            "valid_from": None,
            "priority": 50,
            "module_tags": ["bonus"],
            "normative": False,
        },
        {
            "doc_id": "merkblatt_gebaeudenetze",
            "title": "Merkblatt Gebaeudenetze",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_merkblatt_antragstellung_wnet_gnet"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_merkblatt_antragstellung_wnet_gnet.pdf"
                    "?__blob=publicationFile&v=20"
                ),
                source_url=source_url,
            ),
            "filename": "beg_merkblatt_gebaeudenetze.pdf",
            "version_hint": "Merkblatt Gebaeudenetze",
            "valid_from": None,
            "priority": 40,
            "module_tags": ["heating"],
            "normative": False,
        },
        {
            "doc_id": "checkliste_hydraulischer_abgleich",
            "title": "Checkliste Gleichwertigkeit hydraulischer Abgleich",
            "source_url": _pick_bafa_link(
                links,
                preferred_tokens=["beg_checkliste_gleichwertigkeit"],
                fallback_path=(
                    "/SharedDocs/Downloads/DE/Energie/beg_checkliste_gleichwertigkeit.pdf"
                    "?__blob=publicationFile&v=2"
                ),
                source_url=source_url,
            ),
            "filename": "beg_checkliste_gleichwertigkeit.pdf",
            "version_hint": "Checkliste Gleichwertigkeit",
            "valid_from": None,
            "priority": 40,
            "module_tags": ["heating"],
            "normative": False,
        },
    ]


def save_source_registry(path: str | Path, registry: List[Dict[str, Any]]) -> None:
    write_json(path, registry)


def load_source_registry(path: str | Path) -> List[Dict[str, Any]]:
    payload = read_json(path, default=[])
    if not isinstance(payload, list):
        raise ValueError("source registry must be a list")
    return payload


def _download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BAFA-Agent-Bot/1.0)"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _resolve_local_source(entry: Dict[str, Any], download_dir: Path, fetch: bool) -> Path:
    local = entry.get("local_path")
    if local:
        return Path(local)
    source_url = entry.get("source_url", "")
    if not source_url:
        raise ValueError(f"entry {entry.get('doc_id')} missing source_url/local_path")
    filename = entry.get("filename")
    if not filename:
        parsed = urlparse(source_url)
        filename = Path(parsed.path).name or f"{entry['doc_id']}.pdf"
    target = download_dir / filename
    if fetch or not target.exists():
        _download_file(source_url, target)
    return target


def build_manifest(
    registry: List[Dict[str, Any]],
    download_dir: str | Path,
    manifest_path: str | Path,
    fetch: bool = False,
) -> Manifest:
    download_dir = Path(download_dir)
    docs: List[ManifestDocument] = []
    for entry in registry:
        local_path = _resolve_local_source(entry, download_dir, fetch)
        doc = ManifestDocument(
            doc_id=entry["doc_id"],
            source_url=entry.get("source_url", ""),
            download_date=utc_now_iso(),
            version_hint=entry.get("version_hint", ""),
            valid_from=entry.get("valid_from"),
            sha256=sha256_file(local_path),
            priority=int(entry.get("priority", 0)),
            module_tags=list(entry.get("module_tags", [])),
            normative=bool(entry.get("normative", False)),
            local_path=str(local_path),
        )
        docs.append(doc)
    manifest = Manifest(generated_at=utc_now_iso(), docs=docs)
    write_json(manifest_path, {
        "generated_at": manifest.generated_at,
        "docs": [asdict(item) for item in manifest.docs],
    })
    return manifest


def load_manifest(path: str | Path) -> Manifest:
    payload = read_json(path, default={})
    docs: List[ManifestDocument] = []
    for item in payload.get("docs", []):
        docs.append(ManifestDocument(**item))
    return Manifest(generated_at=payload.get("generated_at", ""), docs=docs)


def changed_doc_ids(previous: Manifest, current: Manifest) -> List[str]:
    prev_hashes = {doc.doc_id: doc.sha256 for doc in previous.docs}
    changed: List[str] = []
    for doc in current.docs:
        if prev_hashes.get(doc.doc_id) != doc.sha256:
            changed.append(doc.doc_id)
    return changed


def docs_for_module(manifest: Manifest, module: str) -> List[ManifestDocument]:
    return [doc for doc in manifest.docs if module in doc.module_tags]


def staged_bundle_name(manifest: Manifest) -> str:
    hash_material = "_".join(sorted(doc.sha256 for doc in manifest.docs))
    return f"bundle_{safe_slug(hash_material[:24])}.json"


def split_priority_docs(manifest: Manifest) -> Tuple[List[ManifestDocument], List[ManifestDocument]]:
    normative = [doc for doc in manifest.docs if doc.normative]
    supporting = [doc for doc in manifest.docs if not doc.normative]
    return normative, supporting


def _extract_bafa_pdf_links(page_url: str) -> List[str]:
    try:
        request = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0 (BAFA-Agent-Bot/1.0)"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw_html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    html = html_lib.unescape(raw_html)
    hrefs = re.findall(r'href="([^"]+?\.pdf[^"]*)"', html, flags=re.IGNORECASE)
    absolute = [urljoin(page_url, href.strip()) for href in hrefs]
    # Deduplicate while preserving order.
    seen = set()
    ordered: List[str] = []
    for item in absolute:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _pick_bafa_link(
    links: List[str],
    preferred_tokens: List[str],
    fallback_path: str,
    source_url: str,
) -> str:
    lowered = [(link, link.lower()) for link in links]
    for token in preferred_tokens:
        for link, link_lower in lowered:
            if token in link_lower:
                return link
    return urljoin(source_url, fallback_path)
