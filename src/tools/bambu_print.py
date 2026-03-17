"""Send an STL file to a Bambu Lab printer via cloud MQTT.

Requires config/bambu.json with: token, user_id, serial, region.
The STL is converted to a minimal 3MF before upload.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import struct
import tempfile
import threading
import time
import zipfile

logger = logging.getLogger(__name__)

CONFIG_PATH = pathlib.Path("config/bambu.json")

# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

def load_config() -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    return json.loads(CONFIG_PATH.read_text())


# --------------------------------------------------------------------------- #
# STL → 3MF wrapper  (minimal — just wraps the STL mesh in a 3MF envelope)   #
# --------------------------------------------------------------------------- #

_3MF_MODEL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>{vertices}</vertices>
        <triangles>{triangles}</triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1"/>
  </build>
</model>"""


def stl_to_3mf(stl_path: str, out_path: str) -> str:
    """Wrap a binary STL in a .3mf archive. Returns out_path."""
    with open(stl_path, "rb") as f:
        data = f.read()

    dv = memoryview(data)
    n_tri = struct.unpack_from("<I", dv, 80)[0]
    verts, tris = [], []
    off = 84
    v_idx = 0
    for _ in range(n_tri):
        off += 12  # skip normal
        tri_verts = []
        for _ in range(3):
            x, y, z = struct.unpack_from("<fff", dv, off)
            verts.append(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>')
            tri_verts.append(v_idx)
            v_idx += 1
            off += 12
        off += 2  # attr
        tris.append(f'<triangle v1="{tri_verts[0]}" v2="{tri_verts[1]}" v3="{tri_verts[2]}"/>')

    xml = _3MF_MODEL_XML.format(
        vertices="\n        ".join(verts),
        triangles="\n        ".join(tris),
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/model.model"/>'
                   '</Relationships>')
        z.writestr("3D/model.model", xml)
    return out_path


# --------------------------------------------------------------------------- #
# Cloud upload + MQTT print                                                    #
# --------------------------------------------------------------------------- #

def _mqtt_brokers(region: str) -> list[str]:
    if region == "cn":
        return ["cn.mqtt.bambulab.com.cn"]
    return ["us.mqtt.bambulab.com", "eu.mqtt.bambulab.com"]


def send_to_printer(stl_path: str) -> tuple[bool, str]:
    """Convert STL to 3MF and send print job via Bambu cloud MQTT.

    Returns (success, message).
    """
    cfg = load_config()
    if not cfg:
        return False, "Kein Bambu-Token — bitte 'uv run get_bambu_token.py' ausführen."
    if not cfg.get("token"):
        return False, "Token fehlt in config/bambu.json."

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return False, "paho-mqtt nicht installiert — 'uv add paho-mqtt' ausführen."

    token = cfg["token"]
    serial = cfg.get("serial", "")
    user_id = cfg.get("user_id", "")
    region = cfg.get("region", "us")

    if not serial:
        return False, "Seriennummer fehlt in config/bambu.json."

    # Convert STL to 3MF
    with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tmp:
        tmf_path = tmp.name
    try:
        stl_to_3mf(stl_path, tmf_path)
        fname = os.path.basename(stl_path).replace(".stl", ".3mf")

        # Upload 3MF to Bambu cloud storage
        url = _upload_to_cloud(tmf_path, fname, token, region)
        if not url:
            return False, "Upload zur Bambu Cloud fehlgeschlagen."

        # Send print command via MQTT
        ok, msg = _mqtt_print(url, fname, serial, user_id, token, region)
        return ok, msg
    finally:
        try:
            os.unlink(tmf_path)
        except OSError:
            pass


def _upload_to_cloud(path: str, name: str, token: str, region: str) -> str | None:
    """Upload file to Bambu cloud. Returns URL or None."""
    import urllib.request
    base = "https://api.bambulab.com" if region != "cn" else "https://api.bambulab.com.cn"
    # Get upload URL
    req_url = f"{base}/v1/iot-service/api/user/task"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = json.dumps({"name": name}).encode()
    try:
        req = urllib.request.Request(req_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        upload_url = resp.get("presignedUrl") or resp.get("url")
        task_id = resp.get("taskId") or resp.get("id", "")
        if not upload_url:
            logger.error("No upload URL in response: %s", resp)
            return None
        # PUT the 3MF
        with open(path, "rb") as f:
            file_data = f.read()
        put_req = urllib.request.Request(upload_url, data=file_data, method="PUT")
        put_req.add_header("Content-Type", "application/octet-stream")
        with urllib.request.urlopen(put_req, timeout=60):
            pass
        return upload_url.split("?")[0]  # strip query params → public URL
    except Exception as e:
        logger.error("Cloud upload error: %s", e)
        return None


def _mqtt_print(url: str, name: str, serial: str, user_id: str, token: str, region: str) -> tuple[bool, str]:
    """Send print command via Bambu MQTT."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return False, "paho-mqtt fehlt"

    result: dict = {"done": False, "error": None}
    evt = threading.Event()

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            topic = f"device/{serial}/request"
            payload = json.dumps({
                "print": {
                    "sequence_id": "0",
                    "command": "project_file",
                    "param": "Metadata/plate_1.gcode",
                    "url": url,
                    "md5": "",
                    "subtask_name": name,
                    "task_id": "",
                    "profile_id": "",
                    "project_id": "",
                    "use_ams": False,
                    "timelapse": False,
                    "bed_leveling": True,
                    "flow_cali": False,
                    "vibration_cali": True,
                    "layer_inspect": False,
                },
            })
            client.publish(topic, payload)
            result["done"] = True
        else:
            result["error"] = f"MQTT connect rc={rc}"
        evt.set()

    def on_connect_fail(client, userdata):
        result["error"] = "MQTT Verbindung fehlgeschlagen"
        evt.set()

    client = mqtt.Client()
    client.username_pw_set(f"u_{user_id}", token)
    client.tls_set()
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail

    for broker in _mqtt_brokers(region):
        try:
            client.connect(broker, 8883, keepalive=10)
            client.loop_start()
            evt.wait(timeout=15)
            client.loop_stop()
            client.disconnect()
            break
        except Exception as e:
            result["error"] = str(e)
            evt.clear()
            continue

    if result.get("done"):
        return True, f"✅ Druckauftrag gesendet: {name}"
    return False, f"❌ MQTT Fehler: {result.get('error', 'unbekannt')}"
