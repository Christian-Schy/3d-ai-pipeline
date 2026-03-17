"""STL viewer for Gradio — Canvas 2D renderer via iframe srcdoc.

No WebGL required. Works with gr.HTML(value=stl_to_iframe_html(path)).

Usage in app.py:
    from src.ui.stl_viewer_html import stl_to_iframe_html, stl_to_plotly_fig

    viewer = gr.HTML(value="")
    # to update:  gr.update(value=stl_to_iframe_html(stl_path))
"""
from __future__ import annotations
import base64
import os
import struct


# --------------------------------------------------------------------------- #
# Canvas 2D iframe renderer (no WebGL)                                        #
# --------------------------------------------------------------------------- #

_IFRAME_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#1a1f2e; overflow:hidden; }}
  canvas {{ display:block; width:100%; touch-action:none; }}
  #hint {{
    position:fixed; bottom:6px; left:0; right:0;
    text-align:center; color:#4a5568; font-size:.7rem; pointer-events:none;
  }}
  #ph {{
    position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
    color:#4a5568; font-size:.9rem;
  }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="hint" style="display:none">drag = rotate &nbsp;·&nbsp; scroll / pinch = zoom</div>
<div id="ph">No model yet</div>
<script>
(function(){{
  var B64 = "{b64}";
  if (!B64) return;

  document.getElementById('ph').style.display = 'none';
  document.getElementById('hint').style.display = 'block';

  // ── Decode base64 ─────────────────────────────────────────────────────
  function b64ToBytes(s) {{
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }}

  // ── Parse binary STL ──────────────────────────────────────────────────
  function parseSTL(bytes) {{
    var dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    var n = dv.getUint32(80, true), tris = new Array(n), off = 84;
    for (var i = 0; i < n; i++) {{
      var nx=dv.getFloat32(off,true), ny=dv.getFloat32(off+4,true), nz=dv.getFloat32(off+8,true);
      off += 12;
      var v = [];
      for (var j = 0; j < 3; j++) {{
        v.push([dv.getFloat32(off,true), dv.getFloat32(off+4,true), dv.getFloat32(off+8,true)]);
        off += 12;
      }}
      off += 2;
      tris[i] = {{ n:[nx,ny,nz], v:v }};
    }}
    return tris;
  }}

  // ── Center & scale ────────────────────────────────────────────────────
  function centerScale(tris) {{
    var x0=1e9,x1=-1e9,y0=1e9,y1=-1e9,z0=1e9,z1=-1e9;
    for (var t of tris) for (var p of t.v) {{
      if(p[0]<x0)x0=p[0]; if(p[0]>x1)x1=p[0];
      if(p[1]<y0)y0=p[1]; if(p[1]>y1)y1=p[1];
      if(p[2]<z0)z0=p[2]; if(p[2]>z1)z1=p[2];
    }}
    var cx=(x0+x1)/2, cy=(y0+y1)/2, cz=(z0+z1)/2;
    var s = 160 / Math.max(x1-x0, y1-y0, z1-z0, 0.001);
    for (var t of tris)
      t.v = t.v.map(function(p){{return [(p[0]-cx)*s,(p[1]-cy)*s,(p[2]-cz)*s];}});
  }}

  var bytes = b64ToBytes(B64);
  var tris  = parseSTL(bytes);
  centerScale(tris);

  // ── Canvas setup ──────────────────────────────────────────────────────
  var c   = document.getElementById('c');
  var dpr = window.devicePixelRatio || 1;
  var H   = 420;

  function resize() {{
    var W = window.innerWidth || 600;
    c.width  = W * dpr;
    c.height = H * dpr;
    c.style.height = H + 'px';
  }}
  resize();

  var ctx = c.getContext('2d');
  ctx.scale(dpr, dpr);

  // ── Renderer ──────────────────────────────────────────────────────────
  // rotX: tilt up/down  rotY: spin left/right  zoom: scale (orthographic)
  var rotX=-0.5, rotY=0.6, zoom=1.4;
  var drag=false, lx=0, ly=0, pd=0;
  var LX=0.577, LY=0.577, LZ=0.577;

  function rv(v, rx, ry) {{
    var x=v[0],y=v[1],z=v[2];
    // rotate around Y axis (left/right spin)
    var cY=Math.cos(ry),sY=Math.sin(ry),t=x*cY+z*sY; z=-x*sY+z*cY; x=t;
    // rotate around X axis (up/down tilt)
    var cX=Math.cos(rx),sX=Math.sin(rx),u=y*cX-z*sX; z=y*sX+z*cX; y=u;
    return [x,y,z];
  }}
  // Orthographic projection — no perspective limit on zoom
  function proj(v) {{
    var W=c.width/dpr;
    return [W/2+v[0]*zoom, H/2-v[1]*zoom, v[2]];
  }}

  function render() {{
    var W=c.width/dpr;
    ctx.fillStyle='#1a1f2e'; ctx.fillRect(0,0,W,H);
    var vis=[];
    for (var t of tris) {{
      var rv2=t.v.map(function(v){{return rv(v,rotX,rotY);}});
      var ax=rv2[1][0]-rv2[0][0], ay=rv2[1][1]-rv2[0][1];
      var bx=rv2[2][0]-rv2[0][0], by=rv2[2][1]-rv2[0][1];
      if (ax*by-ay*bx < 0) continue;
      var rn=rv(t.n,rotX,rotY);
      var dot=Math.max(0,rn[0]*LX+rn[1]*LY+rn[2]*LZ);
      var sh=25+Math.round(dot*210);
      var p=rv2.map(proj);
      vis.push({{p:p, sh:sh, d:(p[0][2]+p[1][2]+p[2][2])/3}});
    }}
    vis.sort(function(a,b){{return b.d-a.d;}});
    for (var f of vis) {{
      ctx.beginPath();
      ctx.moveTo(f.p[0][0],f.p[0][1]);
      ctx.lineTo(f.p[1][0],f.p[1][1]);
      ctx.lineTo(f.p[2][0],f.p[2][1]);
      ctx.closePath();
      ctx.fillStyle='rgb('+Math.round(f.sh*.35)+','+Math.round(f.sh*.52)+','+f.sh+')';
      ctx.fill();
    }}
  }}
  render();

  // ── Mouse ─────────────────────────────────────────────────────────────
  // drag right → model spins right (rotY+), drag down → model tilts down (rotX-)
  c.onmousedown=function(e){{drag=true;lx=e.clientX;ly=e.clientY;}};
  window.onmouseup=function(){{drag=false;}};
  window.onmousemove=function(e){{
    if(!drag)return;
    rotY+=(e.clientX-lx)*0.010;
    rotX+=(e.clientY-ly)*0.010;
    lx=e.clientX; ly=e.clientY; render();
  }};
  c.addEventListener('wheel',function(e){{
    zoom*=e.deltaY>0?0.90:1.11; render(); e.preventDefault();
  }},{{passive:false}});

  // ── Touch ─────────────────────────────────────────────────────────────
  c.addEventListener('touchstart',function(e){{
    if(e.touches.length===1){{drag=true;lx=e.touches[0].clientX;ly=e.touches[0].clientY;}}
    else if(e.touches.length===2){{
      drag=false;
      var dx=e.touches[0].clientX-e.touches[1].clientX,
          dy=e.touches[0].clientY-e.touches[1].clientY;
      pd=Math.sqrt(dx*dx+dy*dy);
    }}
    e.preventDefault();
  }},{{passive:false}});
  c.addEventListener('touchmove',function(e){{
    if(e.touches.length===1&&drag){{
      rotY+=(e.touches[0].clientX-lx)*0.010;
      rotX+=(e.touches[0].clientY-ly)*0.010;
      lx=e.touches[0].clientX; ly=e.touches[0].clientY; render();
    }} else if(e.touches.length===2&&pd){{
      var dx=e.touches[0].clientX-e.touches[1].clientX,
          dy=e.touches[0].clientY-e.touches[1].clientY;
      var d=Math.sqrt(dx*dx+dy*dy); zoom*=d/pd; pd=d; render();
    }}
    e.preventDefault();
  }},{{passive:false}});
  c.addEventListener('touchend',function(){{drag=false;pd=0;}});
  window.addEventListener('resize',function(){{resize();ctx.scale(dpr,dpr);render();}});
}})();
</script>
</body>
</html>
"""


def stl_to_iframe_html(stl_path: str | None) -> str:
    """Return an <iframe srcdoc="..."> with the Canvas 2D STL renderer embedded.

    Returns "" if the path is invalid (shows empty placeholder).
    """
    if not stl_path or not os.path.exists(stl_path):
        return ""
    with open(stl_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    html = _IFRAME_TEMPLATE.format(b64=b64)
    # Escape quotes for srcdoc attribute
    html_escaped = html.replace("&", "&amp;").replace('"', "&quot;")
    return (
        f'<iframe srcdoc="{html_escaped}" '
        f'style="width:100%;height:420px;border:0;border-radius:8px;overflow:hidden" '
        f'sandbox="allow-scripts"></iframe>'
    )


# --------------------------------------------------------------------------- #
# Plotly Mesh3d renderer (requires WebGL)                                     #
# --------------------------------------------------------------------------- #

def stl_to_plotly_fig(stl_path: str | None):
    """Parse a binary STL file and return a plotly Figure with Mesh3d.

    Returns None if the path is invalid. Requires WebGL in the browser.
    """
    import plotly.graph_objects as go

    if not stl_path or not os.path.exists(stl_path):
        return None

    with open(stl_path, "rb") as f:
        data = f.read()

    dv = memoryview(data)
    n_tri = struct.unpack_from("<I", dv, 80)[0]

    xs, ys, zs = [], [], []
    intensities = []
    LX, LY, LZ = 0.577, 0.577, 0.577

    off = 84
    for _ in range(n_tri):
        nx, ny, nz = struct.unpack_from("<fff", dv, off)
        off += 12
        for _ in range(3):
            x, y, z = struct.unpack_from("<fff", dv, off)
            xs.append(x)
            ys.append(y)
            zs.append(z)
            off += 12
        off += 2
        intensities.append(max(0.0, nx * LX + ny * LY + nz * LZ))

    n = 3 * n_tri
    i_idx = list(range(0, n, 3))
    j_idx = list(range(1, n, 3))
    k_idx = list(range(2, n, 3))

    fig = go.Figure(data=[go.Mesh3d(
        x=xs, y=ys, z=zs,
        i=i_idx, j=j_idx, k=k_idx,
        intensity=intensities,
        intensitymode="cell",
        colorscale=[[0, "rgb(30, 50, 110)"], [1, "rgb(90, 150, 255)"]],
        showscale=False,
        flatshading=True,
        lighting=dict(ambient=0.35, diffuse=0.75, specular=0.2, roughness=0.5),
        lightposition=dict(x=100, y=100, z=100),
    )])

    fig.update_layout(
        scene=dict(
            aspectmode="data",
            bgcolor="#1a1f2e",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
        ),
        paper_bgcolor="#1a1f2e",
        margin=dict(l=0, r=0, t=0, b=0),
        height=420,
    )
    return fig
