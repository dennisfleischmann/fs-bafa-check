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

## Web App Backend (Render-ready)

This repository now includes a queue-based backend for your employee web app:

- `webapp/api.py` (FastAPI web service)
- `webapp/worker.py` (RQ worker)
- `webapp/worker_tasks.py` (compile/extract/evaluate jobs)
- `render.yaml` (Render Blueprint: web + worker + cron + postgres + redis)

### Local run

```bash
pip install -r requirements.txt
uvicorn webapp.api:app --reload --port 8000
python -m webapp.worker
```

### API flow

1) Create BAFA application:
```bash
curl -X POST http://localhost:8000/applications -H "Content-Type: application/json" -d '{"title":"Antrag #1"}'
```

2) Upload offer (`.pdf` or `.txt`) and enqueue extraction:
```bash
curl -X POST http://localhost:8000/applications/<application_id>/offers -F "file=@angebot.pdf"
```

3) Start evaluation + plausibility check:
```bash
curl -X POST http://localhost:8000/applications/<application_id>/offers/<offer_id>/evaluate
```

4) Poll job status:
```bash
curl http://localhost:8000/jobs/<job_id>
```

5) Trigger compile latest BAFA docs:
```bash
curl -X POST http://localhost:8000/actions/compile-latest
```

### Render deploy

- Commit and push repo.
- Create Blueprint from `render.yaml`.
- Set `OPENAI_API_KEY` in web/worker/cron services.
- Ensure worker is running (jobs are asynchronous).

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
