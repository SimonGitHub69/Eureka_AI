"""
Bridge tra modelli unificati e app fatture (mirror legacy).

Durante la migrazione:
- sync_fatture_4d continua a popolare le tabelle mirror fatture / fatture_dettaglio
- sync_documenti_4d popola teste_documenti / righe_documenti da 4D ODBC (percorso primario)
- Le view fatture restano su Fattura; le nuove view documenti usano TestaDocumento

sync_fatture_mirror_to_unified() permette di allineare i documenti unificati
dalle tabelle mirror già importate (senza connessione ODBC).
Richiede che le tabelle mirror ``fatture`` / ``fatture_dettaglio`` esistano.
"""

from __future__ import annotations

from typing import Sequence

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from apps.core.programma import is_documento_menu_enabled
from apps.documenti.mapping import map_header_row, map_line_row, resolve_fattura_tipo_doc
from apps.documenti.models import RigaDocumento, TestaDocumento
from apps.documenti.sync import (
    FATTURE_TIPI,
    _pg_table_exists,
    _upsert_teste,
    ensure_documenti_tables,
)
from apps.fatture.models import Fattura, FatturaDettaglio


class FattureMirrorUnavailable(Exception):
    """Mirror PostgreSQL fatture assente o non leggibile — bridge non eseguibile."""


_MIRROR_MISSING_MSG = (
    'Bridge mirror fatture saltato: tabelle "fatture" / "fatture_dettaglio" '
    "assenti (usare sync ODBC documenti oppure sincronizzare prima lo step Fatture)."
)


def _fattura_row_dict(fattura: Fattura) -> dict:
    """Converte Fattura mirror → dict stile riga 4D per riuso map_header_row."""
    return {
        "ID_Testa": fattura.id_testa,
        "NumeroFatt": fattura.numero_fatt,
        "DataFattura": fattura.data_fattura,
        "Cliente": fattura.cliente,
        "Destinatario": fattura.destinatario,
        "Indirizzo": fattura.indirizzo,
        "Localita": fattura.localita,
        "Cap": fattura.cap,
        "Prov": fattura.provincia,
        "Nazione": fattura.nazione,
        "CodISO_Dest": fattura.cod_iso_dest,
        "TotaleFattura": fattura.totale_fattura,
        "Imponibile": fattura.imponibile,
        "Alfa": fattura.alfa,
        "DescNotaC": fattura.desc_nota_c,
        "Desc_Causale": fattura.desc_causale,
        "TipoDocFE": fattura.tipo_doc_fe,
        "SpeseImballo": fattura.spese_imballo,
        "SpeseTrasporto": fattura.spese_trasporto,
        "SpeseIncasso": fattura.spese_incasso,
        "SpeseVarie": fattura.spese_varie,
        "SpeseBolli": fattura.spese_bolli,
        "Spese_E15": fattura.spese_e15,
        "ImpSpeseBolloVirtuale": fattura.imp_spese_bollo_virtuale,
        "CodSDI": fattura.cod_sdi,
        "ProgressivoInvio": fattura.progressivo_invio,
        "Email_PEC": fattura.email_pec,
        "FileName": fattura.file_name,
        "IBAN": fattura.iban,
        "CodPagamento": fattura.cod_pagamento,
        "FattPA_CIG": fattura.cig,
        "CUP": fattura.cup,
        "NumOrdineAcq": fattura.num_ordine_acq,
        "DataOrdineAcq": fattura.data_ordine_acq,
    }


def _dettaglio_row_dict(riga: FatturaDettaglio) -> dict:
    return {
        "ID": riga.id,
        "id_added_by_converter": riga.id_testa,
        "ID_Riga": riga.id_riga,
        "NumeroRiga": riga.numero_riga,
        "Codice": riga.codice,
        "DescAgg": riga.descrizione,
        "Quantita": riga.quantita,
        "PrezzoUnitario": riga.prezzo_unitario,
        "Iva": riga.iva,
        "UnitaMisura": riga.unita_misura,
        "Sconto": riga.sconto,
    }


def fatture_mirror_available() -> bool:
    """True se le tabelle mirror fatture esistono su PostgreSQL."""
    try:
        return _pg_table_exists("fatture") and _pg_table_exists("fatture_dettaglio")
    except Exception:
        return False


def _require_fatture_mirror() -> None:
    if not fatture_mirror_available():
        raise FattureMirrorUnavailable(_MIRROR_MISSING_MSG)
    try:
        with transaction.atomic():
            # Probe ORM: convalida che la relazione sia interrogabile.
            Fattura.objects.exists()
    except (ProgrammingError, OperationalError) as exc:
        raise FattureMirrorUnavailable(
            f"Bridge mirror fatture saltato: impossibile leggere le tabelle mirror ({exc})."
        ) from exc


def sync_fatture_mirror_to_unified(
    batch_size: int = 500,
    tipos: Sequence[str] | None = None,
) -> tuple[int, int]:
    """
    Popola teste_documenti / righe_documenti (FAT/NCR/NDB) dalle mirror fatture.
    Ritorna (n_teste, n_righe). Tipi disabilitati in parametri programma sono ignorati.

    Raises:
        FattureMirrorUnavailable: se le tabelle mirror non esistono o non sono leggibili.
    """
    enabled_fatture = tuple(
        t
        for t in FATTURE_TIPI
        if is_documento_menu_enabled(t) and (tipos is None or t in tipos)
    )
    if not enabled_fatture:
        return 0, 0

    _require_fatture_mirror()
    ensure_documenti_tables()
    now = timezone.now()

    try:
        with transaction.atomic():
            teste: list[TestaDocumento] = []
            for fattura in Fattura.objects.iterator(chunk_size=batch_size):
                raw = _fattura_row_dict(fattura)
                tipo = resolve_fattura_tipo_doc(raw)
                if not is_documento_menu_enabled(tipo):
                    continue
                if tipos is not None and tipo not in tipos:
                    continue
                mapped = map_header_row(
                    raw,
                    tipo_doc=tipo,
                    source_table="Fatture",
                    clifor_tipo="C",
                )
                mapped["synced_at"] = now
                teste.append(TestaDocumento(**mapped))
    except (ProgrammingError, OperationalError) as exc:
        raise FattureMirrorUnavailable(
            f"Bridge mirror fatture saltato: impossibile leggere le tabelle mirror ({exc})."
        ) from exc

    n_teste = _upsert_teste(teste)

    testa_lookup = {
        (t, i): pk
        for t, i, pk in TestaDocumento.objects.filter(
            tipo_doc_id__in=enabled_fatture
        ).values_list("tipo_doc_id", "id_4d", "pk")
    }

    righe_by_tipo: dict[str, list[RigaDocumento]] = {t: [] for t in enabled_fatture}
    try:
        with transaction.atomic():
            fatture_tipo = {
                f.id_testa: resolve_fattura_tipo_doc(_fattura_row_dict(f))
                for f in Fattura.objects.only("id_testa", "tipo_doc_fe", "alfa")
            }

            for riga in FatturaDettaglio.objects.iterator(chunk_size=batch_size):
                if riga.id_testa is None:
                    continue
                tipo = fatture_tipo.get(riga.id_testa, "FAT")
                if not is_documento_menu_enabled(tipo):
                    continue
                if tipos is not None and tipo not in tipos:
                    continue
                testa_pk = testa_lookup.get((tipo, riga.id_testa))
                if not testa_pk:
                    continue
                mapped = map_line_row(_dettaglio_row_dict(riga))
                mapped["testa_id"] = testa_pk
                mapped["synced_at"] = now
                righe_by_tipo.setdefault(tipo, []).append(RigaDocumento(**mapped))
    except (ProgrammingError, OperationalError) as exc:
        raise FattureMirrorUnavailable(
            f"Bridge mirror fatture saltato: impossibile leggere le tabelle mirror ({exc})."
        ) from exc

    from apps.documenti.sync import _replace_righe_for_tipo

    n_righe = 0
    for tipo, righe in righe_by_tipo.items():
        if is_documento_menu_enabled(tipo):
            n_righe += _replace_righe_for_tipo(tipo, righe)

    return n_teste, n_righe
