"""Persistenza ordinamento liste (sort/dir) tra navigazione scheda ↔ elenco."""

from __future__ import annotations

SESSION_KEY = "eureka_list_sort"
ALLOWED_DIRS = frozenset({"asc", "desc"})


def get_remembered_sort(request, path: str | None = None) -> tuple[str, str] | None:
    """Restituisce (sort, dir) memorizzati per il path lista, o None."""
    path = path or request.path
    data = (request.session.get(SESSION_KEY) or {}).get(path)
    if not isinstance(data, dict):
        return None
    sort = (data.get("sort") or "").strip()
    if not sort:
        return None
    direction = (data.get("dir") or "").strip().lower()
    if direction not in ALLOWED_DIRS:
        direction = "asc"
    return sort, direction


def remember_sort(
    request,
    sort: str,
    direction: str,
    *,
    path: str | None = None,
) -> None:
    """Salva sort/dir per il path lista nella sessione."""
    sort = (sort or "").strip()
    if not sort:
        return
    direction = (direction or "").strip().lower()
    if direction not in ALLOWED_DIRS:
        direction = "asc"
    path = path or request.path
    store = request.session.setdefault(SESSION_KEY, {})
    store[path] = {"sort": sort, "dir": direction}
    request.session.modified = True
