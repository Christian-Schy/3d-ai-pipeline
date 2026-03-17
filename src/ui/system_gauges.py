"""src/ui/system_gauges.py — Live GPU & RAM vertical bar gauges for Gradio.

Returns an HTML string with two vertical bars (GPU util + RAM used).
Updated via gr.Timer every N seconds.
"""
from __future__ import annotations
import subprocess


def _get_stats() -> tuple[int, int, int, int]:
    """Return (gpu_pct, vram_used_mb, vram_total_mb, ram_pct).

    GPU via nvidia-smi, RAM via psutil. Falls back to 0 on error.
    """
    import psutil

    # RAM
    vm = psutil.virtual_memory()
    ram_pct = int(vm.percent)

    # GPU
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=2,
        ).decode().strip().split(",")
        gpu_pct      = int(out[0].strip())
        vram_used_mb = int(out[1].strip())
        vram_total_mb = int(out[2].strip())
    except Exception:
        gpu_pct = vram_used_mb = vram_total_mb = 0

    return gpu_pct, vram_used_mb, vram_total_mb, ram_pct


def _color(pct: int) -> str:
    if pct >= 90:
        return "#e53e3e"   # red
    if pct >= 70:
        return "#ed8936"   # orange
    return "#48bb78"       # green


def build_gauges_html() -> str:
    gpu_pct, vram_used, vram_total, ram_pct = _get_stats()
    vram_pct = int(vram_used / vram_total * 100) if vram_total else 0

    def bar(label: str, pct: int, sub: str) -> str:
        col = _color(pct)
        filled = max(2, pct)
        return f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:3px">
          <span style="font-size:.6rem;color:#a0aec0">{label}</span>
          <div style="width:16px;height:120px;border:1px solid #4a5568;border-radius:5px;
                      overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end">
            <div style="width:100%;height:{filled}%;background:{col};transition:height .5s ease"></div>
          </div>
          <span style="font-size:.65rem;color:#e2e8f0;font-weight:600">{pct}%</span>
          <span style="font-size:.55rem;color:#718096;text-align:center;line-height:1.2;max-width:36px">{sub}</span>
        </div>"""

    vram_sub = f"{vram_used//1024:.1f}/{vram_total//1024:.0f}G" if vram_total else "N/A"
    import psutil
    vm = psutil.virtual_memory()
    ram_sub = f"{vm.used//1024**3:.1f}/{vm.total//1024**3:.0f}G"

    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:6px 2px">
      {bar("GPU", gpu_pct, "util")}
      {bar("VRAM", vram_pct, vram_sub)}
      {bar("RAM", ram_pct, ram_sub)}
    </div>"""
