from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


MIDNIGHT = time(0, 0)


@dataclass
class MovimentoPresenza:
    label: str
    ingresso: time | None
    uscita: time | None
    ingresso_originale: time | None
    uscita_originale: time | None
    rettificato: bool
    minuti: int

    @property
    def ore_decimali(self) -> float:
        return round(self.minuti / 60, 2)

    @property
    def attivo(self) -> bool:
        return self.ingresso is not None or self.uscita is not None

    @property
    def ingresso_label(self) -> str:
        return format_time(self.ingresso)

    @property
    def uscita_label(self) -> str:
        return format_time(self.uscita)

    @property
    def intervallo_label(self) -> str:
        if not self.attivo:
            return "—"
        return f"{self.ingresso_label} → {self.uscita_label}"


@dataclass
class PresenzaGiornaliera:
    id: int
    cod_operatore: str
    operatore_nome: str
    reparto: str
    data: date
    movimenti: list[MovimentoPresenza]
    note: str
    scheda_validata: bool | None
    minuti_totali: int

    @property
    def ore_totali(self) -> float:
        return round(self.minuti_totali / 60, 2)

    @property
    def ore_totali_label(self) -> str:
        ore = self.minuti_totali // 60
        minuti = self.minuti_totali % 60
        if minuti:
            return f"{ore}h {minuti:02d}m"
        return f"{ore}h"


TURNI = (
    ("Mattina", "E1_Ora", "U1_Ora", "E1_Ora_Rett", "U1_Ora_Rett"),
    ("Pomeriggio", "E2_Ora", "U2_Ora", "E2_Ora_Rett", "U2_Ora_Rett"),
    ("Serale", "E3_Ora", "U3_Ora", "E3_Ora_Rett", "U3_Ora_Rett"),
)


def _is_set(value: time | None) -> bool:
    return value is not None and value != MIDNIGHT


def effective_time(raw: time | None, rett: time | None) -> time | None:
    if _is_set(rett):
        return rett
    if _is_set(raw):
        return raw
    return None


def pair_minutes(ingresso: time | None, uscita: time | None) -> int:
    if not ingresso or not uscita or uscita <= ingresso:
        return 0
    base = datetime.combine(date.min, ingresso)
    end = datetime.combine(date.min, uscita)
    return int((end - base).total_seconds() // 60)


def format_time(value: time | None) -> str:
    if not value:
        return "—"
    return value.strftime("%H:%M")


def parse_presenza_row(row: dict) -> PresenzaGiornaliera:
    movimenti: list[MovimentoPresenza] = []
    minuti_totali = 0

    for label, e_key, u_key, e_rett_key, u_rett_key in TURNI:
        raw_e = row.get(e_key)
        raw_u = row.get(u_key)
        rett_e = row.get(e_rett_key)
        rett_u = row.get(u_rett_key)
        ingresso = effective_time(raw_e, rett_e)
        uscita = effective_time(raw_u, rett_u)
        rettificato = (
            (_is_set(rett_e) and rett_e != raw_e)
            or (_is_set(rett_u) and rett_u != raw_u)
        )
        minuti = pair_minutes(ingresso, uscita)
        minuti_totali += minuti
        movimenti.append(
            MovimentoPresenza(
                label=label,
                ingresso=ingresso,
                uscita=uscita,
                ingresso_originale=raw_e if _is_set(raw_e) else None,
                uscita_originale=raw_u if _is_set(raw_u) else None,
                rettificato=rettificato,
                minuti=minuti,
            )
        )

    data_value = row.get("Data")
    if isinstance(data_value, datetime):
        data_giorno = data_value.date()
    elif isinstance(data_value, date):
        data_giorno = data_value
    else:
        data_giorno = date.today()

    return PresenzaGiornaliera(
        id=int(row["ID"]),
        cod_operatore=str(row.get("Cod_Operatore") or ""),
        operatore_nome=str(row.get("operatore_nome") or row.get("Cod_Operatore") or ""),
        reparto=str(row.get("reparto") or ""),
        data=data_giorno,
        movimenti=movimenti,
        note=str(row.get("Note") or "").strip(),
        scheda_validata=row.get("Scheda_Validata"),
        minuti_totali=minuti_totali,
    )


def default_period() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    return start, today


def period_from_request(data_da: str, data_a: str) -> tuple[date, date]:
    start, end = default_period()
    for value, target in ((data_da, "start"), (data_a, "end")):
        if not value:
            continue
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            continue
        if target == "start":
            start = parsed
        else:
            end = parsed
    if start > end:
        start, end = end, start
    return start, end
