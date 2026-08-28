"""PDF della stampa documento (Chrome/Edge headless)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.template.loader import render_to_string

from apps.documenti.mail_documento import _txt, documento_mail_title
from apps.documenti.print_documento import build_documento_print_context


def pdf_filename_for(documento) -> str:
    title = documento_mail_title(documento).replace(" ", "_")
    num = _txt(getattr(documento, "numero_documento", None)).replace("/", "-") or "doc"
    safe = "".join(ch for ch in f"{title}_{num}" if ch.isalnum() or ch in "._-")
    return f"{safe or 'documento'}.pdf"


def _chrome_executable() -> str | None:
    env = os.environ.get("EUREKA_CHROME") or os.environ.get("CHROME_PATH") or ""
    candidates = [
        env,
        shutil.which("msedge") or "",
        shutil.which("chrome") or "",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        os.path.join(
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            r"Microsoft\Edge\Application\msedge.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            r"Microsoft\Edge\Application\msedge.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            r"Google\Chrome\Application\chrome.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            r"Google\Chrome\Application\chrome.exe",
        ),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            r"Google\Chrome\Application\chrome.exe",
        ),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _print_css_text() -> str:
    found = find("eureka/css/documento-print.css")
    if found:
        return Path(found).read_text(encoding="utf-8")
    fallback = Path(settings.BASE_DIR) / "static" / "eureka" / "css" / "documento-print.css"
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8")
    return ""


def _url_to_file_uri(url: str) -> str:
    raw = (url or "").strip()
    if not raw or raw.startswith("file:"):
        return raw
    media_url = settings.MEDIA_URL or "/media/"
    if raw.startswith(media_url):
        rel = raw[len(media_url) :].lstrip("/")
        path = Path(settings.MEDIA_ROOT) / rel
        if path.is_file():
            return path.resolve().as_uri()
    static_url = settings.STATIC_URL or "/static/"
    if raw.startswith(static_url):
        rel = raw[len(static_url) :].lstrip("/")
        found = find(rel)
        if found:
            return Path(found).resolve().as_uri()
    return raw


def render_documento_print_html(documento) -> str:
    ctx = build_documento_print_context(documento, autoprint=False)
    logo = _url_to_file_uri(ctx.get("print_azienda_logo_url") or "")
    if logo:
        ctx["print_azienda_logo_url"] = logo
    ctx["pdf_mode"] = True
    ctx["print_css_inline"] = _print_css_text()
    return render_to_string("documenti/documento_print.html", ctx)


def render_documento_pdf(documento) -> bytes:
    """Genera il PDF della stampa. Solleva RuntimeError se Chrome/Edge manca."""
    chrome = _chrome_executable()
    if not chrome:
        raise RuntimeError(
            "Impossibile creare il PDF di stampa: Chrome o Microsoft Edge non trovati."
        )

    html = render_documento_print_html(documento)
    with tempfile.TemporaryDirectory(prefix="eureka-doc-pdf-") as tmp:
        tmp_path = Path(tmp)
        html_path = tmp_path / "documento.html"
        pdf_path = tmp_path / "documento.pdf"
        profile = tmp_path / "profile"
        profile.mkdir()
        html_path.write_text(html, encoding="utf-8")
        uri = html_path.resolve().as_uri()
        base_cmd = [
            chrome,
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=8000",
            f"--print-to-pdf={pdf_path}",
            uri,
        ]
        last_err = b""
        for headless in ("--headless=new", "--headless"):
            try:
                completed = subprocess.run(
                    [chrome, headless, *base_cmd[1:]],
                    check=True,
                    timeout=45,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                last_err = completed.stderr or b""
                break
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "Impossibile creare il PDF di stampa: Chrome o Microsoft Edge non trovati."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "Timeout durante la generazione del PDF di stampa."
                ) from exc
            except subprocess.CalledProcessError as exc:
                last_err = exc.stderr or b""
                continue
        else:
            err = last_err.decode("utf-8", errors="ignore")[:400]
            raise RuntimeError(
                f"Generazione PDF di stampa non riuscita. {err}".strip()
            )
        if not pdf_path.is_file() or pdf_path.stat().st_size < 8:
            raise RuntimeError("Il PDF di stampa è vuoto o non è stato creato.")
        data = pdf_path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise RuntimeError("Il file generato non è un PDF valido.")
    return data
