"""
Indici sulle colonne piu usate dalle query dell'assistente AI.
Su DB vuoto (senza sync 4D) le tabelle unmanaged possono non esistere:
si creano gli indici solo se la relazione e presente.
"""

from django.db import migrations


def _create_if_table(table: str, create_sql: str) -> str:
    # Escape single quotes for EXECUTE string literal
    escaped = create_sql.replace("'", "''")
    return f"""
DO $migration$
BEGIN
  IF to_regclass('public.{table}') IS NOT NULL THEN
    EXECUTE '{escaped}';
  END IF;
END
$migration$;
"""


_RAW = [
    # Clienti
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_codnazione ON clienti ("CodNazione")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_ragsoc1 ON clienti ("RagioneSociale1")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_localita ON clienti ("Localita")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_provincia ON clienti ("Provincia")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_partitaiva ON clienti ("PartitaIva")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_agente ON clienti ("Agente")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_condpaga ON clienti ("CondPaga")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_zona ON clienti ("Zona")'),
    ("clienti", 'CREATE INDEX IF NOT EXISTS idx_clienti_fldisatt ON clienti ("Fl_Disattivato")'),
    # Fornitori
    ("fornitori", 'CREATE INDEX IF NOT EXISTS idx_fornitori_codnazione ON fornitori ("CodNazione")'),
    ("fornitori", 'CREATE INDEX IF NOT EXISTS idx_fornitori_ragsoc1 ON fornitori ("RagioneSociale1")'),
    ("fornitori", 'CREATE INDEX IF NOT EXISTS idx_fornitori_localita ON fornitori ("Localita")'),
    ("fornitori", 'CREATE INDEX IF NOT EXISTS idx_fornitori_provincia ON fornitori ("Provincia")'),
    ("fornitori", 'CREATE INDEX IF NOT EXISTS idx_fornitori_partitaiva ON fornitori ("PartitaIva")'),
    # Articoli
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione ON articoli ("Descrizione")'),
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_codgruppo ON articoli ("CodGruppo")'),
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_codiva ON articoli ("CodIva")'),
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_codfornitore ON articoli ("CodFornitore")'),
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_catom ON articoli ("CatOmogenea")'),
    ("articoli", 'CREATE INDEX IF NOT EXISTS idx_articoli_fldisatt ON articoli ("FlDisattivato")'),
    # Primanota
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_datareg ON primanota ("DataReg")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_causale ON primanota ("Causale")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_tipo ON primanota ("Tipo")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_registro ON primanota ("Registro")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_codpartita ON primanota ("CodicePartita")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_datadoc ON primanota ("DataDoc")'),
    ("primanota", 'CREATE INDEX IF NOT EXISTS idx_primanota_numeroreg ON primanota ("NumeroReg")'),
    # Primanota dettaglio
    ("primanota_dettaglio", 'CREATE INDEX IF NOT EXISTS idx_pndet_codiceiva ON primanota_dettaglio ("CodiceIva")'),
    ("primanota_dettaglio", 'CREATE INDEX IF NOT EXISTS idx_pndet_imp_val ON primanota_dettaglio ("Imp_Val")'),
    ("primanota_dettaglio", 'CREATE INDEX IF NOT EXISTS idx_pndet_importoiva ON primanota_dettaglio ("ImportoIva")'),
    ("primanota_dettaglio", 'CREATE INDEX IF NOT EXISTS idx_pndet_contodare ON primanota_dettaglio ("ContoDare")'),
    ("primanota_dettaglio", 'CREATE INDEX IF NOT EXISTS idx_pndet_contoavere ON primanota_dettaglio ("ContoAvere")'),
]

IDX = [_create_if_table(table, sql) for table, sql in _RAW]

DROP = [
    "DROP INDEX IF EXISTS idx_clienti_codnazione",
    "DROP INDEX IF EXISTS idx_clienti_ragsoc1",
    "DROP INDEX IF EXISTS idx_clienti_localita",
    "DROP INDEX IF EXISTS idx_clienti_provincia",
    "DROP INDEX IF EXISTS idx_clienti_partitaiva",
    "DROP INDEX IF EXISTS idx_clienti_agente",
    "DROP INDEX IF EXISTS idx_clienti_condpaga",
    "DROP INDEX IF EXISTS idx_clienti_zona",
    "DROP INDEX IF EXISTS idx_clienti_fldisatt",
    "DROP INDEX IF EXISTS idx_fornitori_codnazione",
    "DROP INDEX IF EXISTS idx_fornitori_ragsoc1",
    "DROP INDEX IF EXISTS idx_fornitori_localita",
    "DROP INDEX IF EXISTS idx_fornitori_provincia",
    "DROP INDEX IF EXISTS idx_fornitori_partitaiva",
    "DROP INDEX IF EXISTS idx_articoli_descrizione",
    "DROP INDEX IF EXISTS idx_articoli_codgruppo",
    "DROP INDEX IF EXISTS idx_articoli_codiva",
    "DROP INDEX IF EXISTS idx_articoli_codfornitore",
    "DROP INDEX IF EXISTS idx_articoli_catom",
    "DROP INDEX IF EXISTS idx_articoli_fldisatt",
    "DROP INDEX IF EXISTS idx_primanota_datareg",
    "DROP INDEX IF EXISTS idx_primanota_causale",
    "DROP INDEX IF EXISTS idx_primanota_tipo",
    "DROP INDEX IF EXISTS idx_primanota_registro",
    "DROP INDEX IF EXISTS idx_primanota_codpartita",
    "DROP INDEX IF EXISTS idx_primanota_datadoc",
    "DROP INDEX IF EXISTS idx_primanota_numeroreg",
    "DROP INDEX IF EXISTS idx_pndet_codiceiva",
    "DROP INDEX IF EXISTS idx_pndet_imp_val",
    "DROP INDEX IF EXISTS idx_pndet_importoiva",
    "DROP INDEX IF EXISTS idx_pndet_contodare",
    "DROP INDEX IF EXISTS idx_pndet_contoavere",
]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_configurazioneprogramma_extra_carbon"),
    ]

    operations = [
        migrations.RunSQL(
            sql=IDX,
            reverse_sql=DROP,
        ),
    ]
