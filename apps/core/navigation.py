"""Navigazione «Torna a…» tramite query ``next`` (solo path interni)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from apps.core.pagination import LIST_COUNT_EXCLUDE_GET


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


_BACK_QUERY_EXCLUDE = LIST_COUNT_EXCLUDE_GET | frozenset(
    {
        "next",
        "list_back",
        "from",
        "distinta_back",
    }
)


def _path_has_list_filters(path: str) -> bool:
    """True se l'URL di elenco contiene filtri/ricerca oltre paginazione e ordinamento."""
    query = urlparse(path).query
    if not query:
        return False
    params = parse_qs(query, keep_blank_values=True)
    if params.get("ai") == ["1"]:
        return True
    for key, values in params.items():
        if key in _BACK_QUERY_EXCLUDE:
            continue
        if any(str(value or "").strip() for value in values):
            return True
    return False


def _resolve_back_path(request) -> str | None:
    path = next_from_request(request)
    if path:
        return path
    raw = unquote((request.GET.get("list_back") or "").strip())
    if not raw:
        return None
    return safe_internal_path(raw, host=request.get_host())


def list_back_label(path: str) -> str:
    return "Torna alla selezione" if _path_has_list_filters(path) else "Torna all'elenco"


def related_back(request) -> tuple[str | None, str]:
    """Restituisce (url, label) per tornare all'elenco o alla maschera correlata."""
    path = _resolve_back_path(request)
    if not path:
        return None, ""
    lower = path.lower()
    if "/partitario" in lower:
        return path, "Torna al partitario"
    if re.search(r"/primanota/\d+", lower):
        return path, "Torna alla registrazione"
    if re.search(r"/movimenti/\d+", lower):
        return path, "Torna al movimento"
    if re.search(r"/articoli/[^/?#]+", lower):
        if "#" not in path:
            path = f"{path}#articolo-movimenti"
        return path, "Torna ai movimenti"
    return path, list_back_label(path)


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
