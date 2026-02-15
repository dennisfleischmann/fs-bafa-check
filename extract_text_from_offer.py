#!/usr/bin/env python3
"""
Robust offer-PDF text extraction (incl. scanned PDFs) using OpenAI vision OCR.
Auto-loads OPENAI_API_KEY from a local .env file (no shell tricks needed).

Usage:
  ./extract_offer_text_ocr.py ./offer.pdf --out ./angebot.txt

Dependencies:
  pip install openai pymupdf python-dotenv

Environment (.env supported):
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o   # optional
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, List

# -------------------- Auto-load .env --------------------
# It will look for a .env file in:
# 1) current working directory
# 2) the directory of this script
# 3) parents of script dir (via find_dotenv)
def load_env() -> None:
    try:
        from dotenv import load_dotenv, find_dotenv  # pip install python-dotenv
    except Exception:
        # Not installed; keep going (user may rely on real env vars)
        return

    # Load .env near the CWD if present
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)

    # Also try to find a .env relative to script location / parents
    try:
        script_dir = Path(__file__).resolve().parent
        dotenv_path = find_dotenv(filename=".env", usecwd=False)
        # find_dotenv may return "" if none found
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        else:
            # Try script_dir/.env
            load_dotenv(dotenv_path=script_dir / ".env", override=False)
    except Exception:
        pass


load_env()

# -------------------- Prompts (STRICT) --------------------

SYSTEM_OCR = (
    "You are an OCR transcription engine. "
    "You never guess or invent text. "
    "If unsure, output [ILLEGIBLE]. "
    "You output plain text only."
)

DEFAULT_OCR_PROMPT = """Transcribe this page VERBATIM.

Rules:
- Output PLAIN TEXT only. No markdown, no JSON, no commentary.
- Do NOT guess or “fix” text. If a word/number is unclear, write [ILLEGIBLE].
- Preserve line breaks as they appear.
- Preserve all numbers, units, punctuation, and capitalization exactly.
- For tables: keep row order and separate columns with TAB characters.
- Do not add any text that is not present on the page.
- Start with exactly: ===== PAGE {page_no} =====
"""

# -------------------- Helpers --------------------


def _fail(msg: str, code: int = 1) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def _extract_output_text(response: Any) -> str:
    """Extract text from OpenAI Responses API payload."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    payload = None
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    elif isinstance(response, dict):
        payload = response

    if not isinstance(payload, dict):
        return ""

    parts: List[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                if content.get("type") == "output_text" and content.get("text"):
                    parts.append(str(content["text"]))
                text_obj = content.get("text")
                if isinstance(text_obj, dict) and text_obj.get("value"):
                    parts.append(str(text_obj["value"]))
                elif isinstance(text_obj, str):
                    parts.append(text_obj)

    return "\n".join(p for p in parts if p).strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract plain text from offer PDFs (incl. scans) using strict OCR (auto-loads .env)."
    )
    p.add_argument("pdf", help="Path to input PDF")
    p.add_argument("--out", required=True, help="Path to output .txt file")
    p.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4o"),
        help="OpenAI model (default: OPENAI_MODEL or gpt-4o)",
    )
    p.add_argument("--dpi", type=int, default=300, help="Render DPI for OCR pages (default: 300)")
    p.add_argument(
        "--min-local-chars",
        type=int,
        default=40,
        help="If local extracted text on a page is below this char count, OCR that page (default: 40)",
    )
    p.add_argument("--force-ocr", action="store_true", help="OCR every page (ignore local text)")
    p.add_argument("--max-pages", type=int, default=0, help="Limit pages processed (0 = all)")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between OCR calls (default: 0)")
    p.add_argument("--retries", type=int, default=3, help="Retries on API errors (default: 3)")
    p.add_argument(
        "--debug-env",
        action="store_true",
        help="Print where .env was loaded from and whether OPENAI_API_KEY is present (does NOT print the key).",
    )
    return p.parse_args()


def render_page_png_bytes(pdf_path: Path, page_index: int, dpi: int) -> bytes:
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError("Missing dependency: pymupdf. Install with: pip install pymupdf") from e

    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_index)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def extract_local_page_text(pdf_path: Path, page_index: int) -> str:
    """Extract embedded text (if any) from a PDF page using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError("Missing dependency: pymupdf. Install with: pip install pymupdf") from e

    doc = fitz.open(str(pdf_path))
    try:
        page = doc.load_page(page_index)
        txt = page.get_text("text") or ""
        return txt.replace("\r\n", "\n").replace("\r", "\n").strip()
    finally:
        doc.close()


def ocr_page_with_openai(image_png: bytes, page_no_1based: int, model: str, retries: int = 3) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set (even after loading .env)")

    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("Missing dependency: openai. Install with: pip install openai") from e

    client = OpenAI()

    b64 = base64.b64encode(image_png).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"
    prompt = DEFAULT_OCR_PROMPT.format(page_no=page_no_1based)

    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.responses.create(
                model=model,
                temperature=0,
                max_output_tokens=8000,
                input=[
                    {"role": "system", "content": SYSTEM_OCR},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    },
                ],
            )
            text = _extract_output_text(resp)
            return text.strip()
        except Exception as e:
            last_err = e
            time.sleep(0.8 * attempt)

    raise RuntimeError(f"OCR failed after {retries} attempts: {last_err}")


def main() -> int:
    args = parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists() or not pdf_path.is_file():
        return _fail(f"input file not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        return _fail(f"input must be a .pdf file: {pdf_path}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.debug_env:
        # We don't print the key; only presence.
        has_key = bool(os.getenv("OPENAI_API_KEY"))
        print(f"debug: cwd={Path.cwd()}", file=sys.stderr)
        print(f"debug: script_dir={Path(__file__).resolve().parent}", file=sys.stderr)
        print(f"debug: OPENAI_API_KEY present={has_key}", file=sys.stderr)
        print(f"debug: OPENAI_MODEL={os.getenv('OPENAI_MODEL', '(not set)')}", file=sys.stderr)

    # Open once to get page count
    try:
        import fitz  # PyMuPDF
    except Exception:
        return _fail("python package 'pymupdf' is not installed. Run: pip install pymupdf")

    doc = fitz.open(str(pdf_path))
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    max_pages = args.max_pages if args.max_pages and args.max_pages > 0 else total_pages
    max_pages = min(max_pages, total_pages)

    output_chunks: List[str] = []
    for i in range(max_pages):
        page_no = i + 1

        local_text = ""
        if not args.force_ocr:
            try:
                local_text = extract_local_page_text(pdf_path, i)
            except Exception:
                local_text = ""

        needs_ocr = args.force_ocr or (len(local_text) < args.min_local_chars)

        if not needs_ocr:
            output_chunks.append(f"===== PAGE {page_no} =====\n{local_text}\n")
            continue

        try:
            png_bytes = render_page_png_bytes(pdf_path, i, args.dpi)
            ocr_text = ocr_page_with_openai(
                image_png=png_bytes,
                page_no_1based=page_no,
                model=args.model,
                retries=args.retries,
            )
            output_chunks.append(ocr_text.rstrip() + "\n")
        except Exception as e:
            output_chunks.append(f"===== PAGE {page_no} =====\n[OCR_FAILED]\n")
            print(f"warn: OCR failed on page {page_no}: {e}", file=sys.stderr)

        if args.sleep > 0:
            time.sleep(args.sleep)

    final_text = "\n".join(chunk.strip("\n") for chunk in output_chunks).strip() + "\n"
    out_path.write_text(final_text, encoding="utf-8")
    print(f"saved extracted text to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
