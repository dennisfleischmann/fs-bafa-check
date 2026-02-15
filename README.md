# BAFA Agent (Python)

Deterministic BAFA/BEG evaluation scaffold implemented from `developer_spec.md`.

## Shared config

The project loads configuration from:

1. `config.env` (tracked defaults)
2. `.env` (optional local override, ignored by git)

Important keys:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
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
- Evidence-binding, conflict, coverage, activation guards.
- Secretary memo + customer email generation.
- Audit persistence, escalation scoring, model routing, bundle diffing, regression runner.

## CLI

```bash
python3 -m bafa_agent --base-dir . init
python3 -m bafa_agent --base-dir . compile
python3 -m bafa_agent --base-dir . compile --source bafa
python3 -m bafa_agent --base-dir . evaluate --offer samples/offer_example.txt
python3 -m bafa_agent --base-dir . memo --evaluation data/cases/<case_id>/evaluation.json
python3 -m bafa_agent --base-dir . email --evaluation data/cases/<case_id>/evaluation.json --index 0
```

To override locally without editing tracked defaults:

```bash
cat > .env <<'EOF'
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
BAFA_SOURCE_MODE=bafa
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
