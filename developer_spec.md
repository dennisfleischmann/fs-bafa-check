# Developer Spec - BAFA/BEG Agent

Source baseline: `conversion.txt` and the task inventory in `tasts.txt`.
Goal: give a developer implementation-ready specs for every task.

## Global constraints (apply to all tasks)

- Decision model is deterministic: LLM extracts facts, code decides eligibility.
- No-guess policy: missing must-fields never produce PASS/FAIL, only CLARIFY/ABORT.
- Every critical value must be evidence-bound (document/page/quote, optional bbox).
- Rules are modular files in source control; runtime can use a compiled bundle.

---

## T01 - Decision principle (PASS only with explicit must-criteria)

- Objective: enforce strict decision semantics.
- Implementation:
  - Define statuses: `PASS`, `FAIL`, `CLARIFY`, `ABORT`.
  - In evaluator, only allow `PASS` if all `required_fields` exist and all `conditions` are true.
  - Missing must-field routes to `CLARIFY` or `ABORT` via severity policy.
- Deliverable: decision policy module and unit tests.
- Acceptance criteria:
  - Any missing must-field cannot return `PASS`.
  - Any unresolved ambiguity cannot return `PASS`.
- Source anchors: `conversion.txt:141`, `conversion.txt:145`, `conversion.txt:226`, `conversion.txt:876`.

## T02 - No-Guess policy

- Objective: prevent hallucinated assumptions.
- Implementation:
  - Disable inferred values for U-values, material classes, component type.
  - Mark non-explicit values as `unknown`.
  - Emit clarification prompts instead of implicit fill-in.
- Deliverable: no-guess validator in extraction/evaluation pipeline.
- Acceptance criteria:
  - Missing U-value yields `CLARIFY`, never substituted.
  - Incomplete core facts trigger clarification checklist.
- Source anchors: `conversion.txt:233`, `conversion.txt:364`, `conversion.txt:367`, `conversion.txt:1808`.

## T03 - 3-layer architecture

- Objective: separate legal source, machine rules, and runtime decision logic.
- Implementation:
  - Layer A `Source`: immutable PDFs + text extracts.
  - Layer B `Knowledge`: normalized JSON rules/tables.
  - Layer C `Decision`: deterministic evaluator and runtime prompts.
- Deliverable: architecture diagram + module boundaries in repo.
- Acceptance criteria:
  - No runtime decision reads raw PDFs directly.
  - All decisions trace back to normalized rules and evidence.
- Source anchors: `conversion.txt:150`, `conversion.txt:151`, `conversion.txt:187`, `conversion.txt:221`.

## T04 - Fix document sources for envelope module

- Objective: define included/excluded source documents for Gebaeudehuelle scope.
- Implementation:
  - Build document registry with module tags (`envelope`, `heating`, `bonus`).
  - Include normative and operational docs; exclude module-foreign docs by default.
- Deliverable: `rules/source_registry.json`.
- Acceptance criteria:
  - Registry explicitly marks normative vs supporting docs.
  - Envelope run ignores unrelated docs unless module flag enables them.
- Source anchors: `conversion.txt:156`, `conversion.txt:655`, `conversion.txt:1410`, `conversion.txt:1420`.

## T05 - Source priority model

- Objective: deterministic conflict resolution between documents.
- Implementation:
  - Define numeric priority (`richtlinie/tma=100`, `infoblatt=80`, `merkblatt=60`).
  - During compile, conflicting rules keep highest-priority source and retain loser as guidance note.
- Deliverable: priority resolver and conflict log output.
- Acceptance criteria:
  - Same rule conflict always resolves to highest priority.
  - Conflict entries are persisted for review.
- Source anchors: `conversion.txt:673`, `conversion.txt:676`, `conversion.txt:1475`, `conversion.txt:2050`.

## T06 - Daily update job for BAFA docs

- Objective: automate source refresh without unstable live switching.
- Implementation:
  - Daily scheduler downloads source docs and stages a new build.
  - Build artifacts are activated only after guard checks pass.
- Deliverable: cron/scheduler job + build pipeline script.
- Acceptance criteria:
  - Job runs daily and produces a build report.
  - Failed guards block activation of new rules.
- Source anchors: `conversion.txt:135`, `conversion.txt:736`, `conversion.txt:2197`, `conversion.txt:2214`.

## T07 - Persist document metadata

- Objective: full traceability for every ingested document.
- Implementation:
  - Metadata fields: `doc_id`, `source_url`, `download_date`, `version_hint`, `valid_from`, `sha256`.
  - Persist in `manifest.json`.
- Deliverable: metadata schema + writer.
- Acceptance criteria:
  - Every active doc has full metadata.
  - Decision output can reference document version/hash.
- Source anchors: `conversion.txt:166`, `conversion.txt:741`, `conversion.txt:745`, `conversion.txt:2091`.

## T08 - Hash-based change detection

- Objective: skip expensive re-extraction when content is unchanged.
- Implementation:
  - Compute SHA-256 per downloaded file.
  - Re-extract only if hash changes.
- Deliverable: hash cache and incremental extractor.
- Acceptance criteria:
  - Unchanged docs are skipped.
  - Changed docs trigger extraction + compile.
- Source anchors: `conversion.txt:743`, `conversion.txt:747`, `conversion.txt:1914`, `conversion.txt:1918`.

## T09 - Rules directory structure

- Objective: establish modular, versionable storage for rules.
- Implementation:
  - Create structure:
    - `rules/manifest.json`
    - `rules/tables/*.json`
    - `rules/measures/*.json`
    - `rules/taxonomy/*.json`
    - `rules/evidence_store/...`
    - `rules/bundles/ruleset.bundle.json`
- Deliverable: repository scaffold + readme.
- Acceptance criteria:
  - All generated artifacts map to one of these folders.
  - Runtime can load bundle without loading full evidence store.
- Source anchors: `conversion.txt:2089`, `conversion.txt:2095`, `conversion.txt:2113`, `conversion.txt:2153`.

## T10 - Layout extraction (text + coordinates)

- Objective: get structured text with positional evidence.
- Implementation:
  - Extract line objects with `page`, `x0`, `y0`, `x1`, `y1`, `text`.
  - Compute `text_coverage_ratio` for quality gating.
- Deliverable: layout extractor output JSONL.
- Acceptance criteria:
  - Each extracted value can be traced to page coordinates.
  - Low coverage triggers OCR fallback path.
- Source anchors: `conversion.txt:751`, `conversion.txt:754`, `conversion.txt:758`, `conversion.txt:1920`.

## T11 - Table extraction for TMA thresholds

- Objective: make threshold extraction table-first and deterministic.
- Implementation:
  - Detect table regions and extract grid cells.
  - Convert table rows to structured threshold records.
  - Keep original string representations for evidence.
- Deliverable: table parser + row normalizer.
- Acceptance criteria:
  - Umax/Uw thresholds are sourced from table rows, not free text paraphrase.
  - Failed table parsing emits targeted fallback action.
- Source anchors: `conversion.txt:762`, `conversion.txt:767`, `conversion.txt:775`, `conversion.txt:1932`.

## T12 - OCR fallback path

- Objective: handle scanned or extraction-broken pages.
- Implementation:
  - Run OCR only when layout/table extraction quality is insufficient.
  - OCR output must include bounding boxes.
- Deliverable: OCR fallback service + quality gate thresholds.
- Acceptance criteria:
  - OCR not run for clean born-digital pages.
  - OCR evidence supports page/quote/bbox references.
- Source anchors: `conversion.txt:760`, `conversion.txt:777`, `conversion.txt:784`, `conversion.txt:1930`.

## T13 - Value normalization (numbers, units, synonyms)

- Objective: canonicalize extracted facts before rule evaluation.
- Implementation:
  - Normalize decimal comma to decimal point.
  - Canonicalize units (`W/m2K` variants -> `W/(m2K)`).
  - Add plausibility checks (thickness/U-value ranges).
- Deliverable: normalization module and validation errors.
- Acceptance criteria:
  - Equivalent unit spellings map to one canonical unit.
  - Out-of-range values are flagged for clarification.
- Source anchors: `conversion.txt:771`, `conversion.txt:1006`, `conversion.txt:1010`, `conversion.txt:505`.

## T14 - Controlled vocabulary and taxonomy

- Objective: ensure stable mapping from noisy offer language to canonical entities.
- Implementation:
  - Build taxonomy for `component_type`, `measure_type`, `cost_category`, synonyms.
  - Include disambiguation rules (`OGD` vs `Dach`, `Uw` vs `Ug`).
- Deliverable: `rules/taxonomy/components.json`, `rules/taxonomy/cost_categories.json`.
- Acceptance criteria:
  - Known synonym phrases map deterministically to canonical keys.
  - Ambiguous mappings return clarification, not forced mapping.
- Source anchors: `conversion.txt:343`, `conversion.txt:520`, `conversion.txt:1526`, `conversion.txt:1982`.

## T15 - Requirement snippet detection

- Objective: detect candidate requirement statements from text/tables.
- Implementation:
  - Pattern detectors for obligation terms, operators, threshold patterns, exclusion phrases.
  - Tag snippet type: `table_row`, `paragraph`, `bullet`.
- Deliverable: snippet detector output with evidence refs.
- Acceptance criteria:
  - Candidate snippets include `doc_id/page/quote`.
  - Threshold snippets from tables are correctly flagged.
- Source anchors: `conversion.txt:1491`, `conversion.txt:1494`, `conversion.txt:1498`, `conversion.txt:1950`.

## T16 - Define and populate `requirements.jsonl`

- Objective: create atomic requirement records as compile input.
- Implementation:
  - Schema fields: `req_id`, `req_type`, `scope`, `rule`, `evidence`, `priority`, optional `severity_if_missing`.
  - Write one JSON object per requirement line.
- Deliverable: `rules/requirements.jsonl` + schema.
- Acceptance criteria:
  - All compile-time rules originate from atomic requirement records.
  - Records validate against schema.
- Source anchors: `conversion.txt:1905`, `conversion.txt:1990`, `conversion.txt:1995`, `conversion.txt:2005`.

## T17 - Evidence-bound rule storage

- Objective: ensure every decision-relevant field is traceable.
- Implementation:
  - Attach evidence object to each extracted fact/rule (`doc_id`, `page`, `quote`, optional `bbox`).
  - Treat missing evidence as missing field.
- Deliverable: evidence binding utility + evidence schema.
- Acceptance criteria:
  - Numeric thresholds without evidence are rejected.
  - `evaluation.json` can show "where it came from".
- Source anchors: `conversion.txt:371`, `conversion.txt:372`, `conversion.txt:727`, `conversion.txt:841`.

## T18 - Rule compiler (`requirements -> MeasureSpec`)

- Objective: compile atomic records into measure-level executable specs.
- Implementation:
  - Group records by `measure_id`.
  - Build sections: `required_fields`, `eligibility`, `technical_requirements`, `documentation`, `cost_rules`.
- Deliverable: compiler script producing `rules/measures/*.json`.
- Acceptance criteria:
  - Each active measure has one compiled MeasureSpec.
  - Compiler output is deterministic given same inputs.
- Source anchors: `conversion.txt:1543`, `conversion.txt:1546`, `conversion.txt:2023`, `conversion.txt:2034`.

## T19 - Guard: threshold must exist in evidence text

- Objective: reject fabricated or paraphrased threshold values.
- Implementation:
  - Programmatic check that numeric threshold token appears in associated quote/table text.
  - Fail rule compile when evidence token mismatch occurs.
- Deliverable: evidence token guard.
- Acceptance criteria:
  - Rule with missing threshold token is marked invalid.
  - Build status reflects invalid rules count.
- Source anchors: `conversion.txt:729`, `conversion.txt:809`, `conversion.txt:1557`, `conversion.txt:2041`.

## T20 - Coverage checks

- Objective: prevent partial/incomplete rulesets from going live.
- Implementation:
  - Define minimum measure set for envelope module:
    - wall, roof/OGD, floor/ceiling, windows/doors, special cases.
  - Validate module coverage before bundle activation.
- Deliverable: coverage validator with module config.
- Acceptance criteria:
  - Missing mandatory measure category blocks release.
  - Coverage report lists missing components.
- Source anchors: `conversion.txt:815`, `conversion.txt:1561`, `conversion.txt:2055`, `conversion.txt:2061`.

## T21 - Conflict guard (source contradiction handling)

- Objective: deterministic contradiction resolution.
- Implementation:
  - During compile, detect same-scope conflicting rules.
  - Keep highest-priority rule; downgrade others to guidance/audit note.
- Deliverable: conflict resolver + conflict journal.
- Acceptance criteria:
  - Contradictory rules do not coexist in active rule set.
  - Audit log retains discarded alternatives.
- Source anchors: `conversion.txt:1559`, `conversion.txt:2050`, `conversion.txt:2053`.

## T22 - Activation guard

- Objective: activate rules only after full validation.
- Implementation:
  - Build state machine: `staged -> validated -> active`.
  - Block activation on failed guards (evidence, coverage, conflicts).
- Deliverable: release gate in rules update pipeline.
- Acceptance criteria:
  - Failed validation never overwrites active bundle.
  - Last known-good bundle remains active.
- Source anchors: `conversion.txt:825`, `conversion.txt:827`, `conversion.txt:2212`, `conversion.txt:2214`.

## T23 - Offer intake pipeline (case id, document type, quality flag)

- Objective: standardize incoming offer handling.
- Implementation:
  - Generate `case_id`.
  - Detect document class (text PDF, scan PDF, DOCX, email text).
  - Set extraction quality flags (e.g., low table readability).
- Deliverable: intake/preflight service.
- Acceptance criteria:
  - Every run has a stable case id.
  - Preflight output chooses correct extraction path.
- Source anchors: `conversion.txt:2216`, `conversion.txt:2223`, `conversion.txt:2225`, `conversion.txt:2231`.

## T24 - Parse offers into measure objects

- Objective: convert unstructured offer content into canonical measure list.
- Implementation:
  - Detect and split positions by component/measure.
  - Map to taxonomy (`WDVS/Fassade -> Aussenwand`, separate `Dach` vs `OGD`).
  - Cluster line items into cost categories.
- Deliverable: measure parser producing canonical measure objects.
- Acceptance criteria:
  - Parsed measures include component, values, and associated line items.
  - Ambiguous mapping yields clarify marker.
- Source anchors: `conversion.txt:2233`, `conversion.txt:2248`, `conversion.txt:2250`, `conversion.txt:2252`.

## T25 - Strict `offer_facts.json` schema

- Objective: force extraction output into validated structure.
- Implementation:
  - Define JSON Schema for `offer_facts`.
  - Use structured output/function calling from model endpoint.
  - Validate and reject non-conforming output.
- Deliverable: `schemas/offer_facts.schema.json` + validator.
- Acceptance criteria:
  - Invalid extraction JSON fails fast.
  - Missing evidence for required fields triggers clarify/abort.
- Source anchors: `conversion.txt:326`, `conversion.txt:345`, `conversion.txt:2254`, `conversion.txt:2267`.

## T26 - Dual input logic (direct U vs layers)

- Objective: support both explicit U-values and layer-based inputs.
- Implementation:
  - `input_mode` values: `direct_u`, `layers`.
  - If `direct_u`, use explicit target U-value.
  - If `layers`, compute derived U with deterministic formulas.
- Deliverable: derived-value engine with mode switching.
- Acceptance criteria:
  - Both modes produce normalized `derived.*` fields.
  - Missing mandatory inputs in each mode produce clarify/abort.
- Source anchors: `conversion.txt:1049`, `conversion.txt:1059`, `conversion.txt:1760`, `conversion.txt:2261`.

## T27 - Roof logic (bandwidth and sparren handling)

- Objective: implement robust roof evaluation with uncertain wood fraction.
- Implementation:
  - Homogeneous layers: compute `U = 1 / (Rsi + sum(d/lambda) + Rse)`.
  - Zwischensparren case: evaluate using wood fraction `f`.
  - If `f` unknown, evaluate at `f=0.07, 0.10, 0.15`:
    - pass if all conservative cases meet threshold,
    - fail if all fail,
    - else clarify.
- Deliverable: roof calculator + clarify question generator.
- Acceptance criteria:
  - Output includes method + input evidence.
  - Unknown sparren info does not cause guessed pass/fail.
- Source anchors: `conversion.txt:1100`, `conversion.txt:1137`, `conversion.txt:1271`, `conversion.txt:2280`.

## T28 - Wall logic (worst-case when existing buildup unknown)

- Objective: make wall decisions safe when only new insulation data exists.
- Implementation:
  - If target U exists, evaluate directly.
  - If only new layers and unknown existing wall, compute worst-case with existing resistance set to 0.
  - Use worst-case result for guaranteed pass; otherwise clarify.
- Deliverable: wall evaluator + minimum-thickness suggestion mode (marked non-final).
- Acceptance criteria:
  - Worst-case pass is accepted as guaranteed pass.
  - Non-guaranteed case requests missing existing wall info.
- Source anchors: `conversion.txt:1285`, `conversion.txt:1292`, `conversion.txt:1349`, `conversion.txt:2290`.

## T29 - Rule evaluation engine (`PASS/FAIL/CLARIFY`)

- Objective: deterministic per-measure rule execution.
- Implementation:
  - For each measure, load matching MeasureSpec.
  - Evaluate `required_fields`, `eligibility`, thresholds, exclusions.
  - Emit one final status per measure with reasons and questions.
- Deliverable: evaluation engine module.
- Acceptance criteria:
  - Engine output is reproducible for same inputs.
  - Exclusions and missing required fields are reflected in status.
- Source anchors: `conversion.txt:2301`, `conversion.txt:2305`, `conversion.txt:2311`, `conversion.txt:2321`.

## T30 - Separate cost eligibility logic

- Objective: evaluate technical eligibility and cost eligibility independently.
- Implementation:
  - Implement cost classification:
    - `ELIGIBLE`
    - `INELIGIBLE`
    - `ELIGIBLE_IF_NECESSARY` / partial.
  - Aggregate eligible cost total and problematic line items.
- Deliverable: cost rules evaluator.
- Acceptance criteria:
  - Cost outputs include totals and itemized reasons.
  - Technical pass does not imply full cost eligibility.
- Source anchors: `conversion.txt:1451`, `conversion.txt:1686`, `conversion.txt:2323`, `conversion.txt:2334`.

## T31 - Produce `evaluation.json`

- Objective: standardized machine-readable decision output.
- Implementation:
  - Schema fields: `case_id`, `results[]`, `status`, `reason`, `used_evidence`, `questions`, optional customer summary.
  - Include per-measure outputs and references to used rules.
- Deliverable: `schemas/evaluation.schema.json` + output writer.
- Acceptance criteria:
  - JSON validates against schema.
  - Each result has status and reason; clarify includes questions.
- Source anchors: `conversion.txt:1598`, `conversion.txt:1785`, `conversion.txt:2298`, `conversion.txt:2315`.

## T32 - Secretary output spec (internal memo)

- Objective: actionable internal output for office workflow.
- Implementation:
  - Build memo sections per case:
    - traffic-light per measure (`PASS/FAIL/CLARIFY`),
    - missing docs checklist,
    - ready-to-send clarification snippets.
- Deliverable: memo renderer template.
- Acceptance criteria:
  - Memo can be generated from `evaluation.json` without manual editing.
  - Clarify tasks are explicit and specific.
- Source anchors: `conversion.txt:257`, `conversion.txt:260`, `conversion.txt:2336`, `conversion.txt:2343`.

## T33 - Customer email templates

- Objective: generate safe external communication.
- Implementation:
  - Template variants for PASS, FAIL, CLARIFY.
  - Include limitation/disclaimer statement and requested follow-up docs.
  - Never state certainty when status is `CLARIFY`.
- Deliverable: customer mail template library.
- Acceptance criteria:
  - Every mail contains scope disclaimer for pre-check.
  - Clarify mail always includes concrete requested inputs.
- Source anchors: `conversion.txt:609`, `conversion.txt:611`, `conversion.txt:2345`, `conversion.txt:2349`.

## T34 - Logging and audit chain

- Objective: full end-to-end traceability for each case.
- Implementation:
  - Persist chain:
    - raw offer refs
    - `offer_facts`
    - `derived`
    - `evaluation`
    - evidence links
  - Keep immutable case snapshots.
- Deliverable: audit store and retrieval endpoint/tooling.
- Acceptance criteria:
  - Any final status can be traced to exact evidence and rule.
  - Audit entries are queryable by case id.
- Source anchors: `conversion.txt:281`, `conversion.txt:845`, `conversion.txt:2353`, `conversion.txt:2354`.

## T35 - Escalation rules

- Objective: route high-risk cases to human review.
- Implementation:
  - Define escalation triggers:
    - high-impact CLARIFY
    - contradictions in extracted facts
    - low OCR/extraction confidence
    - risk score above threshold
  - Generate escalation ticket payload.
- Deliverable: escalation policy + queue integration.
- Acceptance criteria:
  - Triggered cases are not auto-closed.
  - Escalation payload includes reason and missing evidence.
- Source anchors: `conversion.txt:394`, `conversion.txt:401`, `conversion.txt:2356`, `conversion.txt:2362`.

## T36 - Model routing (default + escalation model)

- Objective: optimize cost/quality with a model cascade.
- Implementation:
  - Default model for extraction/triage/text generation.
  - Escalation model for contradictory or ambiguous complex cases.
  - Structured output with JSON schema at extraction boundary.
  - For scan docs, run OCR before strict JSON generation.
- Deliverable: routing policy config and orchestration logic.
- Acceptance criteria:
  - Normal cases stay on default model.
  - Escalation cases are routed deterministically by trigger rules.
- Source anchors: `conversion.txt:1831`, `conversion.txt:1835`, `conversion.txt:1846`, `conversion.txt:1867`.

## T37 - Regression test corpus

- Objective: catch drift from source updates and parser changes.
- Implementation:
  - Build canonical test cases for `eligible`, `not_eligible`, `clarify`.
  - Run regression after every rules rebuild and pipeline change.
  - Track rule hit rates and failure reasons.
- Deliverable: test corpus + automated regression job.
- Acceptance criteria:
  - Daily runs report pass/fail deltas.
  - Significant result drift blocks release.
- Source anchors: `conversion.txt:873`, `conversion.txt:935`, `conversion.txt:621`, `conversion.txt:1713`.

## T38 - Daily diff alarm + human review gate

- Objective: control risk when source documents change.
- Implementation:
  - Compare previous and current compiled rules:
    - changed thresholds,
    - added/removed rules.
  - Require human approval for material diffs before activation.
- Deliverable: diff report generator + approval gate.
- Acceptance criteria:
  - Changed thresholds are explicitly listed in report.
  - Unapproved material changes cannot become active.
- Source anchors: `conversion.txt:821`, `conversion.txt:823`, `conversion.txt:2063`, `conversion.txt:2066`.

## T39 - Data protection and access concept

- Objective: protect customer data and minimize exposure.
- Implementation:
  - PII redaction before LLM processing where possible.
  - Store minimal necessary artifacts (facts, hash, evidence snippets).
  - Define role-based access for offers, evidence, outputs.
  - Document hosting/region policy (EU/on-prem decisions).
- Deliverable: privacy architecture doc + data retention policy.
- Acceptance criteria:
  - Sensitive fields are redacted/masked in model prompts.
  - Access logs exist for data reads and exports.
- Source anchors: `conversion.txt:627`, `conversion.txt:633`, `conversion.txt:637`.

---

## Suggested implementation order

- Phase 1: T01-T09 (policy, architecture, sources, file layout).
- Phase 2: T10-T22 (extraction, normalization, requirements, compiler, guards).
- Phase 3: T23-T31 (offer runtime flow, evaluation, outputs).
- Phase 4: T32-T39 (communications, audit, routing, tests, governance).

