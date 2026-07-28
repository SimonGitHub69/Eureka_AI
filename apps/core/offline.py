"""Sync dati slim per SQLite locale (iPad / offline)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from apps.anagrafiche.models import Cliente
from apps.fatture.models import Fattura
from apps.geografia.models import Provincia, Regione

DEFAULT_YEARS = 5
CHUNK_SIZE = 1500


def default_from_date(oggi: date | None = None) -> date:
    oggi = oggi or timezone.localdate()
    return date(oggi.year - DEFAULT_YEARS, 1, 1)


def parse_from_date(raw: str | None) -> date:
    value = (raw or "").strip()
    if not value:
        return default_from_date()
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return default_from_date()


def offline_meta() -> dict[str, Any]:
    from_date = default_from_date()
    fatture_qs = Fattura.objects.filter(
        data_fattura__isnull=False,
        data_fattura__date__gte=from_date,
    )
    return {
        "from_date": from_date.isoformat(),
        "years": DEFAULT_YEARS,
        "chunk_size": CHUNK_SIZE,
        "counts": {
            "clienti": Cliente.objects.count(),
            "fatture": fatture_qs.count(),
            "regioni": Regione.objects.count(),
            "province": Provincia.objects.count(),
        },
        "synced_at": timezone.now().isoformat(),
    }


def _serialize_cliente(c: Cliente) -> dict[str, Any]:
    return {
        "codice": c.codice,
        "ragione_sociale1": c.ragione_sociale1 or "",
        "ragione_sociale2": c.ragione_sociale2 or "",
        "indirizzo": c.indirizzo or "",
        "localita": c.localita or "",
        "cap": c.cap or "",
        "provincia": (c.provincia or "").strip().upper()[:2],
        "cod_nazione": (c.cod_nazione or "").strip().upper(),
        "partita_iva": c.partita_iva or "",
        "telefono": c.telefono or "",
        "email": c.email or "",
        "cliente_fittizio": 1 if c.cliente_fittizio else 0,
    }


def _serialize_fattura(f: Fattura) -> dict[str, Any]:
    data = f.data_fattura
    if isinstance(data, datetime):
        data_s = data.date().isoformat()
    elif isinstance(data, date):
        data_s = data.isoformat()
    else:
        data_s = ""
    return {
        "id_testa": int(f.id_testa),
        "numero_fatt": int(f.numero_fatt) if f.numero_fatt is not None else None,
        "data_fattura": data_s,
        "cliente": (f.cliente or "").strip(),
        "imponibile": float(f.imponibile or 0),
        "totale_fattura": float(f.totale_fattura or 0),
        "alfa": (f.alfa or "").strip(),
        "tipo_doc_fe": (f.tipo_doc_fe or "").strip(),
        "spese_imballo": float(f.spese_imballo or 0),
        "spese_trasporto": float(f.spese_trasporto or 0),
        "spese_incasso": float(f.spese_incasso or 0),
        "spese_varie": float(f.spese_varie or 0),
        "spese_bolli": float(f.spese_bolli or 0),
        "spese_e15": float(f.spese_e15 or 0),
    }


def chunk_clienti(*, offset: int, limit: int) -> dict[str, Any]:
    qs = Cliente.objects.order_by("codice")
    total = qs.count()
    rows = [_serialize_cliente(c) for c in qs[offset : offset + limit]]
    next_offset = offset + len(rows)
    return {
        "dataset": "clienti",
        "offset": offset,
        "limit": limit,
        "total": total,
        "done": next_offset >= total,
        "next_offset": next_offset if next_offset < total else None,
        "rows": rows,
    }


def chunk_fatture(*, from_date: date, offset: int, limit: int) -> dict[str, Any]:
    qs = (
        Fattura.objects.filter(
            data_fattura__isnull=False,
            data_fattura__date__gte=from_date,
        )
        .order_by("id_testa")
        .only(
            "id_testa",
            "numero_fatt",
            "data_fattura",
            "cliente",
            "imponibile",
            "totale_fattura",
            "alfa",
            "tipo_doc_fe",
            "spese_imballo",
            "spese_trasporto",
            "spese_incasso",
            "spese_varie",
            "spese_bolli",
            "spese_e15",
        )
    )
    total = qs.count()
    rows = [_serialize_fattura(f) for f in qs[offset : offset + limit]]
    next_offset = offset + len(rows)
    return {
        "dataset": "fatture",
        "from_date": from_date.isoformat(),
        "offset": offset,
        "limit": limit,
        "total": total,
        "done": next_offset >= total,
        "next_offset": next_offset if next_offset < total else None,
        "rows": rows,
    }


def chunk_geo() -> dict[str, Any]:
    from apps.fatture.analisi import nomi_nazioni_da_geojson

    regioni = [
        {"codice": r.codice, "nome": r.nome}
        for r in Regione.objects.order_by("codice")
    ]
    province = [
        {
            "sigla": p.sigla,
            "nome": p.nome,
            "regione": p.regione_id,
        }
        for p in Provincia.objects.select_related("regione").order_by("sigla")
    ]
    nazioni = [
        {"codice": iso, "nome": nome}
        for iso, nome in sorted(nomi_nazioni_da_geojson().items())
    ]
    return {
        "dataset": "geo",
        "done": True,
        "regioni": regioni,
        "province": province,
        "nazioni": nazioni,
        "total": len(regioni) + len(province) + len(nazioni),
    }


def sync_chunk_response(request: HttpRequest) -> JsonResponse:
    dataset = (request.GET.get("dataset") or "").strip().lower()
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(request.GET.get("limit") or CHUNK_SIZE)
    except (TypeError, ValueError):
        limit = CHUNK_SIZE
    limit = max(100, min(limit, 3000))

    if dataset == "meta":
        return JsonResponse(offline_meta())
    if dataset == "clienti":
        return JsonResponse(chunk_clienti(offset=offset, limit=limit))
    if dataset == "fatture":
        from_date = parse_from_date(request.GET.get("from"))
        return JsonResponse(
            chunk_fatture(from_date=from_date, offset=offset, limit=limit)
        )
    if dataset == "geo":
        return JsonResponse(chunk_geo())

    return JsonResponse(
        {
            "error": "dataset non valido",
            "allowed": ["meta", "clienti", "fatture", "geo"],
        },
        status=400,
    )
