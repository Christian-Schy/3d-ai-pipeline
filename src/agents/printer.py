"""
src/agents/printer.py — Slices STL and sends to Bambu P1S via Cloud.

Flow:
  STL → OrcaSlicer CLI (--slice --export-3mf) → .3mf → Bambu Cloud MQTT → Drucker

Config (config.yaml):
  bambu:
    serial:       "01P00A..."   # Seriennummer (Aufkleber hinten am Drucker)
    access_code:  "12345678"    # Access Code (Bambu App → Drucker → ...)
    region:       "eu"          # eu / us / cn
    orca_path:    "~/OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.3.1.AppImage"
    printer_profile: "Bambu Lab P1S 0.4 nozzle"
    filament_profile: "Bambu PLA Basic @BBL P1S"
    ams_slot:     1             # 1-4, oder 0 für externes Filament

Usage:
    agent = PrinterAgent()
    result = agent.print(stl_path="/tmp/model.stl")
    # → {"success": True, "job_id": "...", "message": "..."}
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import structlog
from pathlib import Path

log = structlog.get_logger()


class PrinterAgent:
    """Orchestrates STL → slice → print on Bambu P1S.

    Two separate responsibilities:
      1. Slicing:  OrcaSlicer CLI converts STL → .3mf with print settings
      2. Sending:  Bambu Cloud MQTT triggers the print job on the printer
    """

    def __init__(self):
        from src.config.loader import get_config
        cfg = get_config()
        self.cfg = cfg.bambu
        self.log = structlog.get_logger().bind(agent="printer")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def print(self, stl_path: str, task_name: str = None) -> dict:
        """Slice STL and send to printer.

        Args:
            stl_path:   Absolute path to the STL file.
            task_name:  Optional job name shown on printer display.

        Returns:
            {"success": bool, "message": str, "3mf_path": str (if sliced)}
        """
        if not Path(stl_path).exists():
            return {"success": False, "message": f"STL not found: {stl_path}"}

        task_name = task_name or Path(stl_path).stem

        # Step 1: Slice
        self.log.info("printer_slice_start", stl=stl_path)
        slice_result = self._slice(stl_path)
        if not slice_result["success"]:
            return slice_result

        tmf_path = slice_result["3mf_path"]
        self.log.info("printer_slice_done", tmf=tmf_path)

        # Step 2: Send to printer
        self.log.info("printer_send_start", tmf=tmf_path)
        send_result = self._send(tmf_path, task_name)

        return {**send_result, "3mf_path": tmf_path}

    # ------------------------------------------------------------------
    # Step 1: OrcaSlicer CLI
    # ------------------------------------------------------------------

    def _slice(self, stl_path: str) -> dict:
        """Run OrcaSlicer CLI to convert STL → .3mf with print settings."""
        orca = Path(self.cfg.orca_path).expanduser()
        if not orca.exists():
            return {
                "success": False,
                "message": f"OrcaSlicer not found at {orca}\n"
                           "Set bambu.orca_path in config.yaml"
            }

        # Output dir — same folder as STL
        output_dir = Path(stl_path).parent
        tmf_path = output_dir / (Path(stl_path).stem + ".3mf")

        # Build profile files for CLI
        # OrcaSlicer CLI needs JSON config files for printer + filament.
        # We use the built-in profiles by name via --load-settings workaround:
        # Actually OrcaSlicer CLI accepts profile names directly via env + datadir.
        # Simplest approach: use --load-filaments and --load-settings with
        # the profiles that ship with OrcaSlicer.
        cmd = [
            str(orca),
            "--slice", "0",                         # slice all plates
            "--export-3mf", str(tmf_path),
            "--outputdir", str(output_dir),
            stl_path,
        ]

        self.log.info("orca_cli", cmd=" ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                self.log.error("orca_cli_failed",
                               stdout=result.stdout[-500:],
                               stderr=result.stderr[-500:])
                return {
                    "success": False,
                    "message": f"OrcaSlicer failed (code {result.returncode}):\n"
                               f"{result.stderr[-300:]}"
                }

            if not tmf_path.exists():
                return {
                    "success": False,
                    "message": "OrcaSlicer ran but no .3mf was created.\n"
                               "Check that the printer profile is correct."
                }

            return {"success": True, "3mf_path": str(tmf_path)}

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "OrcaSlicer timed out after 120s"}
        except Exception as e:
            return {"success": False, "message": f"OrcaSlicer error: {e}"}

    # ------------------------------------------------------------------
    # Step 2: Bambu Cloud MQTT
    # ------------------------------------------------------------------

    def _send(self, tmf_path: str, task_name: str) -> dict:
        """Upload .3mf and trigger print via Bambu Cloud MQTT.

        Bambu Cloud flow:
          1. Upload .3mf to Bambu's file storage (via HTTPS)
          2. Send MQTT message to printer: "start print job X"

        Uses bambulabs_api (pip install bambulabs-api) which wraps
        the unofficial Bambu Cloud API.
        """
        try:
            import bambulabs_api as bl
        except ImportError:
            return {
                "success": False,
                "message": "bambulabs_api not installed.\nRun: uv add bambulabs-api"
            }

        try:
            # Connect to printer via cloud
            printer = bl.Printer(
                serial=self.cfg.serial,
                access_code=self.cfg.access_code,
                ip=None,          # Cloud mode — no direct IP needed
                region=getattr(self.cfg, "region", "eu"),
            )
            printer.start()
            time.sleep(2)  # Wait for MQTT connection

            self.log.info("bambu_connected", serial=self.cfg.serial[:8] + "...")

            # Upload and print
            result = printer.print_3mf(
                filepath=tmf_path,
                plate_id=1,
                use_ams=getattr(self.cfg, "ams_slot", 1) > 0,
                ams_mapping=[getattr(self.cfg, "ams_slot", 1) - 1],
                task_name=task_name,
            )

            printer.stop()

            if result:
                self.log.info("bambu_print_sent", task=task_name)
                return {
                    "success": True,
                    "message": f"✓ Druckauftrag gesendet: {task_name}"
                }
            else:
                return {
                    "success": False,
                    "message": "Bambu API: Druckauftrag konnte nicht gesendet werden."
                }

        except Exception as e:
            self.log.error("bambu_send_failed", error=str(e))
            return {
                "success": False,
                "message": f"Bambu Cloud Fehler: {e}\n"
                           "Prüfe serial, access_code und region in config.yaml"
            }
