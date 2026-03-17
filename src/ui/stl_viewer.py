"""
src/ui/stl_viewer.py — Generates a self-contained HTML 3D viewer.

Reads an STL file, encodes it as base64, and returns an HTML string
that renders it using Three.js with toggleable dimension lines.

The HTML is fully self-contained — no external file serving needed.
Three.js is loaded from cdnjs. STL data is embedded as base64.

Usage:
    from src.ui.stl_viewer import build_viewer_html
    html = build_viewer_html(stl_path, size_mm=[30, 30, 30], volume_mm3=27000)
"""

import base64
from pathlib import Path


def build_viewer_html(
    stl_path: str,
    size_mm: list[float] | None = None,
    volume_mm3: float | None = None,
) -> str:
    """Return a self-contained HTML string with a 3D STL viewer.

    Args:
        stl_path:   Path to the STL file on disk.
        size_mm:    [x, y, z] bounding box in mm (from trimesh stats).
        volume_mm3: Volume in mm³ (from trimesh stats).
    """
    if not stl_path or not Path(stl_path).exists():
        return _empty_viewer()

    stl_bytes = Path(stl_path).read_bytes()
    stl_b64 = base64.b64encode(stl_bytes).decode("utf-8")

    # Display values for HTML stats bar — "?" when not available
    sx_disp = round(size_mm[0], 1) if size_mm else "?"
    sy_disp = round(size_mm[1], 1) if size_mm else "?"
    sz_disp = round(size_mm[2], 1) if size_mm else "?"
    vol = f"{volume_mm3:,.0f}" if volume_mm3 else "?"
    # JS array values — must be valid numbers; null means "unknown" in JS
    sx = round(size_mm[0], 1) if size_mm else "null"
    sy = round(size_mm[1], 1) if size_mm else "null"
    sz = round(size_mm[2], 1) if size_mm else "null"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0f1117; font-family: 'JetBrains Mono', 'Fira Code', monospace; overflow: hidden; }}
  #viewport {{ width: 100%; height: 420px; display: block; }}
  #controls {{
    position: absolute; top: 12px; right: 12px;
    display: flex; gap: 8px; z-index: 10;
  }}
  .btn {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    color: #a0aec0;
    padding: 6px 14px;
    font-size: 11px;
    font-family: inherit;
    letter-spacing: 0.05em;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.15s;
    text-transform: uppercase;
  }}
  .btn:hover {{ background: rgba(255,255,255,0.12); color: #e2e8f0; }}
  .btn.active {{ background: rgba(99,179,237,0.15); border-color: #63b3ed; color: #63b3ed; }}
  #stats {{
    position: absolute; bottom: 12px; left: 14px;
    font-size: 11px; color: #4a5568;
    letter-spacing: 0.04em;
    line-height: 1.7;
  }}
  #stats span {{ color: #718096; }}
</style>
</head>
<body>
<div style="position:relative; width:100%; height:420px;">
  <canvas id="viewport"></canvas>

  <div id="controls">
    <button class="btn active" id="btn-dims" onclick="toggleDims()">⊡ Maße</button>
    <button class="btn" id="btn-wire" onclick="toggleWire()">⬡ Wire</button>
    <button class="btn" onclick="resetCamera()">⟳ Reset</button>
  </div>

  <div id="stats">
    <span>X</span> {sx_disp} mm &nbsp; <span>Y</span> {sy_disp} mm &nbsp; <span>Z</span> {sz_disp} mm<br>
    <span>VOL</span> {vol} mm³
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
// ── STL DATA ──────────────────────────────────────────────────────────────
const STL_B64 = "{stl_b64}";
const SIZE_MM = [{sx}, {sy}, {sz}];

// ── THREE.JS SETUP ────────────────────────────────────────────────────────
const canvas = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, alpha: true }});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f1117);

// Use 800 as fallback — ResizeObserver corrects it when the tab becomes visible
const _initW = canvas.parentElement.clientWidth || 800;
renderer.setSize(_initW, 420);
const camera = new THREE.PerspectiveCamera(45, _initW / 420, 0.1, 10000);

// Resize renderer + camera when the Gradio tab becomes visible (clientWidth > 0)
new ResizeObserver(() => {{
  const w = canvas.parentElement.clientWidth;
  if (w > 0) {{
    renderer.setSize(w, 420);
    camera.aspect = w / 420;
    camera.updateProjectionMatrix();
  }}
}}).observe(canvas.parentElement);

// Lighting
const ambient = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(ambient);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(1, 2, 3);
scene.add(dirLight);
const fillLight = new THREE.DirectionalLight(0x6090ff, 0.3);
fillLight.position.set(-2, -1, -1);
scene.add(fillLight);

// Grid
const grid = new THREE.GridHelper(200, 20, 0x1a1f2e, 0x1a1f2e);
scene.add(grid);

// ── STL PARSER ───────────────────────────────────────────────────────────
function b64ToBytes(b64) {{
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}}

function parseSTL(bytes) {{
  const dv = new DataView(bytes.buffer);
  // Check ASCII vs binary
  const header = String.fromCharCode(...bytes.slice(0, 5));
  if (header === 'solid') {{
    // Try binary first (ASCII "solid" can appear in binary header)
    const nTri = dv.getUint32(80, true);
    if (80 + 4 + nTri * 50 === bytes.length) {{
      return parseBinarySTL(dv, nTri);
    }}
    return parseASCIISTL(new TextDecoder().decode(bytes));
  }}
  const nTri = dv.getUint32(80, true);
  return parseBinarySTL(dv, nTri);
}}

function parseBinarySTL(dv, nTri) {{
  const positions = new Float32Array(nTri * 9);
  const normals   = new Float32Array(nTri * 9);
  let offset = 84;
  for (let i = 0; i < nTri; i++) {{
    const nx = dv.getFloat32(offset, true);
    const ny = dv.getFloat32(offset + 4, true);
    const nz = dv.getFloat32(offset + 8, true);
    offset += 12;
    for (let v = 0; v < 3; v++) {{
      const base = i * 9 + v * 3;
      positions[base]     = dv.getFloat32(offset, true);
      positions[base + 1] = dv.getFloat32(offset + 4, true);
      positions[base + 2] = dv.getFloat32(offset + 8, true);
      normals[base] = nx; normals[base+1] = ny; normals[base+2] = nz;
      offset += 12;
    }}
    offset += 2; // attribute byte count
  }}
  return {{ positions, normals }};
}}

function parseASCIISTL(text) {{
  const vRe = /vertex\\s+([\\d.eE+\\-]+)\\s+([\\d.eE+\\-]+)\\s+([\\d.eE+\\-]+)/g;
  const nRe = /facet normal\\s+([\\d.eE+\\-]+)\\s+([\\d.eE+\\-]+)\\s+([\\d.eE+\\-]+)/g;
  const positions = []; const normals = [];
  let vm, nm;
  const nMatches = [...text.matchAll(nRe)];
  let ni = 0;
  while ((vm = vRe.exec(text)) !== null) {{
    positions.push(+vm[1], +vm[2], +vm[3]);
    if (ni < nMatches.length) {{
      const n = nMatches[Math.floor(positions.length / 9)];
      if (n) normals.push(+n[1], +n[2], +n[3]);
      else normals.push(0, 1, 0);
    }}
  }}
  return {{ positions: new Float32Array(positions), normals: new Float32Array(normals) }};
}}

// ── BUILD MESH ────────────────────────────────────────────────────────────
const bytes = b64ToBytes(STL_B64);
const {{ positions, normals }} = parseSTL(bytes);

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geo.setAttribute('normal',   new THREE.BufferAttribute(normals, 3));
geo.computeBoundingBox();

const mat = new THREE.MeshPhongMaterial({{
  color: 0x4a9eda,
  specular: 0x222244,
  shininess: 40,
  side: THREE.DoubleSide,
}});
const mesh = new THREE.Mesh(geo, mat);

// Center mesh
const box = new THREE.Box3().setFromObject(mesh);
const center = box.getCenter(new THREE.Vector3());
const size = box.getSize(new THREE.Vector3());
mesh.position.sub(center);
mesh.position.y += size.y / 2;
scene.add(mesh);

// Position camera
const maxDim = Math.max(size.x, size.y, size.z);
camera.position.set(maxDim * 1.2, maxDim * 0.9, maxDim * 1.8);
camera.lookAt(0, size.y / 2, 0);

// ── DIMENSION LINES ───────────────────────────────────────────────────────
let dimsVisible = true;
const dimObjects = [];

function makeDimLine(from, to, color) {{
  const mat = new THREE.LineBasicMaterial({{ color, linewidth: 1.5 }});
  const geo = new THREE.BufferGeometry().setFromPoints([from, to]);
  const line = new THREE.Line(geo, mat);
  scene.add(line);
  dimObjects.push(line);
  return line;
}}

// Build dim lines from bounding box of mesh
const hx = size.x / 2, hy = size.y, hz = size.z / 2;
const pad = maxDim * 0.15;

// X dimension line (front bottom)
makeDimLine(
  new THREE.Vector3(-hx, -1, hz + pad),
  new THREE.Vector3( hx, -1, hz + pad),
  0x63b3ed
);
// Y dimension line (right side)
makeDimLine(
  new THREE.Vector3(hx + pad, 0,  hz),
  new THREE.Vector3(hx + pad, hy, hz),
  0x68d391
);
// Z dimension line (bottom right)
makeDimLine(
  new THREE.Vector3(hx, -1, -hz),
  new THREE.Vector3(hx, -1,  hz),
  0xf6ad55
);

// ── DIM LABELS (Three.js Sprites) ────────────────────────────────────────
// Sprites live inside the 3D scene — no DOM overlay, no CSS, no iframe issues.
// Each sprite uses a small canvas texture with the label text drawn on it.

function makeTextSprite(text, hexColor) {{
  const tc = document.createElement('canvas');
  tc.width = 256; tc.height = 56;
  const cx = tc.getContext('2d');

  cx.font = 'bold 26px monospace';
  const tw = cx.measureText(text).width;

  // Background pill
  cx.fillStyle   = 'rgba(15,17,23,0.88)';
  cx.strokeStyle = hexColor;
  cx.lineWidth   = 2.5;
  const px = (256 - tw) / 2 - 8;
  cx.fillRect(px, 6, tw + 16, 44);
  cx.strokeRect(px, 6, tw + 16, 44);

  // Text
  cx.fillStyle    = hexColor;
  cx.textAlign    = 'center';
  cx.textBaseline = 'middle';
  cx.fillText(text, 128, 28);

  const tex = new THREE.CanvasTexture(tc);
  const mat = new THREE.SpriteMaterial({{
    map: tex, transparent: true,
    depthTest: false, depthWrite: false,
  }});
  const sprite = new THREE.Sprite(mat);
  // Scale in world units: width proportional to maxDim, height keeps 256:56 ratio
  sprite.scale.set(maxDim * 0.45, maxDim * 0.45 * (56 / 256), 1);
  return sprite;
}}

const xLabel = makeTextSprite(
  `X: ${{SIZE_MM[0] != null ? SIZE_MM[0] : '?'}} mm`, '#63b3ed'
);
xLabel.position.set(0, 0, hz + pad);
scene.add(xLabel);
dimObjects.push(xLabel);

const yLabel = makeTextSprite(
  `Y: ${{SIZE_MM[1] != null ? SIZE_MM[1] : '?'}} mm`, '#68d391'
);
yLabel.position.set(hx + pad, hy / 2, hz);
scene.add(yLabel);
dimObjects.push(yLabel);

const zLabel = makeTextSprite(
  `Z: ${{SIZE_MM[2] != null ? SIZE_MM[2] : '?'}} mm`, '#f6ad55'
);
zLabel.position.set(hx, 0, 0);
scene.add(zLabel);
dimObjects.push(zLabel);

// ── ORBIT CONTROLS (manual) ──────────────────────────────────────────────
let isDragging = false, lastX = 0, lastY = 0;
let theta = 0.6, phi = 0.4, radius = maxDim * 2.5;
const target = new THREE.Vector3(0, size.y / 2, 0);

function updateCamera() {{
  camera.position.set(
    target.x + radius * Math.sin(phi) * Math.sin(theta),
    target.y + radius * Math.cos(phi),
    target.z + radius * Math.sin(phi) * Math.cos(theta),
  );
  camera.lookAt(target);
}}
updateCamera();

canvas.addEventListener('mousedown', e => {{ isDragging = true; lastX = e.clientX; lastY = e.clientY; }});
canvas.addEventListener('mouseup',   () => isDragging = false);
canvas.addEventListener('mouseleave',() => isDragging = false);
canvas.addEventListener('mousemove', e => {{
  if (!isDragging) return;
  theta -= (e.clientX - lastX) * 0.008;
  phi    = Math.max(0.05, Math.min(Math.PI - 0.05, phi - (e.clientY - lastY) * 0.008));
  lastX = e.clientX; lastY = e.clientY;
  updateCamera();
}});
canvas.addEventListener('wheel', e => {{
  radius = Math.max(maxDim * 0.5, Math.min(maxDim * 6, radius + e.deltaY * 0.3));
  updateCamera();
  e.preventDefault();
}}, {{ passive: false }});

// Touch support
let lastTouchDist = 0;
canvas.addEventListener('touchstart', e => {{
  if (e.touches.length === 1) {{ isDragging = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY; }}
  if (e.touches.length === 2) lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
}});
canvas.addEventListener('touchend', () => isDragging = false);
canvas.addEventListener('touchmove', e => {{
  if (e.touches.length === 1 && isDragging) {{
    theta -= (e.touches[0].clientX - lastX) * 0.008;
    phi    = Math.max(0.05, Math.min(Math.PI - 0.05, phi - (e.touches[0].clientY - lastY) * 0.008));
    lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
    updateCamera();
  }}
  if (e.touches.length === 2) {{
    const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    radius = Math.max(maxDim * 0.5, Math.min(maxDim * 6, radius - (d - lastTouchDist) * 0.5));
    lastTouchDist = d;
    updateCamera();
  }}
  e.preventDefault();
}}, {{ passive: false }});

// ── CONTROLS ──────────────────────────────────────────────────────────────
let wireframe = false;
function toggleDims() {{
  dimsVisible = !dimsVisible;
  dimObjects.forEach(o => o.visible = dimsVisible);
  document.getElementById('btn-dims').classList.toggle('active', dimsVisible);
}}
function toggleWire() {{
  wireframe = !wireframe;
  mat.wireframe = wireframe;
  document.getElementById('btn-wire').classList.toggle('active', wireframe);
}}
function resetCamera() {{
  theta = 0.6; phi = 0.4; radius = maxDim * 2.5;
  updateCamera();
}}

// ── RENDER LOOP ───────────────────────────────────────────────────────────
function animate() {{
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>"""


def _empty_viewer() -> str:
    return """<div style="width:100%;height:420px;background:#0f1117;display:flex;
    align-items:center;justify-content:center;font-family:monospace;
    color:#2d3748;font-size:13px;letter-spacing:0.1em;">
    NO MODEL LOADED
    </div>"""
