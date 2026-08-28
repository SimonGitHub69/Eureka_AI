from django.core.management.base import BaseCommand

from apps.core.sync_incremental import add_sync_mode_arguments, sync_full_from_options
from apps.causali_trasp.sync import sync_causali_trasp


class Command(BaseCommand):
    help = "Importa la tabella 4D CausaliTrasp in PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="Righe lette/scritte per batch (default 2000).",
        )
        parser.add_argument(
            "--only",
            type=str,
            default="",
            help="Sincronizza solo CausaliTrasp/causali_trasp (source/target name).",
        )
        add_sync_mode_arguments(parser)

    def handle(self, *args, **options):
        full = sync_full_from_options(options)
        batch_size = options["batch_size"]
        only = (options.get("only") or "").strip() or None
        self.stdout.write(self.style.WARNING("Avvio sync 4D -> PostgreSQL..."))

        result = sync_causali_trasp(batch_size=batch_size, only=only, full=full)

        for table in result.tables:
            style = self.style.SUCCESS if table.ok else self.style.ERROR
            self.stdout.write(style(table.message))

        if result.ok:
            self.stdout.write(self.style.SUCCESS(result.message))
        else:
            self.stderr.write(self.style.ERROR(result.message))
            raise SystemExit(1)
