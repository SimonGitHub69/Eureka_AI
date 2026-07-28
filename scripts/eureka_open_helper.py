from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
TMP_DIR = Path(tempfile.gettempdir()) / "eureka-open"
TMP_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR = Path(__file__).resolve().parent
HELPER_VERSION = 5


def save_export_payload(data: dict) -> Path:
    filename = os.path.basename((data.get("filename") or "export.bin").strip())
    content_b64 = data.get("content_b64") or ""
    payload = base64.b64decode(content_b64)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = TMP_DIR / f"{stamp}-{filename}"
    target.write_bytes(payload)
    return target


def open_with_default_app(path: Path) -> None:
    os.startfile(str(path))


def _eureka_share_exe() -> Path | None:
    candidates = [
        SCRIPTS_DIR / "EurekaShare.exe",
        SCRIPTS_DIR / "share_publish" / "EurekaShare.exe",
        SCRIPTS_DIR / "eureka_share_net" / "bin" / "Release" / "net8.0-windows10.0.19041.0" / "win-x64" / "EurekaShare.exe",
        SCRIPTS_DIR / "eureka_share_net" / "bin" / "Release" / "net8.0-windows10.0.19041.0" / "EurekaShare.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _ensure_eureka_share_built() -> Path:
    existing = _eureka_share_exe()
    if existing is not None:
        return existing

    csproj = SCRIPTS_DIR / "eureka_share_net" / "EurekaShareNet.csproj"
    out_dir = SCRIPTS_DIR / "share_publish"
    if not csproj.exists():
        raise RuntimeError("Progetto EurekaShare non trovato")

    completed = subprocess.run(
        [
            "dotnet",
            "publish",
            str(csproj),
            "-c",
            "Release",
            "-r",
            "win-x64",
            "--self-contained",
            "false",
            "-p:PublishSingleFile=true",
            "-o",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Compilazione EurekaShare fallita. "
            + ((completed.stderr or completed.stdout or "")[-400:])
        )
    exe = out_dir / "EurekaShare.exe"
    if not exe.exists():
        raise RuntimeError("EurekaShare.exe non generato")
    return exe


def share_with_system(path: Path) -> None:
    if os.name != "nt":
        open_with_default_app(path)
        return

    exe = _ensure_eureka_share_built()

    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [str(exe), str(path)],
        cwd=str(exe.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    time.sleep(0.8)
    code = proc.poll()
    if code not in (None, 0):
        log = Path(tempfile.gettempdir()) / "eureka-share-log.txt"
        detail = ""
        if log.exists():
            detail = log.read_text(encoding="utf-8", errors="replace")[-500:]
        raise RuntimeError(detail or f"EurekaShare.exe terminato con codice {code}")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._json_response(
                200,
                {
                    "ok": True,
                    "share": True,
                    "version": HELPER_VERSION,
                    "eureka_share": bool(_eureka_share_exe()),
                },
            )
            return
        self.send_error(404)

    def do_POST(self):
        if self.path not in {"/open", "/share"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            target = save_export_payload(data)
            if self.path == "/open":
                open_with_default_app(target)
            else:
                share_with_system(target)
            self._json_response(200, {"ok": True, "path": str(target)})
        except Exception as exc:
            self._json_response(500, {"ok": False, "error": str(exc)})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Eureka open helper listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
