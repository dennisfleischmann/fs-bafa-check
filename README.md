# BAFA Agent (Python)

Deterministic BAFA/BEG evaluation scaffold implemented from `developer_spec.md`.

## Shared config

The project loads configuration from:

1. `config.env` (tracked defaults)
2. `.env` (optional local override, ignored by git)

Important keys:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `BAFA_SEMANTIC_USE_EMBEDDINGS` (default: `false`)
- `BAFA_SEMANTIC_MIN_CONFIDENCE` (default: `0.58`)
- `BAFA_EMBEDDING_MODEL` (default: `text-embedding-3-small`)
- `OPENAI_PLAUSIBILITY_MODEL` (default: `gpt-5.2`)
- `BAFA_BASE_DIR`
- `BAFA_SOURCE_MODE`
- `BAFA_SOURCE_URL`

## What is implemented

- Layered architecture: source -> normalized rules -> deterministic decision engine.
- Rule artifacts: `rules/manifest.json`, `rules/measures/*.json`, `rules/tables/*.json`, `rules/taxonomy/*.json`, `rules/bundles/*.json`.
- Intake + offer parsing to strict `offer_facts` shape.
- Derived calculations (direct U, layer-based U, roof bandwidth helper, wall worst-case helper).
- Deterministic measure evaluation with statuses: `PASS`, `FAIL`, `CLARIFY`, `ABORT`.
- Cost evaluation separated from technical checks.
- Hybrid semantic line-item mapping (lexical by default, optional embedding rerank) before deterministic rules.
- Evidence-binding, conflict, coverage, activation guards.
- Secretary memo + customer email generation.
- Audit persistence, escalation scoring, model routing, bundle diffing, regression runner.

## CLI

```bash
python3 -m bafa_agent --base-dir . init
python3 -m bafa_agent --base-dir . compile
python3 -m bafa_agent --base-dir . compile --source bafa
python3 -m bafa_agent --base-dir . evaluate --offer samples/offer_example.txt
./execute_plausibility_check.py --base-dir . --offer ./offer.txt
./execute-plausibility-check --base-dir . --offer ./offer.txt
python3 -m bafa_agent --base-dir . memo --evaluation data/cases/<case_id>/evaluation.json
python3 -m bafa_agent --base-dir . email --evaluation data/cases/<case_id>/evaluation.json --index 0
```

## Web app (simple migration wrapper)

This repository now includes a minimal Flask app that keeps the CLI logic and wraps it in a browser flow:

1. Upload offer PDF
2. Extract text with `pdfplumber` to `./offer.txt`
3. Run `python3 -m bafa_agent compile --source bafa`
4. Run `python3 -m bafa_agent evaluate --offer ./offer.txt`
5. Show JSON result and a human-readable memo
6. Persist offer + evaluation in SQLite and support listing/editing saved evaluations

If the PDF has no embedded text, the app falls back to `extract_text_from_offer.py` OCR automatically.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python3 webapp/app.py
```

Open `http://127.0.0.1:8000`.

Persistence details:

- Default DB path: `data/webapp_evaluations.db`
- Override DB path with environment variable: `EVALUATIONS_DB_PATH`
- List evaluations: `GET /evaluations`
- Edit evaluation: `GET/POST /evaluations/<id>`

## Deploy on Render

This repository includes a `render.yaml` blueprint for a Render Web Service.

1. Push this repo to GitHub.
2. In Render: **New** -> **Blueprint** -> select the repository.
3. Render will read `render.yaml` and create service `ai-bafa-check`.
4. Set `OPENAI_API_KEY` in Render environment variables.
5. Deploy.

To persist evaluations on Render across restarts, use a persistent disk and point:

```bash
EVALUATIONS_DB_PATH=/var/data/webapp_evaluations.db
```

Start command used in production:

```bash
gunicorn webapp.app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300
```

Note: Render free services use an ephemeral filesystem. Uploaded PDFs and generated outputs are not persistent across restarts.

To override locally without editing tracked defaults:

```bash
cat > .env <<'EOF'
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
BAFA_SOURCE_MODE=bafa
BAFA_SEMANTIC_USE_EMBEDDINGS=false
OPENAI_PLAUSIBILITY_MODEL=gpt-5.2
EOF
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Notes

- This implementation is deterministic by design and keeps LLM concerns outside decision logic.
- Source registry defaults to local `conversion.txt` so the pipeline runs immediately in this workspace.
- Use `compile --source bafa` to build a BAFA URL-based source registry and download referenced PDFs.
