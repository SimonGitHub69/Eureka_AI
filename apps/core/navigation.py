"""Navigazione «Torna a…» tramite query ``next`` (solo path interni)."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def safe_internal_path(raw: str, *, host: str) -> str | None:
    """Accetta solo path relativi (o URL stesso host)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.netloc and parsed.netloc != host:
            return None
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
    else:
        path = raw
    if path.startswith("/") and not path.startswith("//"):
        return path
    return None


def next_from_request(request) -> str | None:
    raw = (
        (request.POST.get("next") if getattr(request, "method", "") == "POST" else None)
        or (request.GET.get("next") or "")
    ).strip()
    return safe_internal_path(raw, host=request.get_host())


def related_back(request) -> tuple[str | None, str]:
    """Se ``next`` punta a una maschera nota, restituisce (url, label)."""
    path = next_from_request(request)
    if not path:
        return None, ""
    lower = path.lower()
    if "/primanota/" in lower:
        return path, "Torna alla registrazione"
    if re.search(r"/movimenti/\d+", lower):
        return path, "Torna al movimento"
    if re.search(r"/articoli/[^/?#]+", lower):
        if "#" not in path:
            path = f"{path}#articolo-movimenti"
        return path, "Torna ai movimenti"
    return None, ""


def back_to_primanota(request) -> tuple[str | None, str]:
    """Compat: solo se ``next`` punta a Primanota."""
    path = next_from_request(request)
    if not path or "/primanota/" not in path.lower():
        return None, ""
    return path, "Torna alla registrazione"


def back_to_movimento(request) -> tuple[str | None, str]:
    """Compat: solo se ``next`` punta a un movimento magazzino."""
    path = next_from_request(request)
    if not path or not re.search(r"/movimenti/\d+", path.lower()):
        return None, ""
    return path, "Torna al movimento"
