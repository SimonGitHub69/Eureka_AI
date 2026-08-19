"""
Indici sulle colonne più usate dalle query dell'assistente AI.
Creati con IF NOT EXISTS per sicurezza su tabelle unmanaged (mirror 4D).
"""

from django.db import migrations


IDX = [
    # ── Clienti ──
    'CREATE INDEX IF NOT EXISTS idx_clienti_codnazione    ON clienti ("CodNazione")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_ragsoc1       ON clienti ("RagioneSociale1")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_localita      ON clienti ("Localita")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_provincia     ON clienti ("Provincia")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_partitaiva    ON clienti ("PartitaIva")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_agente        ON clienti ("Agente")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_condpaga      ON clienti ("CondPaga")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_zona          ON clienti ("Zona")',
    'CREATE INDEX IF NOT EXISTS idx_clienti_fldisatt      ON clienti ("Fl_Disattivato")',

    # ── Fornitori ──
    'CREATE INDEX IF NOT EXISTS idx_fornitori_codnazione  ON fornitori ("CodNazione")',
    'CREATE INDEX IF NOT EXISTS idx_fornitori_ragsoc1     ON fornitori ("RagioneSociale1")',
    'CREATE INDEX IF NOT EXISTS idx_fornitori_localita    ON fornitori ("Localita")',
    'CREATE INDEX IF NOT EXISTS idx_fornitori_provincia   ON fornitori ("Provincia")',
    'CREATE INDEX IF NOT EXISTS idx_fornitori_partitaiva  ON fornitori ("PartitaIva")',

    # ── Articoli ──
    'CREATE INDEX IF NOT EXISTS idx_articoli_descrizione  ON articoli ("Descrizione")',
    'CREATE INDEX IF NOT EXISTS idx_articoli_codgruppo    ON articoli ("CodGruppo")',
    'CREATE INDEX IF NOT EXISTS idx_articoli_codiva       ON articoli ("CodIva")',
    'CREATE INDEX IF NOT EXISTS idx_articoli_codfornitore ON articoli ("CodFornitore")',
    'CREATE INDEX IF NOT EXISTS idx_articoli_catom        ON articoli ("CatOmogenea")',
    'CREATE INDEX IF NOT EXISTS idx_articoli_fldisatt     ON articoli ("FlDisattivato")',

    # ── Primanota ──
    'CREATE INDEX IF NOT EXISTS idx_primanota_datareg     ON primanota ("DataReg")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_causale     ON primanota ("Causale")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_tipo        ON primanota ("Tipo")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_registro    ON primanota ("Registro")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_codpartita  ON primanota ("CodicePartita")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_datadoc     ON primanota ("DataDoc")',
    'CREATE INDEX IF NOT EXISTS idx_primanota_numeroreg   ON primanota ("NumeroReg")',

    # ── Primanota dettaglio ──
    'CREATE INDEX IF NOT EXISTS idx_pndet_codiceiva      ON primanota_dettaglio ("CodiceIva")',
    'CREATE INDEX IF NOT EXISTS idx_pndet_imp_val        ON primanota_dettaglio ("Imp_Val")',
    'CREATE INDEX IF NOT EXISTS idx_pndet_importoiva     ON primanota_dettaglio ("ImportoIva")',
    'CREATE INDEX IF NOT EXISTS idx_pndet_contodare      ON primanota_dettaglio ("ContoDare")',
    'CREATE INDEX IF NOT EXISTS idx_pndet_contoavere     ON primanota_dettaglio ("ContoAvere")',
]

DROP = [sql.replace("CREATE INDEX IF NOT EXISTS", "DROP INDEX IF EXISTS").split(" ON ")[0]
        for sql in IDX]


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
