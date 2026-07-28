"""Client per l'helper locale Eureka (apri/condividi file su Windows)."""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
_LOCK = threading.Lock()
_LAST_SPAWN = 0.0


def is_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            return True
    except OSError:
        return False


def health_ok() -> bool:
    request = urllib.request.Request(f"http://{HOST}:{PORT}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=0.5) as response:
            data = json.loads(response.read().decode("utf-8"))
            version = int(data.get("version") or 0)
            return bool(data.get("ok")) and bool(data.get("share")) and version >= 4
    except Exception:
        return False


def _kill_helper_on_port() -> None:
    if os.name != "nt":
        return
    ps = (
        f"$p = Get-NetTCPConnection -LocalPort {PORT} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; "
        "foreach ($id in $p) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _spawn_helper() -> None:
    root = Path(__file__).resolve().parents[2]
    helper_script = root / "scripts" / "eureka_open_helper.py"
    if not helper_script.exists():
        return

    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags |= subprocess.DETACHED_PROCESS

    subprocess.Popen(
        [sys.executable, str(helper_script)],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )


def ensure_started(*, force_restart: bool = False) -> None:
    global _LAST_SPAWN
    if os.name != "nt":
        return

    with _LOCK:
        if force_restart:
            _kill_helper_on_port()
            _LAST_SPAWN = 0.0
            time.sleep(0.15)
        elif is_running() and health_ok():
            return
        elif is_running() and not health_ok():
            _kill_helper_on_port()
            _LAST_SPAWN = 0.0
            time.sleep(0.15)

        if is_running() and health_ok():
            return

        now = time.monotonic()
        if now - _LAST_SPAWN < 1.0:
            return
        _LAST_SPAWN = now

        try:
            _spawn_helper()
        except Exception:
            return

        for _ in range(40):
            if is_running() and health_ok():
                return
            time.sleep(0.05)


def friendly_error(message: str) -> str:
    text = (message or "").strip()
    if not text:
        return "Helper locale non disponibile."
    if "<html" in text.lower() or "<!doctype" in text.lower():
        return (
            "Helper locale non aggiornato. Riavvia Django oppure esegui "
            "scripts\\start_eureka_open_helper.ps1"
        )
    text = re.sub(r"\s+", " ", text)
    return text[:240]


def _post_once(path: str, filename: str, content: bytes) -> dict:
    payload = json.dumps(
        {
            "filename": filename,
            "content_b64": base64.b64encode(content).decode("ascii"),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://{HOST}:{PORT}{path}",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(path: str, filename: str, content: bytes) -> dict:
    ensure_started()
    try:
        return _post_once(path, filename, content)
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 501}:
            ensure_started(force_restart=True)
            try:
                return _post_once(path, filename, content)
            except Exception as retry_exc:
                raise RuntimeError(friendly_error(str(retry_exc))) from retry_exc
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(detail)
            message = data.get("error") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise RuntimeError(friendly_error(message)) from exc
    except urllib.error.URLError as exc:
        ensure_started(force_restart=True)
        try:
            return _post_once(path, filename, content)
        except Exception as retry_exc:
            raise RuntimeError(
                friendly_error(
                    "Helper locale non disponibile. Riavvia Django o esegui "
                    "scripts\\start_eureka_open_helper.ps1"
                )
            ) from retry_exc
    except Exception as exc:
        raise RuntimeError(friendly_error(str(exc))) from exc


def open_file(filename: str, content: bytes) -> dict:
    return _post("/open", filename, content)


def share_file(filename: str, content: bytes) -> dict:
    return _post("/share", filename, content)
