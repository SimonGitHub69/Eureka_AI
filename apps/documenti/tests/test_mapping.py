"""Unit test mapping documenti (no DB ODBC)."""

from django.test import SimpleTestCase

from apps.documenti.mapping import (
    DEFAULT_TIPI_DOCUMENTO,
    map_header_row,
    map_line_row,
    pick_value,
    resolve_fattura_tipo_doc,
)


class TipoDocMappingTests(SimpleTestCase):
    def test_resolve_fattura_fattura_standard(self):
        row = {"TipoDocFE": "TD01", "Alfa": "A"}
        self.assertEqual(resolve_fattura_tipo_doc(row), "FAT")

    def test_resolve_fattura_nota_credito(self):
        row = {"TipoDocFE": "TD04"}
        self.assertEqual(resolve_fattura_tipo_doc(row), "NCR")

    def test_resolve_fattura_nota_debito(self):
        row = {"TipoDocFE": "TD05"}
        self.assertEqual(resolve_fattura_tipo_doc(row), "NDB")

    def test_resolve_fattura_fallback_alfa_nc(self):
        row = {"Alfa": "NC"}
        self.assertEqual(resolve_fattura_tipo_doc(row), "NCR")

    def test_default_tipi_include_all_required(self):
        codes = {t["codice"] for t in DEFAULT_TIPI_DOCUMENTO}
        self.assertEqual(codes, {"ORV", "ORA", "PRV", "DDT", "FAT", "NCR", "NDB"})
        by_code = {t["codice"]: t for t in DEFAULT_TIPI_DOCUMENTO}
        self.assertEqual(by_code["ORV"]["categoria"], "ORDINI")
        self.assertEqual(by_code["ORA"]["clifor_tipo"], "F")
        self.assertEqual(by_code["FAT"]["categoria"], "FATTURE")
        self.assertEqual(by_code["NCR"]["categoria"], "NOTE_CREDITO")
        self.assertEqual(by_code["PRV"]["categoria"], "PREVENTIVI")
        self.assertEqual(by_code["DDT"]["categoria"], "DDT")


class FieldMappingTests(SimpleTestCase):
    def test_pick_value_first_match(self):
        row = {"NumeroOrd": 42, "Numero": 99}
        self.assertEqual(pick_value(row, "NumeroFatt", "NumeroOrd", "Numero"), 42)

    def test_pick_value_case_insensitive(self):
        row = {"agente": "21"}
        self.assertEqual(pick_value(row, "Agente", "CodAgente"), "21")

    def test_map_header_fattura(self):
        row = {
            "ID_Testa": 1001,
            "NumeroFatt": 47,
            "DataFattura": "2024-03-15",
            "Cliente": "C0001",
            "Alfa": "A",
            "TotaleFattura": 1200.5,
            "Imponibile": 1000.0,
            "TipoDocFE": "TD04",
            "NumOrdineAcq": "OA-99",
            "DataOrdineAcq": "2024-02-20",
        }
        mapped = map_header_row(
            row, tipo_doc="NCR", source_table="Fatture", clifor_tipo="C"
        )
        self.assertEqual(mapped["id_4d"], 1001)
        self.assertEqual(mapped["numero"], 47)
        self.assertEqual(mapped["codice_clifor"], "C0001")
        self.assertEqual(mapped["alfa"], "A")
        self.assertEqual(mapped["totale"], 1200.5)
        self.assertEqual(mapped["tipo_doc_id"], "NCR")
        self.assertEqual(mapped["num_ordine_acq"], "OA-99")
        self.assertIsNotNone(mapped["data_ordine_acq"])

    def test_map_header_ordine_acquisto_fornitore(self):
        row = {
            "ID_Testa": 55,
            "NumeroOrd": 10,
            "Fornitore": "F001",
            "DataOrd": "2024-01-01",
        }
        mapped = map_header_row(
            row, tipo_doc="ORA", source_table="Ordini_Acquisto", clifor_tipo="F"
        )
        self.assertEqual(mapped["codice_clifor"], "F001")
        self.assertEqual(mapped["clifor_tipo"], "F")

    def test_map_line_dettaglio(self):
        row = {
            "ID": 900,
            "id_added_by_converter": 1001,
            "NumeroRiga": 1,
            "Codice": "ART01",
            "DescAgg": "Prodotto test",
            "Quantita": 2.0,
            "PrezzoUnitario": 50.0,
        }
        mapped = map_line_row(row)
        self.assertEqual(mapped["id_4d"], 900)
        self.assertEqual(mapped["codice"], "ART01")
        self.assertEqual(mapped["quantita"], 2.0)

    def test_map_header_preventivo(self):
        row = {
            "ID_Testa": 77,
            "Numero": 12,
            "Data": "2024-06-01",
            "Cliente": "C0099",
            "TotaleOrdine": 350.0,
            "Codice_ISO": "IT",
            "CondPaga": "31",
            "Agente": "A12",
            "Telefono": "0932 986532",
            "Porto1": "F.CO ADD. FATTURA",
            "Cod_CauTrasp": "01",
            "Annotazioni": "CELL. 3397226184",
            "Note": "NOTE GENERICHE",
            "Validita": "fino al 31/08/2026",
            "DataConsegna": "15/09/2026",
            "TipoPreventivo": "Cliente",
            "Confermato": True,
            "Valuta": "Euro",
            "Cambio": 1.0,
            "AddSpese": "Si",
            "Cod_Banca": "000683",
            "Data1": "28/07/2026",
            "Data2": "28/08/2026",
            "Data10": "28/04/2027",
        }
        mapped = map_header_row(
            row, tipo_doc="PRV", source_table="Preventivi", clifor_tipo="C"
        )
        self.assertEqual(mapped["id_4d"], 77)
        self.assertEqual(mapped["numero"], 12)
        self.assertEqual(mapped["codice_clifor"], "C0099")
        self.assertEqual(mapped["totale"], 350.0)
        self.assertEqual(mapped["cod_iso_dest"], "IT")
        self.assertEqual(mapped["cod_pagamento"], "31")
        self.assertEqual(mapped["codice_agente"], "A12")
        self.assertEqual(mapped["telefono"], "0932 986532")
        self.assertEqual(mapped["porto"], "F.CO ADD. FATTURA")
        self.assertEqual(mapped["cod_cau_trasp"], "01")
        self.assertEqual(mapped["annotazioni"], "CELL. 3397226184")
        self.assertEqual(mapped["note"], "NOTE GENERICHE")
        self.assertEqual(mapped["validita"], "fino al 31/08/2026")
        self.assertEqual(mapped["data_consegna"].date().isoformat(), "2026-09-15")
        self.assertEqual(mapped["tipo_preventivo"], "Cliente")
        self.assertTrue(mapped["confermato"])
        self.assertEqual(mapped["valuta"], "Euro")
        self.assertEqual(mapped["cambio"], 1.0)
        self.assertTrue(mapped["add_spese"])
        self.assertEqual(mapped["cod_banca"], "000683")
        self.assertEqual(mapped["scadenze"], ["2026-07-28", "2026-08-28", "2027-04-28"])

    def test_map_header_cod_banca_alias_banca(self):
        mapped = map_header_row(
            {"ID_Testa": 1, "Cliente": "C1", "Banca": "000105"},
            tipo_doc="ORA",
            source_table="Ordini_Acquisto",
            clifor_tipo="F",
        )
        self.assertEqual(mapped["cod_banca"], "000105")

    def test_map_header_add_spese_no_and_empty(self):
        mapped = map_header_row(
            {"ID_Testa": 1, "Cliente": "C1", "AddSpese": "No"},
            tipo_doc="PRV",
            source_table="Preventivi",
            clifor_tipo="C",
        )
        self.assertFalse(mapped["add_spese"])
        mapped2 = map_header_row(
            {"ID_Testa": 2, "Cliente": "C1", "AddSpese": ""},
            tipo_doc="ORV",
            source_table="Ordini_Vendita",
            clifor_tipo="C",
        )
        self.assertFalse(mapped2["add_spese"])

    def test_map_header_confermato_false_and_aliases(self):
        mapped = map_header_row(
            {"ID_Testa": 1, "Cliente": "C1", "Confermato": False},
            tipo_doc="PRV",
            source_table="Preventivi",
            clifor_tipo="C",
        )
        self.assertFalse(mapped["confermato"])
        mapped2 = map_header_row(
            {"ID_Testa": 2, "Cliente": "C1", "Confermato": "si"},
            tipo_doc="PRV",
            source_table="Preventivi",
            clifor_tipo="C",
        )
        self.assertTrue(mapped2["confermato"])
        mapped3 = map_header_row(
            {"ID_Testa": 3, "Cliente": "C1"},
            tipo_doc="ORV",
            source_table="Ordini_Vendita",
            clifor_tipo="C",
        )
        self.assertFalse(mapped3["confermato"])

    def test_map_header_validita_prefers_validita_over_offerta(self):
        mapped = map_header_row(
            {
                "ID_Testa": 1,
                "Cliente": "C1",
                "Validita": "30 giorni",
                "ValiditaOfferta": "60 giorni",
            },
            tipo_doc="PRV",
            source_table="Preventivi",
            clifor_tipo="C",
        )
        self.assertEqual(mapped["validita"], "30 giorni")

    def test_map_header_validita_fallback_offerta(self):
        mapped = map_header_row(
            {"ID_Testa": 2, "Cliente": "C1", "ValiditaOfferta": "15 gg"},
            tipo_doc="PRV",
            source_table="Preventivi",
            clifor_tipo="C",
        )
        self.assertEqual(mapped["validita"], "15 gg")

    def test_map_header_cod_cau_trasp_aliases(self):
        mapped = map_header_row(
            {"ID_Testa": 1, "Cliente": "C1", "CodCauTrasp": "03"},
            tipo_doc="ORV",
            source_table="Ordini_Vendita",
            clifor_tipo="C",
        )
        self.assertEqual(mapped["cod_cau_trasp"], "03")

        mapped2 = map_header_row(
            {"ID_Testa": 2, "Cliente": "C1", "CausaleTrasp": "05"},
            tipo_doc="DDT",
            source_table="Bolle",
            clifor_tipo="C",
        )
        self.assertEqual(mapped2["cod_cau_trasp"], "05")

    def test_map_header_annotazioni_distinct_from_note(self):
        row = {
            "ID_Testa": 88,
            "Cliente": "C1",
            "Annotazioni": "335 6429404 ANTONIO",
            "Note": "altro testo note",
        }
        mapped = map_header_row(
            row, tipo_doc="PRV", source_table="Preventivi", clifor_tipo="C"
        )
        self.assertEqual(mapped["annotazioni"], "335 6429404 ANTONIO")
        self.assertEqual(mapped["note"], "altro testo note")
        self.assertNotEqual(mapped["annotazioni"], mapped["note"])

    def test_map_header_annotazioni_case_insensitive(self):
        row = {
            "ID_Testa": 89,
            "Cliente": "C1",
            "ANNOTAZIONI": "  ba - ordine per telefono  ",
        }
        mapped = map_header_row(
            row, tipo_doc="ORV", source_table="Ordini_Vendita", clifor_tipo="C"
        )
        self.assertEqual(mapped["annotazioni"], "ba - ordine per telefono")

    def test_map_header_cod_pagamento_prefers_codpagamento(self):
        row = {
            "ID_Testa": 1,
            "NumeroFatt": 1,
            "Cliente": "C1",
            "CodPagamento": "44",
            "CondPaga": "31",
        }
        mapped = map_header_row(
            row, tipo_doc="FAT", source_table="Fatture", clifor_tipo="C"
        )
        self.assertEqual(mapped["cod_pagamento"], "44")

    def test_map_header_agente_alias_codagente(self):
        row = {
            "ID_Testa": 3,
            "Cliente": "C1",
            "CodAgente": "B7",
        }
        mapped = map_header_row(
            row, tipo_doc="PRV", source_table="Preventivi", clifor_tipo="C"
        )
        self.assertEqual(mapped["codice_agente"], "B7")

    def test_map_header_porto_alias_ordini_acquisto(self):
        row = {
            "ID_Testa": 4,
            "Fornitore": "F001",
            "Porto": "FRANCO",
        }
        mapped = map_header_row(
            row, tipo_doc="ORA", source_table="Ordini_Acquisto", clifor_tipo="F"
        )
        self.assertEqual(mapped["porto"], "FRANCO")

    def test_map_header_porto_ignores_codincoterm(self):
        row = {
            "ID_Testa": 5,
            "Cliente": "C1",
            "Porto1": "ASSEGNATO",
            "CodIncoterm_Porto": "EXW",
        }
        mapped = map_header_row(
            row, tipo_doc="FAT", source_table="Fatture", clifor_tipo="C"
        )
        self.assertEqual(mapped["porto"], "ASSEGNATO")

    def test_map_line_preventivi_dettaglio(self):
        row = {
            "ID_Riga": 501,
            "ID_Testa": 77,
            "NumeroRiga": 1,
            "Articolo": "PREV01",
            "DescAgg": "Riga preventivo",
            "Quantita": 3.0,
            "PrezzoUnitario": 10.0,
        }
        mapped = map_line_row(row)
        self.assertEqual(mapped["id_4d"], 501)
        self.assertEqual(mapped["codice"], "PREV01")
        self.assertEqual(mapped["quantita"], 3.0)
