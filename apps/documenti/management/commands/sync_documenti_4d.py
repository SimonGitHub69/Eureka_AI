from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.programma import get_tipi_documento_abilitati, is_documento_menu_enabled
from apps.core.sync_incremental import add_sync_mode_arguments, sync_full_from_options
from apps.documenti.bridge import (
    FattureMirrorUnavailable,
    sync_fatture_mirror_to_unified,
)
from apps.documenti.mapping import DEFAULT_TIPI_DOCUMENTO
from apps.documenti.models import SyncDocumentiLog, TipoDocumento
from apps.documenti.sync import FATTURE_TIPI, parse_only_selection, sync_documenti


class Command(BaseCommand):
    help = (
        "Importa documenti 4D nelle tabelle unificate teste_documenti / righe_documenti. "
        "Sorgenti: Ordini_Vendita, Ordini_Acquisto, Preventivi, Bolle, Fatture (+ dettagli). "
        "Tipi disabilitati in Parametri programma vengono ignorati."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Righe lette/scritte per batch ODBC (default 5000).",
        )
        parser.add_argument(
            "--only",
            action="append",
            default=[],
            help=(
                "Limita sync a uno o più tipi/tabelle (ripetibile o elenco separato da virgola). "
                "Esempi: --only ORV --only PRV oppure --only ORV,PRV,DDT. "
                "Valori: TipoDoc (ORV, FAT), tabella 4D (Ordini_Vendita, Fatture). "
                "Rispetta i flag parametri programma."
            ),
        )
        parser.add_argument(
            "--from-fatture-mirror",
            action="store_true",
            help="Popola FAT/NCR/NDB dalle tabelle mirror fatture (senza ODBC).",
        )
        parser.add_argument(
            "--seed-tipi",
            action="store_true",
            help="Crea/aggiorna i record TipoDocumento predefiniti.",
        )
        add_sync_mode_arguments(parser)

    def handle(self, *args, **options):
        only_tokens = parse_only_selection(options.get("only") or [])
        if options["seed_tipi"]:
            self._seed_tipi()
            if not options.get("from_fatture_mirror") and not only_tokens:
                self.stdout.write(self.style.SUCCESS("Tipi documento aggiornati."))
                return

        batch_size = options["batch_size"]
        only = only_tokens
        full = sync_full_from_options(options)

        if options["from_fatture_mirror"]:
            disabled = [t for t in FATTURE_TIPI if not is_documento_menu_enabled(t)]
            for tipo in disabled:
                self.stdout.write(
                    self.style.WARNING(
                        f"Tipo {tipo} disabilitato in parametri programma — ignorato."
                    )
                )
            if not any(is_documento_menu_enabled(t) for t in FATTURE_TIPI):
                self.stdout.write(
                    self.style.WARNING(
                        "Nessun tipo fattura abilitato (FAT/NCR/NDB) — bridge non eseguito."
                    )
                )
                return

            enabled = ", ".join(t for t in FATTURE_TIPI if is_documento_menu_enabled(t))
            self.stdout.write(
                f"Bridge mirror fatture -> documenti unificati ({enabled})..."
            )
            try:
                n_teste, n_righe = sync_fatture_mirror_to_unified(
                    batch_size=batch_size
                )
            except FattureMirrorUnavailable as exc:
                self.stdout.write(self.style.WARNING(str(exc)))
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"Bridge completato: {n_teste} testate, {n_righe} righe."
                )
            )
            return

        abilitati = get_tipi_documento_abilitati()
        if abilitati:
            self.stdout.write(
                f"Tipi abilitati in parametri programma: {', '.join(abilitati)}"
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Nessun tipo documento abilitato in parametri programma."
                )
            )

        if only_tokens:
            self.stdout.write(f"Sync limitato a: {', '.join(only_tokens)}")

        log = SyncDocumentiLog.objects.create(message="Sync in corso...")
        self.stdout.write(self.style.WARNING("Avvio sync documenti 4D -> PostgreSQL..."))

        result = sync_documenti(batch_size=batch_size, only=only, full=full)

        log.ok = result.ok
        log.teste_count = result.teste_count
        log.righe_count = result.righe_count
        log.message = "\n".join(t.message for t in result.tables) or result.message
        log.finished_at = timezone.now()
        log.save()

        for table in result.tables:
            if "disabilitato" in table.message:
                style = self.style.WARNING
            elif table.ok:
                style = self.style.SUCCESS
            else:
                style = self.style.ERROR
            self.stdout.write(style(table.message))

        if result.ok:
            self.stdout.write(self.style.SUCCESS(result.message))
        else:
            self.stderr.write(self.style.ERROR(result.message))
            raise SystemExit(1)

    def _seed_tipi(self):
        from apps.documenti.mapping import tipo_documento_seed_defaults

        for spec in DEFAULT_TIPI_DOCUMENTO:
            TipoDocumento.objects.update_or_create(
                codice=spec["codice"],
                defaults=tipo_documento_seed_defaults(spec),
            )
