"""
api.py — Thin FastAPI layer over PipelineRunner.

Exposes the pipeline via HTTP so any device on the Tailscale network
can trigger model generation without opening ports to the internet.

Endpoints:
  GET  /status              — health check
  POST /generate            — text or image → STL
  POST /modify              — modification on existing model → STL

Run with:
  uvicorn api:app --host 0.0.0.0 --port 8000

On Tailscale: accessible at http://<machine-name>:8000 from any
device in your Tailscale network (phone, laptop, etc.)
"""

import base64
import tempfile
import os
import structlog
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from src.graph.pipeline import PipelineRunner
from src.tools.session_logger import SessionLogger
try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    GraphInterrupt = None  # fallback if not available

log = structlog.get_logger()

app = FastAPI(
    title="3D-AI-Pipeline API",
    description="Generate 3D models from text or images via Tailscale",
    version="1.0.0",
)

# Single shared runner — pipeline is built once
_runner = PipelineRunner()
_session_logger = SessionLogger()

# ------------------------------------------------------------------
# Standalone JS served at /app.js
# ------------------------------------------------------------------

_APP_JS = """\
// ── State (declared first — must be initialized before any IIFE runs) ─────────
let _currentState = null;  // pipeline_state for /modify
let _lastDesc     = '';     // original description (for question retry)
let _lastImg      = null;   // original image file  (for question retry)

// ── Agent icon map (declared early so renderTraces always has it) ─────────────
const _ICONS = {
  interpreter:'🧠', planner:'📐',
  plan_validator:'✅', coder:'💻', executor:'⚙️',
  validator:'🔍', code_fixer:'🛠️'
};

// ── Pure-JS STL viewer — no CDN, no external dependencies ────────────────────

function parseBinarySTL(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const nTri = dv.getUint32(80, true);
  const tris = new Array(nTri);
  let off = 84;
  for (let i = 0; i < nTri; i++) {
    const nx = dv.getFloat32(off,   true);
    const ny = dv.getFloat32(off+4, true);
    const nz = dv.getFloat32(off+8, true);
    off += 12;
    const v = [];
    for (let j = 0; j < 3; j++) {
      v.push([dv.getFloat32(off,true), dv.getFloat32(off+4,true), dv.getFloat32(off+8,true)]);
      off += 12;
    }
    off += 2;
    tris[i] = { n:[nx,ny,nz], v };
  }
  return tris;
}

function centerAndScale(tris) {
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity,z0=Infinity,z1=-Infinity;
  for (const t of tris) for (const [x,y,z] of t.v) {
    if(x<x0)x0=x; if(x>x1)x1=x;
    if(y<y0)y0=y; if(y>y1)y1=y;
    if(z<z0)z0=z; if(z>z1)z1=z;
  }
  const cx=(x0+x1)/2, cy=(y0+y1)/2, cz=(z0+z1)/2;
  const s = 180 / Math.max(x1-x0, y1-y0, z1-z0, 0.001);
  for (const t of tris)
    t.v = t.v.map(([x,y,z]) => [(x-cx)*s, (y-cy)*s, (z-cz)*s]);
}

function showViewer(bytes) {
  const tris = parseBinarySTL(bytes);
  centerAndScale(tris);

  const wrap   = document.getElementById('viewer-wrap');
  const canvas = document.getElementById('c');
  wrap.style.display = 'block';

  const dpr = window.devicePixelRatio || 1;
  const W   = wrap.clientWidth;
  const H   = Math.round(W * 0.75);
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  let rotX = 0.45, rotY = -0.6, zoom = 1.0;
  let dragging = false, lastX = 0, lastY = 0, pinchD = 0;

  // Light direction (normalised)
  const LX=0.577, LY=0.577, LZ=0.577;

  function rotVec([x,y,z], rx, ry) {
    const cY=Math.cos(ry), sY=Math.sin(ry);
    [x,z] = [x*cY - z*sY, x*sY + z*cY];
    const cX=Math.cos(rx), sX=Math.sin(rx);
    [y,z] = [y*cX - z*sX, y*sX + z*cX];
    return [x,y,z];
  }

  function proj([x,y,z]) {
    const fov = 320*zoom;
    const d   = fov / (fov + z + 280);
    return [W/2 + x*d, H/2 - y*d, z];
  }

  function render() {
    ctx.fillStyle = '#1a1f2e';
    ctx.fillRect(0, 0, W, H);

    const visible = [];
    for (const t of tris) {
      const rv = t.v.map(v => rotVec(v, rotX, rotY));
      // Back-face cull via screen-space cross product
      const ax=rv[1][0]-rv[0][0], ay=rv[1][1]-rv[0][1];
      const bx=rv[2][0]-rv[0][0], by=rv[2][1]-rv[0][1];
      if (ax*by - ay*bx > 0) continue;

      const rn = rotVec(t.n, rotX, rotY);
      const dot = Math.max(0, rn[0]*LX + rn[1]*LY + rn[2]*LZ);
      const shade = 25 + Math.round(dot * 210);
      const p = rv.map(proj);
      const depth = (p[0][2]+p[1][2]+p[2][2]) / 3;
      visible.push({ p, shade, depth });
    }

    visible.sort((a,b) => b.depth - a.depth);

    for (const { p, shade } of visible) {
      ctx.beginPath();
      ctx.moveTo(p[0][0], p[0][1]);
      ctx.lineTo(p[1][0], p[1][1]);
      ctx.lineTo(p[2][0], p[2][1]);
      ctx.closePath();
      ctx.fillStyle = `rgb(${Math.round(shade*.35)},${Math.round(shade*.52)},${shade})`;
      ctx.fill();
    }
  }

  render();

  // Mouse
  canvas.addEventListener('mousedown', e=>{dragging=true; lastX=e.clientX; lastY=e.clientY;});
  window.addEventListener('mouseup',   ()=>{dragging=false;});
  window.addEventListener('mousemove', e=>{
    if(!dragging) return;
    rotY+=(e.clientX-lastX)*0.012; rotX+=(e.clientY-lastY)*0.012;
    lastX=e.clientX; lastY=e.clientY; render();
  });
  canvas.addEventListener('wheel', e=>{
    zoom *= e.deltaY>0 ? 0.92 : 1.09; render(); e.preventDefault();
  },{passive:false});

  // Touch
  canvas.addEventListener('touchstart', e=>{
    if(e.touches.length===1){
      dragging=true; lastX=e.touches[0].clientX; lastY=e.touches[0].clientY;
    } else if(e.touches.length===2){
      dragging=false;
      const dx=e.touches[0].clientX-e.touches[1].clientX;
      const dy=e.touches[0].clientY-e.touches[1].clientY;
      pinchD=Math.sqrt(dx*dx+dy*dy);
    }
    e.preventDefault();
  },{passive:false});

  canvas.addEventListener('touchmove', e=>{
    if(e.touches.length===1 && dragging){
      rotY+=(e.touches[0].clientX-lastX)*0.012;
      rotX+=(e.touches[0].clientY-lastY)*0.012;
      lastX=e.touches[0].clientX; lastY=e.touches[0].clientY; render();
    } else if(e.touches.length===2 && pinchD){
      const dx=e.touches[0].clientX-e.touches[1].clientX;
      const dy=e.touches[0].clientY-e.touches[1].clientY;
      const d=Math.sqrt(dx*dx+dy*dy);
      zoom*=d/pinchD; pinchD=d; render();
    }
    e.preventDefault();
  },{passive:false});

  canvas.addEventListener('touchend',()=>{dragging=false; pinchD=0;});
}

// ── Agent-Radio-Buttons generieren ───────────────────────────────────────────
(function() {
  const agents = ['Interpreter','Task-Classifier','Planner','Plan-Validator','Coder','Validator'];
  const div = document.getElementById('agent-radios');
  if (!div) return;  // safety: skip if element not yet in DOM
  agents.forEach(function(a) {
    const id = 'ra-' + a;
    div.innerHTML +=
      '<input type="radio" name="err-agent" value="' + a + '" class="agent-radio" id="' + id + '">' +
      '<label for="' + id + '" class="agent-label">' + a + '</label>';
  });
})();

async function saveError() {
  const note    = document.getElementById('err-note').value;
  const agentEl = document.querySelector('input[name="err-agent"]:checked');
  const runId   = document.getElementById('current-run-id').value;
  const errSt   = document.getElementById('err-status');
  if (!agentEl) { alert('Bitte Agent auswählen'); return; }
  try {
    const resp = await fetch('/report_error', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({run_id: runId, error_agent: agentEl.value, note: note}),
    });
    errSt.textContent = resp.ok ? '✅ Fehler gespeichert' : '❌ Fehler beim Speichern';
  } catch(e) {
    errSt.textContent = '❌ Verbindungsfehler';
  }
}

// ── Agent traces ─────────────────────────────────────────────────────────────
function renderTraces(traces) {
  const section   = document.getElementById('traces-section');
  const container = document.getElementById('traces-container');
  if (!traces || !traces.length) { section.style.display = 'none'; return; }

  container.innerHTML = '';
  traces.forEach(function(t) {
    const icon  = _ICONS[t.agent] || '🤖';
    const name  = (t.agent || '').replace(/_/g, ' ');
    const ms    = t.duration_ms ? Math.round(t.duration_ms) + ' ms' : '';
    const rev   = t.revision ? '<span class="trace-rev">\\u21a9 Revision</span>' : '';

    const d = document.createElement('details');
    d.className = 'trace-item';

    const s = document.createElement('summary');
    s.className = 'trace-summary';
    s.innerHTML =
      icon + ' <span class="trace-name">' + name + '</span>' +
      (t.model ? '<span class="trace-model">' + t.model + '</span>' : '') +
      (ms      ? '<span class="trace-ms">' + ms + '</span>' : '') +
      rev;
    d.appendChild(s);

    const body = document.createElement('div');
    body.className = 'trace-body';
    if (t.input && Object.keys(t.input).length) {
      body.innerHTML += '<div class="trace-label">Input</div>' +
        '<pre class="trace-pre">' + JSON.stringify(t.input, null, 2) + '</pre>';
    }
    if (t.output && Object.keys(t.output).length) {
      body.innerHTML += '<div class="trace-label">Output</div>' +
        '<pre class="trace-pre">' + JSON.stringify(t.output, null, 2) + '</pre>';
    }
    d.appendChild(body);
    container.appendChild(d);
  });

  section.style.display = 'block';
}

// ── Main ─────────────────────────────────────────────────────────────────────
function go() { _goAsync().catch(function(e) {
  var st = document.getElementById('status');
  st.className = 'err'; st.style.display = 'block';
  st.textContent = 'Fehler: ' + e.message;
}); }
async function _goAsync() {
  const st  = document.getElementById('status');
  const btn = document.getElementById('btn');
  const vw  = document.getElementById('viewer-wrap');

  // Immediately show spinner so we know the click registered
  st.className = 'loading';
  st.style.display = 'block';
  st.innerHTML = '<span class="spin"></span>Starte…';

  const desc = document.getElementById('desc').value.trim();
  const imgFile = document.getElementById('img').files[0];
  if (!desc && !imgFile) {
    st.style.display = 'none';
    alert('Bitte Beschreibung eingeben oder Bild auswählen.');
    return;
  }

  // Save for question retry, then clear the input
  _lastDesc = desc;
  _lastImg  = imgFile;
  document.getElementById('desc').value = '';

  btn.disabled = true;
  btn.style.display = 'block';
  document.getElementById('action-btns').classList.remove('visible');
  document.getElementById('modify-section').style.display = 'none';
  document.getElementById('error-section').style.display = 'none';
  document.getElementById('traces-section').style.display = 'none';
  document.getElementById('err-status').textContent = '';
  vw.style.display = 'none';
  st.innerHTML = '<span class="spin"></span>Generiere Modell… das dauert 1–3 Minuten.';

  const taskId = (document.getElementById('task-id') || {}).value || '';
  const body = { description: desc, task_id: taskId || null };
  if (imgFile) {
    const b64 = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = rej;
      r.readAsDataURL(imgFile);
    });
    body.image_base64 = b64.split(',')[1];
    body.image_name = imgFile.name;
  }

  try {
    const resp = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (data.clarification_question) {
      st.style.display = 'none';
      document.getElementById('q-text').textContent = data.clarification_question;
      document.getElementById('q-modal').classList.add('open');
      btn.disabled = false;
      return;
    }

    if (data.success && data.stl_base64) {
      _currentState = data.pipeline_state || null;
      const s = data.stats || {};
      let info = `✅ Fertig! (${data.attempts} Versuch(e))`;
      if (s.extents_mm) {
        const e = s.extents_mm;
        info += `<br><small>${e[0]} × ${e[1]} × ${e[2]} mm`;
        if (s.volume_mm3) info += `  |  Vol: ${Math.round(s.volume_mm3).toLocaleString()} mm³`;
        info += '</small>';
      }
      st.className = 'ok';
      st.innerHTML = info;

      const bytes = Uint8Array.from(atob(data.stl_base64), c => c.charCodeAt(0));
      if (data.run_id) document.getElementById('current-run-id').value = data.run_id;
      showViewer(bytes);
      renderTraces(data.agent_traces);
      document.getElementById('error-section').style.display = 'block';
      btn.style.display = 'none';
      document.getElementById('action-btns').classList.add('visible');
    } else {
      st.className = 'err';
      st.textContent = '❌ ' + (data.error || data.detail || 'Unbekannter Fehler');
    }
  } catch (e) {
    st.className = 'err';
    st.textContent = '❌ Verbindungsfehler: ' + e.message;
  }
  btn.disabled = false;
}
function answerQuestion() {
  const answer = document.getElementById('q-answer').value.trim();
  if (!answer) { alert('Bitte Antwort eingeben'); return; }
  document.getElementById('q-modal').classList.remove('open');
  document.getElementById('q-answer').value = '';
  // Combined description → re-run generate
  document.getElementById('desc').value = _lastDesc + '\\n\\n' + answer;
  go();
}

function newPart() {
  _currentState = null;
  document.getElementById('desc').value = '';
  document.getElementById('img').value  = '';
  document.getElementById('viewer-wrap').style.display    = 'none';
  document.getElementById('traces-section').style.display = 'none';
  document.getElementById('error-section').style.display  = 'none';
  document.getElementById('modify-section').style.display = 'none';
  document.getElementById('action-btns').classList.remove('visible');
  document.getElementById('status').style.display = 'none';
  document.getElementById('btn').style.display    = 'block';
}

function startModify() {
  document.getElementById('modify-section').style.display = 'block';
  document.getElementById('mod-desc').focus();
}

async function applyModify() {
  const modDesc = document.getElementById('mod-desc').value.trim();
  if (!modDesc)      { alert('Bitte Änderung beschreiben'); return; }
  if (!_currentState){ alert('Kein Modell vorhanden');     return; }

  const applyBtn = document.getElementById('mod-apply-btn');
  const st       = document.getElementById('status');
  applyBtn.disabled = true;
  document.getElementById('action-btns').classList.remove('visible');
  document.getElementById('modify-section').style.display = 'none';
  document.getElementById('error-section').style.display  = 'none';
  document.getElementById('traces-section').style.display = 'none';
  st.className = 'loading';
  st.style.display = 'block';
  st.innerHTML = '<span class="spin"></span>Modifikation wird angewendet…';

  try {
    const resp = await fetch('/modify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modification: modDesc, previous_state: _currentState, task_id: (document.getElementById('task-id') || {}).value || null }),
    });
    const data = await resp.json();

    if (data.success && data.stl_base64) {
      _currentState = data.pipeline_state || _currentState;
      const s = data.stats || {};
      let info = `✅ Fertig! (${data.attempts} Versuch(e))`;
      if (s.extents_mm) {
        const e = s.extents_mm;
        info += `<br><small>${e[0]} × ${e[1]} × ${e[2]} mm`;
        if (s.volume_mm3) info += `  |  Vol: ${Math.round(s.volume_mm3).toLocaleString()} mm³`;
        info += '</small>';
      }
      st.className = 'ok';
      st.innerHTML = info;
      const bytes = Uint8Array.from(atob(data.stl_base64), c => c.charCodeAt(0));
      if (data.run_id) document.getElementById('current-run-id').value = data.run_id;
      showViewer(bytes);
      renderTraces(data.agent_traces);
      document.getElementById('error-section').style.display = 'block';
      document.getElementById('mod-desc').value = '';
      document.getElementById('btn').style.display = 'none';
      document.getElementById('action-btns').classList.add('visible');
    } else {
      st.className = 'err';
      st.textContent = '❌ ' + (data.error || data.detail || 'Fehler');
      document.getElementById('action-btns').classList.add('visible');
      document.getElementById('modify-section').style.display = 'block';
    }
  } catch(e) {
    st.className = 'err';
    st.textContent = '❌ Verbindungsfehler: ' + e.message;
    document.getElementById('action-btns').classList.add('visible');
  }
  applyBtn.disabled = false;
}
"""


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------

class GenerateRequest(BaseModel):
    description: str = ""
    image_base64: Optional[str] = None   # base64-encoded image (JPEG/PNG)
    image_name: Optional[str] = "image.jpg"
    task_id: Optional[str] = None        # optional task identifier for filtering runs


class ModifyRequest(BaseModel):
    modification: str
    previous_state: dict   # the state dict returned by /generate or /modify
    task_id: Optional[str] = None        # optional task identifier for filtering runs


class PipelineResponse(BaseModel):
    success: bool
    stl_base64: Optional[str] = None     # base64-encoded STL bytes
    stl_filename: Optional[str] = None
    blueprint: Optional[dict] = None
    specification: Optional[str] = None
    stats: Optional[dict] = None         # size_mm, volume_mm3
    error: Optional[str] = None
    attempts: int = 0
    run_id: Optional[str] = None         # session log ID for error reporting
    agent_traces: Optional[list] = None           # per-agent trace data for mobile UI
    clarification_question: Optional[str] = None  # interpreter needs more info
    pipeline_state: Optional[dict] = None          # minimal state for /modify


class ErrorReportRequest(BaseModel):
    run_id: str
    error_agent: str
    note: str = ""


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def mobile_ui():
    """Mobile-friendly web UI — open http://<tailscale-ip>:8000 on any device."""
    return """<!DOCTYPE html>
<html lang="de"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>3D-AI-Pipeline</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f1117;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px;min-height:100vh}
  h1{color:#63b3ed;font-size:1.4rem;margin-bottom:4px}
  .sub{color:#4a5568;font-size:.85rem;margin-bottom:24px}
  label{display:block;color:#a0aec0;font-size:.85rem;margin-bottom:6px}
  textarea,input[type=file]{
    width:100%;padding:12px;background:#1a1f2e;
    border:1px solid #2d3748;border-radius:8px;
    color:#e2e8f0;font-size:1rem;margin-bottom:16px
  }
  textarea{min-height:120px;resize:vertical}
  input[type=file]{color:#718096;padding:10px}
  button#btn{
    width:100%;padding:14px;background:#3182ce;
    border:none;border-radius:8px;color:#fff;
    font-size:1.1rem;font-weight:700;cursor:pointer;
    touch-action:manipulation
  }
  button#btn:disabled{background:#2d3748;color:#4a5568;cursor:not-allowed}
  #status{
    margin-top:20px;padding:14px;background:#1a1f2e;
    border-radius:8px;display:none;text-align:center;line-height:1.6
  }
  #status.loading{border:1px solid #63b3ed;color:#63b3ed}
  #status.ok{border:1px solid #68d391;color:#68d391}
  #status.err{border:1px solid #fc8181;color:#fc8181}
  #viewer-wrap{
    display:none;margin-top:16px;border-radius:8px;overflow:hidden;
    background:#1a1f2e;border:1px solid #2d3748;position:relative
  }
  #viewer-wrap canvas{display:block;width:100%!important;touch-action:none}
  #viewer-hint{
    position:absolute;bottom:8px;left:0;right:0;
    text-align:center;color:#4a5568;font-size:.75rem;pointer-events:none
  }
  #error-section{display:none;margin-top:16px}
  #error-section label{display:block;color:#a0aec0;font-size:.85rem;margin-bottom:6px}
  #err-note{
    width:100%;min-height:80px;padding:10px;background:#1a1f2e;
    border:1px solid #2d3748;border-radius:8px;color:#e2e8f0;
    font-size:.95rem;resize:vertical;margin-bottom:10px
  }
  #agent-radios{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
  .agent-radio{display:none}
  .agent-label{
    padding:6px 12px;background:#1a1f2e;border:1px solid #2d3748;
    border-radius:6px;cursor:pointer;font-size:.85rem;color:#a0aec0
  }
  .agent-radio:checked+.agent-label{
    background:#2c5282;border-color:#63b3ed;color:#e2e8f0
  }
  #save-err-btn{
    width:100%;padding:12px;background:#9b2c2c;border:none;
    border-radius:8px;color:#fff;font-size:1rem;cursor:pointer
  }
  #err-status{margin-top:8px;text-align:center;font-size:.9rem;color:#a0aec0}
  #img-clear{display:none;width:100%;padding:8px;background:#2d3748;border:none;border-radius:8px;color:#a0aec0;cursor:pointer;margin-top:-10px;margin-bottom:16px;font-size:.85rem;touch-action:manipulation}
  #action-btns{display:none;gap:10px;margin-top:16px}
  #action-btns.visible{display:flex}
  #new-btn,#mod-start-btn{
    flex:1;padding:12px;border:none;border-radius:8px;
    color:#e2e8f0;font-size:.95rem;cursor:pointer
  }
  #new-btn{background:#2d3748}
  #mod-start-btn{background:#2c5282}
  #modify-section{display:none;margin-top:16px}
  #mod-desc{
    width:100%;min-height:80px;padding:10px;background:#1a1f2e;
    border:1px solid #2d3748;border-radius:8px;color:#e2e8f0;
    font-size:.95rem;resize:vertical;margin-bottom:10px
  }
  #mod-apply-btn{
    width:100%;padding:12px;background:#276749;border:none;
    border-radius:8px;color:#fff;font-size:1rem;cursor:pointer
  }
  #mod-apply-btn:disabled{background:#2d3748;color:#4a5568;cursor:not-allowed}
  #q-modal{display:none}
  #q-modal.open{
    display:flex;position:fixed;top:0;left:0;right:0;bottom:0;
    background:rgba(0,0,0,.8);z-index:100;
    align-items:center;justify-content:center;padding:20px
  }
  #q-box{
    background:#1a1f2e;border:1px solid #2d3748;border-radius:12px;
    padding:20px;max-width:420px;width:100%
  }
  #q-text{color:#e2e8f0;margin-bottom:14px;line-height:1.5;font-size:.95rem}
  #q-answer{
    width:100%;min-height:70px;padding:10px;background:#0f1117;
    border:1px solid #2d3748;border-radius:8px;color:#e2e8f0;
    font-size:.95rem;resize:vertical;margin-bottom:10px
  }
  #q-send-btn{
    width:100%;padding:12px;background:#3182ce;border:none;
    border-radius:8px;color:#fff;font-size:1rem;cursor:pointer
  }
  #traces-section{margin-top:16px}
  #traces-section h3{color:#718096;font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
  .trace-item{background:#1a1f2e;border:1px solid #2d3748;border-radius:8px;margin-bottom:6px;overflow:hidden}
  .trace-summary{padding:10px 14px;cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;font-size:.9rem}
  .trace-summary::-webkit-details-marker{display:none}
  .trace-name{color:#e2e8f0;text-transform:capitalize;flex:1}
  .trace-model{color:#4a5568;font-size:.75rem}
  .trace-ms{color:#4a5568;font-size:.75rem}
  .trace-rev{color:#f6ad55;font-size:.75rem;margin-left:4px}
  .trace-body{padding:10px 14px;border-top:1px solid #2d3748}
  .trace-label{color:#63b3ed;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
  .trace-pre{background:#0f1117;border-radius:6px;padding:10px;font-size:.72rem;color:#a0aec0;overflow-x:auto;white-space:pre-wrap;word-break:break-all;max-height:250px;overflow-y:auto;margin-bottom:8px}
  .spin{
    display:inline-block;width:18px;height:18px;
    border:3px solid rgba(99,179,237,.3);border-top-color:#63b3ed;
    border-radius:50%;animation:sp .8s linear infinite;vertical-align:middle;margin-right:6px
  }
  @keyframes sp{to{transform:rotate(360deg)}}
  small{color:#718096;font-size:.8rem}
  #desc-row{display:flex;gap:10px;align-items:flex-start;margin-bottom:16px}
  #desc-row>div:first-child{flex:1;min-width:0}
  #desc-row>div:first-child textarea{margin-bottom:0}
  #task-id-wrap{width:72px;flex-shrink:0}
  #task-id-wrap label{display:block;color:#a0aec0;font-size:.85rem;margin-bottom:6px}
  #task-id{width:100%;padding:10px 8px;background:#1a1f2e;border:1px solid #2d3748;border-radius:8px;color:#e2e8f0;font-size:.95rem;text-align:center}
</style>
</head><body>
<h1>🔧 3D-AI-Pipeline</h1>
<p class="sub">Modell beschreiben → 3D Generierung.</p>

<div id="desc-row">
  <div>
    <label>Beschreibung</label>
    <textarea id="desc" placeholder="Ein 30mm Würfel mit zentraler M3-Bohrung auf der Oberseite..."></textarea>
  </div>
  <div id="task-id-wrap">
    <label>Task-ID</label>
    <input type="text" id="task-id" placeholder="z.B. 4" maxlength="20">
  </div>
</div>

<label>Bild / Skizze (optional)</label>
<input type="file" id="img" accept="image/*" onchange="document.getElementById('img-clear').style.display=this.files.length?'block':'none'">
<button id="img-clear" onclick="document.getElementById('img').value='';this.style.display='none'">&#x2715; Bild entfernen</button>

<button id="btn" onclick="go()">Generieren</button>
<div id="action-btns">
  <button id="new-btn" onclick="newPart()">🔄 Neues Teil</button>
  <button id="mod-start-btn" onclick="startModify()">✏️ Modifizieren</button>
</div>
<div id="status"></div>
<div id="viewer-wrap">
  <canvas id="c"></canvas>
  <div id="viewer-hint">Ziehen = drehen  ·  2 Finger = zoom</div>
</div>
<div id="modify-section">
  <label>Änderung beschreiben</label>
  <textarea id="mod-desc" placeholder="z.B. M4 Bohrung auf 6mm vergrößern…"></textarea>
  <button id="mod-apply-btn" onclick="applyModify()">Änderung anwenden</button>
</div>
<div id="q-modal">
  <div id="q-box">
    <p id="q-text"></p>
    <textarea id="q-answer" placeholder="Ihre Antwort…"></textarea>
    <button id="q-send-btn" onclick="answerQuestion()">Antworten ➔</button>
  </div>
</div>
<input type="hidden" id="current-run-id" value="">
<div id="traces-section" style="display:none">
  <h3>Agent-Antworten</h3>
  <div id="traces-container"></div>
</div>
<div id="error-section">
  <label>Fehlerbeschreibung</label>
  <textarea id="err-note" placeholder="z.B. Fase fehlt, Maße falsch…"></textarea>
  <label>Fehler verursacht durch:</label>
  <div id="agent-radios"></div>
  <button id="save-err-btn" onclick="saveError()">Fehler speichern</button>
  <div id="err-status"></div>
</div>

<script>
// ── Error handlers isolated — work even if main script has syntax errors ───────
window.onerror = function(msg, src, line, col, err) {
  var st = document.getElementById('status');
  if (st) { st.style.display='block'; st.className='err'; st.textContent='JS-Fehler: '+msg+' (Zeile '+line+')'; }
  return false;
};
window.addEventListener('unhandledrejection', function(e) {
  var st = document.getElementById('status');
  if (st) { st.style.display='block'; st.className='err'; st.textContent='Promise-Fehler: '+(e.reason&&e.reason.message||String(e.reason)); }
});
</script>
<script src="/app.js"></script>
<script>
// ── Verify main script loaded — shows error if go() is missing ────────────────
var _diag = [];
if (typeof go !== 'function')   _diag.push('go fehlt');
if (typeof _goAsync !== 'function') _diag.push('_goAsync fehlt');
if (typeof renderTraces !== 'function') _diag.push('renderTraces fehlt');
if (_diag.length) {
  var _s = document.getElementById('status');
  if (_s) { _s.style.display='block'; _s.className='err'; _s.textContent='Script-Fehler: '+_diag.join(', ')+'. Bitte Konsole prüfen.'; }
}
</script>
</body></html>"""


@app.get("/app.js")
def app_js():
    """Serve the mobile UI JavaScript."""
    from fastapi.responses import Response
    return Response(content=_APP_JS, media_type="application/javascript")


@app.get("/status")
def status():
    """Health check — returns 200 if the API is running."""
    return {"ready": True, "service": "3D-AI-Pipeline"}


@app.post("/report_error")
def report_error(req: ErrorReportRequest):
    """Save error feedback for a run (from mobile UI)."""
    _session_logger.update_feedback(
        req.run_id, "bad",
        error_agent=req.error_agent.lower().replace("-", "_"),
        error_note=req.note.strip(),
    )
    return {"ok": True}


@app.post("/generate", response_model=PipelineResponse)
def generate(req: GenerateRequest):
    """Generate a 3D model from a text description or image.

    - Text only:  set description
    - Image only: set image_base64 (Visioner will extract the spec)
    - Both:       image_base64 + description as hint for Visioner
    """
    if not req.description and not req.image_base64:
        raise HTTPException(400, "Provide either description or image_base64")

    image_path = ""

    # If image provided: decode and save to temp file
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
            suffix = Path(req.image_name or "image.jpg").suffix or ".jpg"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, prefix="api_img_"
            ) as f:
                f.write(image_bytes)
                image_path = f.name
            log.info("api_generate_image_saved", path=image_path, bytes=len(image_bytes))
        except Exception as e:
            raise HTTPException(400, f"Invalid image_base64: {e}")

    try:
        state = _runner.run(
            description=req.description,
            image_path=image_path,
        )
    except Exception as e:
        if GraphInterrupt and isinstance(e, GraphInterrupt):
            question = e.interrupts[0].value if getattr(e, "interrupts", None) else str(e)
            log.info("api_generate_question", question=question)
            return PipelineResponse(success=False, clarification_question=str(question))
        log.error("api_generate_failed", error=str(e))
        raise HTTPException(500, f"Pipeline error: {e}")
    finally:
        # Clean up temp image
        if image_path and os.path.exists(image_path):
            os.unlink(image_path)

    resp = _build_response(state)
    resp.run_id = _session_logger.log_run(state, feedback="good" if resp.success else "bad", task_id=req.task_id or "")
    return resp


@app.post("/modify", response_model=PipelineResponse)
def modify(req: ModifyRequest):
    """Apply a modification to an existing model.

    Pass the full state dict from a previous /generate or /modify call
    as previous_state. The pipeline will apply the modification on top.
    """
    if not req.modification.strip():
        raise HTTPException(400, "modification must not be empty")

    try:
        state = _runner.modify(
            modification=req.modification,
            previous_state=req.previous_state,
        )
    except Exception as e:
        log.error("api_modify_failed", error=str(e))
        raise HTTPException(500, f"Pipeline error: {e}")

    resp = _build_response(state)
    resp.run_id = _session_logger.log_run(state, feedback="good" if resp.success else "bad", task_id=req.task_id or "")
    return resp


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_response(state: dict) -> PipelineResponse:
    """Convert a PipelineState dict into a PipelineResponse."""
    stl_path = state.get("stl_path", "")
    success = bool(stl_path) and not state.get("validator_feedback")

    stl_b64 = None
    stl_filename = None
    if success and stl_path and Path(stl_path).exists():
        stl_bytes = Path(stl_path).read_bytes()
        stl_b64 = base64.b64encode(stl_bytes).decode("utf-8")
        stl_filename = Path(stl_path).name

    error = None
    if not success:
        error = (
            state.get("execution_error")
            or state.get("validation_error")
            or state.get("validator_feedback")
            or "Unknown error"
        )

    return PipelineResponse(
        success=success,
        stl_base64=stl_b64,
        stl_filename=stl_filename,
        blueprint=state.get("blueprint"),
        specification=state.get("specification"),
        stats=state.get("validator_stats"),
        error=error,
        attempts=state.get("attempts", 0),
        agent_traces=_sanitize_traces(state.get("agent_traces", [])),
        pipeline_state=_state_for_client(state),
    )


def _state_for_client(state: dict) -> dict:
    """Minimal state subset needed for /modify — no binary content."""
    _KEEP = {"blueprint", "stl_path", "code", "geometry_state",
             "specification", "description"}
    return {k: v for k, v in state.items()
            if k in _KEEP and not isinstance(v, bytes)}


def _sanitize_traces(traces: list) -> list:
    """Strip large binary fields and truncate long strings in agent traces."""
    _LARGE_KEYS = {"image_base64", "stl_base64", "stl_bytes"}
    _MAX_STR = 2000
    result = []
    for t in traces:
        clean = dict(t)
        for field in ("input", "output"):
            if isinstance(clean.get(field), dict):
                d = {}
                for k, v in clean[field].items():
                    if k in _LARGE_KEYS:
                        continue
                    if isinstance(v, str) and len(v) > _MAX_STR:
                        v = v[:_MAX_STR] + "…[truncated]"
                    d[k] = v
                clean[field] = d
        result.append(clean)
    return result
