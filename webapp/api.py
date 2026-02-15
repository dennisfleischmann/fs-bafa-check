from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from .db import Base, ENGINE, get_session
from .models import Application, Evaluation, JobRecord, Offer
from .queueing import get_queue
from .schemas import (
    ApplicationCreate,
    ApplicationResponse,
    EvaluationResponse,
    JobResponse,
    OfferResponse,
)

app = FastAPI(title="BAFA Web API", version="0.1.0")

_cors_raw = os.getenv("WEB_CORS_ORIGINS", "*").strip()
if _cors_raw == "*":
    _cors_origins = ["*"]
else:
    _cors_origins = [item.strip() for item in _cors_raw.split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(bind=ENGINE)


_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>BAFA Check</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
      :root{
        --bg0:#0b0d12;
        --bg1:#0f1320;
        --card:#121829;
        --card2:#0f1628;
        --text:#e8ecff;
        --muted:#a9b2d6;
        --faint:#6f789b;
        --line:rgba(255,255,255,.10);
        --line2:rgba(255,255,255,.16);
        --accent:#56d7ff;
        --accent2:#ffce5a;
        --danger:#ff4d7d;
        --ok:#4dff9b;
        --warn:#ffd369;
        --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        --sans: "Space Grotesk", ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      }

      *{box-sizing:border-box}
      html,body{height:100%}
      body{
        margin:0;
        color:var(--text);
        font-family:var(--sans);
        background:
          radial-gradient(1100px 700px at 16% 0%, rgba(86,215,255,.18), transparent 60%),
          radial-gradient(800px 500px at 100% 30%, rgba(255,206,90,.12), transparent 55%),
          linear-gradient(180deg, var(--bg0), var(--bg1));
      }

      a{color:inherit}
      .wrap{max-width:1200px;margin:0 auto;padding:18px 16px 40px}
      header{
        display:flex;align-items:center;justify-content:space-between;gap:12px;
        padding:14px 14px;border:1px solid var(--line);border-radius:18px;
        background:rgba(18,24,41,.65);backdrop-filter: blur(10px);
      }
      .brand{display:flex;flex-direction:column;gap:2px}
      .brand .t{font-weight:600;letter-spacing:.2px}
      .brand .s{font-size:13px;color:var(--muted)}
      .actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}
      button{
        border:1px solid var(--line2);
        background:linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.02));
        color:var(--text);
        padding:10px 12px;border-radius:14px;
        font-family:var(--sans);
        font-weight:600;
        cursor:pointer;
      }
      button:hover{border-color:rgba(255,255,255,.24)}
      button:disabled{opacity:.45;cursor:not-allowed}
      .btn-accent{
        border-color:rgba(86,215,255,.35);
        background:linear-gradient(180deg, rgba(86,215,255,.22), rgba(86,215,255,.06));
      }
      .btn-warn{
        border-color:rgba(255,206,90,.35);
        background:linear-gradient(180deg, rgba(255,206,90,.22), rgba(255,206,90,.06));
      }
      .btn-danger{
        border-color:rgba(255,77,125,.35);
        background:linear-gradient(180deg, rgba(255,77,125,.20), rgba(255,77,125,.06));
      }

      main{margin-top:14px;display:grid;grid-template-columns: 360px 1fr;gap:14px}
      @media (max-width: 980px){
        main{grid-template-columns: 1fr}
      }

      .card{
        border:1px solid var(--line);
        border-radius:18px;
        background:rgba(18,24,41,.55);
        backdrop-filter: blur(10px);
        overflow:hidden;
      }
      .card .hd{
        padding:14px 14px;
        display:flex;align-items:flex-end;justify-content:space-between;gap:10px;
        border-bottom:1px solid var(--line);
        background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,0));
      }
      .card .hd .h{
        font-weight:700;letter-spacing:.2px
      }
      .card .hd .sub{font-size:12px;color:var(--muted)}
      .card .bd{padding:12px 14px}
      .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .row > *{flex:1}
      input[type="text"]{
        width:100%;
        background:rgba(0,0,0,.25);
        border:1px solid var(--line2);
        color:var(--text);
        padding:10px 12px;border-radius:14px;
        font-family:var(--sans);
        outline:none;
      }
      input[type="text"]::placeholder{color:var(--faint)}
      .list{display:flex;flex-direction:column;gap:8px}
      .item{
        border:1px solid var(--line);
        background:rgba(0,0,0,.18);
        padding:10px 10px;border-radius:14px;
        cursor:pointer;
      }
      .item:hover{border-color:rgba(255,255,255,.22)}
      .item.active{border-color:rgba(86,215,255,.45);box-shadow:0 0 0 1px rgba(86,215,255,.12) inset}
      .item .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
      .item .title{font-weight:700}
      .pill{
        font-size:11px;
        padding:3px 8px;border-radius:999px;
        border:1px solid var(--line2);
        color:var(--muted);
        font-family:var(--mono);
      }
      .pill.ok{border-color:rgba(77,255,155,.30);color:rgba(77,255,155,.95)}
      .pill.warn{border-color:rgba(255,211,105,.30);color:rgba(255,211,105,.95)}
      .pill.bad{border-color:rgba(255,77,125,.30);color:rgba(255,77,125,.95)}
      .meta{margin-top:4px;font-size:12px;color:var(--muted)}

      .drop{
        border:1px dashed rgba(86,215,255,.42);
        background:rgba(86,215,255,.06);
        border-radius:16px;
        padding:14px;
        display:flex;flex-direction:column;gap:8px;
      }
      .drop strong{letter-spacing:.2px}
      .drop .hint{font-size:12px;color:var(--muted)}
      .drop.drag{border-color:rgba(255,206,90,.55);background:rgba(255,206,90,.06)}

      .kv{display:grid;grid-template-columns: 130px 1fr;gap:8px 12px}
      .k{color:var(--muted);font-size:12px}
      .v{font-family:var(--mono);font-size:12px;color:rgba(232,236,255,.92);overflow:auto}
      pre{
        margin:0;
        white-space:pre-wrap;
        word-break:break-word;
        font-family:var(--mono);
        font-size:12px;
        color:rgba(232,236,255,.90);
        background:rgba(0,0,0,.22);
        border:1px solid var(--line);
        border-radius:16px;
        padding:12px;
        overflow:auto;
        max-height:460px;
      }
      .grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
      @media (max-width: 980px){.grid2{grid-template-columns:1fr}}
      .small{font-size:12px;color:var(--muted)}
    </style>
  </head>
  <body>
    <div class="wrap">
      <header>
        <div class="brand">
          <div class="t">BAFA Check</div>
          <div class="s">Compile, upload, evaluate (incl. plausibility) directly from your browser.</div>
        </div>
        <div class="actions">
          <button class="btn-warn" id="btnCompile">Compile latest BAFA docs</button>
          <button id="btnRefresh">Refresh</button>
          <a class="small" href="/docs" target="_blank" rel="noopener noreferrer" style="align-self:center;text-decoration:none;opacity:.9">API docs</a>
        </div>
      </header>

      <main>
        <section class="card">
          <div class="hd">
            <div>
              <div class="h">Antraege</div>
              <div class="sub">Create/select a BAFA application.</div>
            </div>
            <div class="sub" id="appsCount">0</div>
          </div>
          <div class="bd">
            <div class="row" style="margin-bottom:10px">
              <input id="newTitle" type="text" placeholder="Title (e.g. Antrag Dach 2026-02)" />
              <button class="btn-accent" id="btnCreate">New</button>
            </div>
            <div class="list" id="appsList"></div>
          </div>
        </section>

        <section class="card">
          <div class="hd">
            <div>
              <div class="h">Workspace</div>
              <div class="sub" id="selSub">Select an application to start.</div>
            </div>
            <div class="sub" id="selId"></div>
          </div>
          <div class="bd">
            <div class="grid2">
              <div>
                <div class="drop" id="drop">
                  <strong>Offer upload</strong>
                  <div class="hint">Drag & drop a <code>.pdf</code> or <code>.txt</code> here (or pick a file).</div>
                  <div class="row" style="margin-top:6px">
                    <input id="filePick" type="file" accept=".pdf,.txt,application/pdf,text/plain" />
                    <button id="btnUpload" class="btn-accent">Upload</button>
                  </div>
                  <div class="small" id="uploadStatus"></div>
                </div>

                <div style="height:12px"></div>

                <div class="card" style="background:rgba(15,22,40,.35)">
                  <div class="hd">
                    <div>
                      <div class="h">Offers</div>
                      <div class="sub">Select one offer to evaluate.</div>
                    </div>
                    <div class="sub" id="offersCount">0</div>
                  </div>
                  <div class="bd">
                    <div class="list" id="offersList"></div>
                    <div style="height:10px"></div>
                    <button id="btnEvaluate" class="btn-warn" disabled>Evaluate + plausibility</button>
                    <div class="small" id="evalStatus" style="margin-top:8px"></div>
                  </div>
                </div>
              </div>

              <div>
                <div class="card" style="background:rgba(15,22,40,.35);margin-bottom:14px">
                  <div class="hd">
                    <div>
                      <div class="h">Evaluations</div>
                      <div class="sub">Latest results for the selected application.</div>
                    </div>
                    <div class="sub" id="evalsCount">0</div>
                  </div>
                  <div class="bd">
                    <div class="list" id="evalsList"></div>
                  </div>
                </div>

                <div class="card" style="background:rgba(15,22,40,.35)">
                  <div class="hd">
                    <div>
                      <div class="h">Details</div>
                      <div class="sub">Job output / evaluation JSON.</div>
                    </div>
                    <div class="sub" id="detailTag"></div>
                  </div>
                  <div class="bd">
                    <pre id="details">{}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>

    <script>
      const state = {
        apps: [],
        selectedAppId: null,
        offers: [],
        selectedOfferId: null,
        evals: [],
      };

      const $ = (id) => document.getElementById(id);

      function pillClass(status){
        const s = String(status || '').toLowerCase();
        if (s.includes('done') || s.includes('live') || s.includes('available') || s.includes('pass')) return 'pill ok';
        if (s.includes('fail') || s.includes('error')) return 'pill bad';
        if (s.includes('queue') || s.includes('run') || s.includes('clarify')) return 'pill warn';
        return 'pill';
      }

      function pretty(obj){
        try { return JSON.stringify(obj, null, 2); } catch(e){ return String(obj); }
      }

      async function api(path, opts = {}){
        const res = await fetch(path, opts);
        let text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch(e){ /* ignore */ }
        if (!res.ok){
          const msg = (data && (data.detail || data.message)) || text || (res.status + ' ' + res.statusText);
          throw new Error(msg);
        }
        return data;
      }

      async function pollJob(jobId, label){
        const start = Date.now();
        while (true){
          const job = await api(`/jobs/${jobId}`);
          $('detailTag').textContent = `job:${jobId} ${job.status}`;
          $('details').textContent = pretty(job);
          if (job.status === 'done' || job.status === 'failed'){
            const full = await api(`/jobs/${jobId}/result`);
            $('details').textContent = pretty(full);
            return full;
          }
          if (Date.now() - start > 10 * 60 * 1000){
            throw new Error(`timeout waiting for job ${jobId}`);
          }
          await new Promise(r => setTimeout(r, 1500));
        }
      }

      function renderApps(){
        $('appsCount').textContent = String(state.apps.length);
        const el = $('appsList');
        el.innerHTML = '';
        for (const app of state.apps){
          const div = document.createElement('div');
          div.className = 'item' + (app.id === state.selectedAppId ? ' active' : '');
          div.onclick = () => selectApp(app.id);
          const top = document.createElement('div');
          top.className = 'top';
          const t = document.createElement('div');
          t.className = 'title';
          t.textContent = app.title || '(untitled)';
          const p = document.createElement('div');
          p.className = pillClass(app.status);
          p.textContent = app.status;
          top.appendChild(t);
          top.appendChild(p);
          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = app.id;
          div.appendChild(top);
          div.appendChild(meta);
          el.appendChild(div);
        }
      }

      function renderOffers(){
        $('offersCount').textContent = String(state.offers.length);
        const el = $('offersList');
        el.innerHTML = '';
        for (const offer of state.offers){
          const div = document.createElement('div');
          div.className = 'item' + (offer.id === state.selectedOfferId ? ' active' : '');
          div.onclick = () => { state.selectedOfferId = offer.id; renderOffers(); syncEvaluateButton(); };
          const top = document.createElement('div');
          top.className = 'top';
          const t = document.createElement('div');
          t.className = 'title';
          t.textContent = offer.filename;
          const p = document.createElement('div');
          p.className = pillClass(offer.extraction_status);
          p.textContent = offer.extraction_status;
          top.appendChild(t);
          top.appendChild(p);
          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = offer.id;
          div.appendChild(top);
          div.appendChild(meta);
          el.appendChild(div);
        }
      }

      function renderEvals(){
        $('evalsCount').textContent = String(state.evals.length);
        const el = $('evalsList');
        el.innerHTML = '';
        for (const ev of state.evals){
          const div = document.createElement('div');
          div.className = 'item';
          div.onclick = () => {
            $('detailTag').textContent = `evaluation:${ev.id}`;
            $('details').textContent = pretty(ev);
          };
          const top = document.createElement('div');
          top.className = 'top';
          const t = document.createElement('div');
          t.className = 'title';
          t.textContent = `Offer ${ev.offer_id.slice(0,8)}…`;
          const p = document.createElement('div');
          p.className = pillClass((ev.evaluation_payload && ev.evaluation_payload.results && ev.evaluation_payload.results[0] && ev.evaluation_payload.results[0].status) || ev.status);
          p.textContent = (ev.plausibility_payload && typeof ev.plausibility_payload.overall_correct === 'boolean')
            ? (ev.plausibility_payload.overall_correct ? 'plausible' : 'NOT plausible')
            : ev.status;
          top.appendChild(t);
          top.appendChild(p);
          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = ev.id;
          div.appendChild(top);
          div.appendChild(meta);
          el.appendChild(div);
        }
      }

      function syncEvaluateButton(){
        const offer = state.offers.find(o => o.id === state.selectedOfferId);
        $('btnEvaluate').disabled = !state.selectedAppId || !offer || offer.extraction_status !== 'done';
      }

      async function refresh(){
        state.apps = await api('/applications');
        if (!state.selectedAppId && state.apps.length) state.selectedAppId = state.apps[0].id;
        renderApps();
        await refreshSelected();
      }

      async function refreshSelected(){
        if (!state.selectedAppId){
          $('selSub').textContent = 'Select an application to start.';
          $('selId').textContent = '';
          state.offers = [];
          state.evals = [];
          state.selectedOfferId = null;
          renderOffers();
          renderEvals();
          syncEvaluateButton();
          return;
        }
        const app = state.apps.find(a => a.id === state.selectedAppId);
        $('selSub').textContent = app ? `${app.title || '(untitled)'} • ${app.status}` : 'Application';
        $('selId').textContent = state.selectedAppId;

        state.offers = await api(`/applications/${state.selectedAppId}/offers`);
        if (state.offers.length && !state.selectedOfferId) state.selectedOfferId = state.offers[0].id;
        if (state.selectedOfferId && !state.offers.find(o => o.id === state.selectedOfferId)) state.selectedOfferId = state.offers[0]?.id || null;
        renderOffers();

        state.evals = await api(`/applications/${state.selectedAppId}/evaluations`);
        renderEvals();

        syncEvaluateButton();
      }

      async function selectApp(appId){
        state.selectedAppId = appId;
        state.selectedOfferId = null;
        renderApps();
        await refreshSelected();
      }

      async function createApp(){
        const title = ($('newTitle').value || '').trim();
        const created = await api('/applications', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({title}),
        });
        $('details').textContent = pretty(created);
        $('detailTag').textContent = 'application:created';
        $('newTitle').value = '';
        await refresh();
        await selectApp(created.id);
      }

      async function compileLatest(){
        $('details').textContent = 'Starting compile...';
        $('detailTag').textContent = 'compile';
        const job = await api('/actions/compile-latest', {method:'POST'});
        $('details').textContent = pretty(job);
        $('detailTag').textContent = `compile job:${job.id}`;
        const result = await pollJob(job.id, 'compile');
        $('details').textContent = pretty(result);
      }

      async function uploadSelected(){
        if (!state.selectedAppId) throw new Error('Select an application first.');
        const fileInput = $('filePick');
        const file = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
        if (!file) throw new Error('Pick a file first.');

        $('uploadStatus').textContent = 'Uploading...';
        const fd = new FormData();
        fd.append('file', file, file.name);
        const job = await api(`/applications/${state.selectedAppId}/offers`, {method:'POST', body: fd});
        $('uploadStatus').textContent = `Uploaded. Extracting (job ${job.id})...`;
        const done = await pollJob(job.id, 'extract');
        $('uploadStatus').textContent = 'Extraction finished.';
        await refreshSelected();
        if (job.offer_id) state.selectedOfferId = job.offer_id;
        renderOffers();
        syncEvaluateButton();
        $('details').textContent = pretty(done);
        $('detailTag').textContent = 'extract result';
      }

      async function evaluateSelected(){
        if (!state.selectedAppId) throw new Error('Select an application first.');
        if (!state.selectedOfferId) throw new Error('Select an offer first.');
        $('evalStatus').textContent = 'Starting evaluation...';
        const job = await api(`/applications/${state.selectedAppId}/offers/${state.selectedOfferId}/evaluate`, {method:'POST'});
        $('evalStatus').textContent = `Running (job ${job.id})...`;
        const done = await pollJob(job.id, 'evaluate');
        $('evalStatus').textContent = 'Done.';
        await refreshSelected();
        $('details').textContent = pretty(done);
        $('detailTag').textContent = 'evaluate result';
      }

      function hookDrop(){
        const dz = $('drop');
        const prevent = (e) => { e.preventDefault(); e.stopPropagation(); };
        ['dragenter','dragover','dragleave','drop'].forEach(ev => dz.addEventListener(ev, prevent));
        dz.addEventListener('dragenter', () => dz.classList.add('drag'));
        dz.addEventListener('dragover', () => dz.classList.add('drag'));
        dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
        dz.addEventListener('drop', async (e) => {
          dz.classList.remove('drag');
          const files = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files : null;
          if (!files || !files.length) return;
          $('filePick').files = files;
          try { await uploadSelected(); } catch(err){ alert(err.message || String(err)); }
        });
      }

      function bind(){
        $('btnRefresh').onclick = () => refresh().catch(err => alert(err.message || String(err)));
        $('btnCreate').onclick = () => createApp().catch(err => alert(err.message || String(err)));
        $('btnCompile').onclick = () => compileLatest().catch(err => alert(err.message || String(err)));
        $('btnUpload').onclick = () => uploadSelected().catch(err => alert(err.message || String(err)));
        $('btnEvaluate').onclick = () => evaluateSelected().catch(err => alert(err.message || String(err)));
        hookDrop();
      }

      bind();
      refresh().catch(err => { $('details').textContent = String(err); });
    </script>
  </body>
</html>
"""


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def root() -> str:
    return _UI_HTML


def _job_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        application_id=job.application_id,
        offer_id=job.offer_id,
        payload=job.payload or {},
        result=job.result or {},
        error_message=job.error_message or "",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _enqueue_job(
    session: Session,
    job_type: str,
    payload: dict[str, Any],
    application_id: str | None = None,
    offer_id: str | None = None,
) -> JobRecord:
    job = JobRecord(
        id=str(uuid.uuid4()),
        job_type=job_type,
        status="queued",
        application_id=application_id,
        offer_id=offer_id,
        payload=payload,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    rq_job = get_queue("default").enqueue("webapp.worker_tasks.run_job", job.id)
    job.rq_job_id = rq_job.id
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/applications", response_model=list[ApplicationResponse])
def list_applications(session: Session = Depends(get_session)) -> list[ApplicationResponse]:
    rows = session.query(Application).order_by(Application.created_at.desc()).all()
    return [
        ApplicationResponse(
            id=row.id,
            title=row.title,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.post("/applications", response_model=ApplicationResponse)
def create_application(payload: ApplicationCreate, session: Session = Depends(get_session)) -> ApplicationResponse:
    app_row = Application(title=payload.title or "", status="draft")
    session.add(app_row)
    session.commit()
    session.refresh(app_row)
    return ApplicationResponse(
        id=app_row.id,
        title=app_row.title,
        status=app_row.status,
        created_at=app_row.created_at,
        updated_at=app_row.updated_at,
    )


@app.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: str, session: Session = Depends(get_session)) -> ApplicationResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    return ApplicationResponse(
        id=app_row.id,
        title=app_row.title,
        status=app_row.status,
        created_at=app_row.created_at,
        updated_at=app_row.updated_at,
    )


@app.get("/applications/{application_id}/offers", response_model=list[OfferResponse])
def list_offers(application_id: str, session: Session = Depends(get_session)) -> list[OfferResponse]:
    rows = (
        session.query(Offer)
        .filter(Offer.application_id == application_id)
        .order_by(Offer.created_at.desc())
        .all()
    )
    return [
        OfferResponse(
            id=row.id,
            application_id=row.application_id,
            filename=row.filename,
            mime_type=row.mime_type,
            extraction_status=row.extraction_status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.get("/applications/{application_id}/evaluations", response_model=list[EvaluationResponse])
def list_evaluations(application_id: str, session: Session = Depends(get_session)) -> list[EvaluationResponse]:
    rows = (
        session.query(Evaluation)
        .filter(Evaluation.application_id == application_id)
        .order_by(Evaluation.created_at.desc())
        .all()
    )
    return [
        EvaluationResponse(
            id=row.id,
            application_id=row.application_id,
            offer_id=row.offer_id,
            status=row.status,
            evaluation_payload=row.evaluation_payload or {},
            plausibility_payload=row.plausibility_payload or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.post("/actions/compile-latest", response_model=JobResponse)
def compile_latest(session: Session = Depends(get_session)) -> JobResponse:
    job = _enqueue_job(
        session=session,
        job_type="compile_latest_bafa",
        payload={},
        application_id=None,
        offer_id=None,
    )
    return _job_response(job)


@app.post("/applications/{application_id}/offers", response_model=JobResponse)
async def upload_offer(
    application_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JobResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")

    filename = file.filename or "offer.pdf"
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="only .pdf or .txt offers are supported")
    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty file")

    offer = Offer(
        application_id=application_id,
        filename=filename,
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=blob,
        extraction_status="queued",
    )
    session.add(offer)
    app_row.status = "offer_uploaded"
    session.add(app_row)
    session.commit()
    session.refresh(offer)

    job = _enqueue_job(
        session=session,
        job_type="extract_offer",
        payload={"offer_id": offer.id},
        application_id=application_id,
        offer_id=offer.id,
    )
    return _job_response(job)


@app.post("/applications/{application_id}/offers/{offer_id}/evaluate", response_model=JobResponse)
def evaluate_offer_job(application_id: str, offer_id: str, session: Session = Depends(get_session)) -> JobResponse:
    app_row = session.get(Application, application_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    offer = session.get(Offer, offer_id)
    if offer is None or offer.application_id != application_id:
        raise HTTPException(status_code=404, detail="offer not found")
    if offer.extraction_status != "done":
        raise HTTPException(status_code=409, detail="offer extraction not finished")

    app_row.status = "evaluation_queued"
    session.add(app_row)
    session.commit()

    job = _enqueue_job(
        session=session,
        job_type="evaluate_offer",
        payload={"offer_id": offer_id},
        application_id=application_id,
        offer_id=offer_id,
    )
    return _job_response(job)


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobResponse:
    row = session.get(JobRecord, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_response(row)


@app.get("/jobs/{job_id}/result")
def get_job_result(job_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(JobRecord, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(
        {
            "id": row.id,
            "status": row.status,
            "job_type": row.job_type,
            "result": row.result or {},
            "error": row.error_message or "",
        }
    )
