"""Carica regioni, province e città da data/comuni.json (fonte ISTAT / comuni-json)."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.geografia.models import Citta, Provincia, Regione

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "comuni.json"


class Command(BaseCommand):
    help = "Carica/aggiorna geografia Italia (regioni, province, città) da comuni.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=str(DATA_FILE),
            help="Percorso al file JSON comuni",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Svuota le tabelle geografia prima del caricamento",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"File non trovato: {path}")

        with path.open(encoding="utf-8") as fh:
            comuni = json.load(fh)

        if not isinstance(comuni, list) or not comuni:
            raise CommandError("JSON non valido: attesa lista di comuni")

        with transaction.atomic():
            if options["purge"]:
                Citta.objects.all().delete()
                Provincia.objects.all().delete()
                Regione.objects.all().delete()
                self.stdout.write("Tabelle geografia svuotate.")

            regioni: dict[str, Regione] = {}
            province: dict[str, Provincia] = {}
            citta_rows: list[Citta] = []

            for item in comuni:
                reg = item.get("regione") or {}
                prov = item.get("provincia") or {}
                reg_cod = str(reg.get("codice") or "").zfill(2)[-2:]
                reg_nome = (reg.get("nome") or "").strip()
                prov_cod = str(prov.get("codice") or "").zfill(3)[-3:]
                prov_nome = (prov.get("nome") or "").strip()
                sigla = (item.get("sigla") or "").strip().upper()
                citta_cod = str(item.get("codice") or "").strip()
                citta_nome = (item.get("nome") or "").strip()
                caps = item.get("cap") or []
                cap = ""
                if isinstance(caps, list) and caps:
                    cap = str(caps[0]).strip()[:5]
                elif isinstance(caps, str):
                    cap = caps.strip()[:5]
                catastale = (item.get("codiceCatastale") or "").strip().upper()[:4]

                if not (reg_cod and reg_nome and sigla and prov_cod and citta_cod and citta_nome):
                    continue

                if reg_cod not in regioni:
                    regioni[reg_cod] = Regione(codice=reg_cod, nome=reg_nome)

                if sigla not in province:
                    province[sigla] = Provincia(
                        sigla=sigla,
                        codice_istat=prov_cod,
                        nome=prov_nome,
                        regione_id=reg_cod,
                    )

                citta_rows.append(
                    Citta(
                        codice_istat=citta_cod,
                        nome=citta_nome,
                        provincia_id=sigla,
                        cap=cap,
                        codice_catastale=catastale,
                    )
                )

            Regione.objects.bulk_create(
                list(regioni.values()),
                update_conflicts=True,
                unique_fields=["codice"],
                update_fields=["nome"],
            )
            Provincia.objects.bulk_create(
                list(province.values()),
                update_conflicts=True,
                unique_fields=["sigla"],
                update_fields=["codice_istat", "nome", "regione_id"],
            )
            # bulk_create update_conflicts for Citta in batches
            batch = 1000
            for i in range(0, len(citta_rows), batch):
                Citta.objects.bulk_create(
                    citta_rows[i : i + batch],
                    update_conflicts=True,
                    unique_fields=["codice_istat"],
                    update_fields=["nome", "provincia_id", "cap", "codice_catastale"],
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Caricate {Regione.objects.count()} regioni, "
                f"{Provincia.objects.count()} province, "
                f"{Citta.objects.count()} città."
            )
        )
