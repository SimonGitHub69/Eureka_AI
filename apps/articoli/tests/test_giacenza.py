"""Test calcolo giacenza da movimenti magazzino."""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.articoli.giacenza import (
    FLAG_CD_CARICO,
    FLAG_CD_SCARICO,
    FLAG_CD_ULTIMO_ACQUISTO,
    attach_giacenze_articoli,
    attach_inventario_articoli,
    costo_inventario,
    flag_cd_sign,
    giacenza_articolo,
    giacenze_non_nulle,
    giacenze_per_codici,
    inventario_anomalia_counts,
    inventario_categorie_label,
    inventario_discrepanza_soglia,
    inventario_filter_solo_anomalie,
    inventario_filter_giacenza_non_zero,
    inventario_gruppi_per_categoria,
    inventario_periodo_label,
    inventario_periodo_anno,
    inventario_preset_urls,
    inventario_active_preset,
    inventario_row_class,
    inventario_row_classes,
    inventario_sort_articoli,
    inventario_sort_label,
    inventario_sort_per_categoria,
    inventario_totali,
    inventario_want_ignora_anomalie,
    inventario_want_rottura,
    inventario_want_solo_anomalie,
    parse_inventario_categorie,
    parse_inventario_periodo,
    prezzi_movimento_per_codici,
    _prezzo_valido,
    _resolve_prezzo_medio,
    _resolve_prezzo_ultimo,
)
from apps.articoli.views import ArticoloInventarioPrintView
from apps.core.print_list import format_it_number


class FlagCdSignTests(SimpleTestCase):
    def test_carico(self):
        for value in FLAG_CD_CARICO:
            self.assertEqual(flag_cd_sign(value), 1)
        self.assertIn(3, FLAG_CD_CARICO)

    def test_ultimo_acquisto_include_giacenza_fornitore_e_diversi(self):
        self.assertEqual(FLAG_CD_ULTIMO_ACQUISTO, (1, 2, 3))
        self.assertIn(1, FLAG_CD_ULTIMO_ACQUISTO)
        self.assertIn(2, FLAG_CD_ULTIMO_ACQUISTO)
        self.assertIn(3, FLAG_CD_ULTIMO_ACQUISTO)

    def test_scarico(self):
        for value in FLAG_CD_SCARICO:
            self.assertEqual(flag_cd_sign(value), -1)

    def test_neutro(self):
        self.assertEqual(flag_cd_sign(None), 0)
        self.assertEqual(flag_cd_sign(99), 0)
        self.assertEqual(flag_cd_sign(-1), 0)


class PrezziMovimentoTests(SimpleTestCase):
    @patch("apps.articoli.giacenza.connection")
    def test_ultimo_carico_usa_flag_fornitore_e_diversi(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [("102", 9.85)],
            [("102", 9.775)],
            [("102", 9.4123)],
        ]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = prezzi_movimento_per_codici(["102"], data_a=date(2025, 12, 31))

        self.assertEqual(result["102"]["ultimo_carico"], 9.85)
        self.assertEqual(result["102"]["medio_carico"], 9.775)
        self.assertEqual(result["102"]["giacenza_iniziale"], 9.4123)
        sql_ultimo = cursor.execute.call_args_list[0][0][0]
        self.assertIn("Flag_CD\" IN (1, 2, 3)", sql_ultimo)
        self.assertIn("Update_Listino", sql_ultimo)
        self.assertIn("causali_maga", sql_ultimo)
        sql_medio = cursor.execute.call_args_list[1][0][0]
        self.assertIn("SUM(pd.\"Quantita\" * pd.\"ValoreUnNetto\")", sql_medio)
        self.assertIn("Update_Prezzo_Medio", sql_medio)
        self.assertNotIn("Update_Listino", sql_medio)
        sql_giacenza = cursor.execute.call_args_list[2][0][0]
        self.assertIn("Flag_CD\" IN (1, 2, 3)", sql_giacenza)

    @patch("apps.articoli.giacenza.connection")
    def test_prezzi_movimento_filtra_data_da(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], [], []]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        prezzi_movimento_per_codici(
            ["102"],
            data_da=date(2025, 1, 1),
            data_a=date(2025, 12, 31),
        )

        params = cursor.execute.call_args_list[0][0][1]
        self.assertEqual(params[1], date(2025, 1, 1))
        self.assertEqual(params[2], date(2025, 12, 31))
        sql = cursor.execute.call_args_list[0][0][0]
        self.assertIn('DataRegistraz"::date >= %s', sql)
        self.assertIn('DataRegistraz"::date <= %s', sql)


class GiacenzaQueryTests(SimpleTestCase):
    @patch("apps.articoli.giacenza.connection")
    def test_giacenza_articolo_empty_codice(self, mock_connection):
        self.assertEqual(giacenza_articolo(""), 0.0)
        self.assertEqual(giacenza_articolo(None), 0.0)
        mock_connection.cursor.assert_not_called()

    @patch("apps.articoli.giacenza.connection")
    def test_giacenza_articolo_runs_query(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = (13726.0,)
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = giacenza_articolo("va22")

        self.assertEqual(result, 13726.0)
        sql = cursor.execute.call_args[0][0]
        self.assertIn("Flag_CD", sql)
        self.assertIn("CodiceArt", sql)
        self.assertEqual(cursor.execute.call_args[0][1], ["VA22"])

    @patch("apps.articoli.giacenza.connection")
    def test_giacenze_per_codici_batch(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("VA22", 13726.0), ("AB01", 5.0)]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = giacenze_per_codici(["VA22", "ab01", ""])

        self.assertEqual(result, {"VA22": 13726.0, "AB01": 5.0})
        self.assertEqual(cursor.execute.call_args[0][1], [["AB01", "VA22"]])

    @patch("apps.articoli.giacenza.giacenze_per_codici", return_value={"VA22": 10.0})
    def test_attach_giacenze_articoli(self, _mock_batch):
        art = MagicMock(codice="va22")
        other = MagicMock(codice="NEW")
        attach_giacenze_articoli([art, other])
        self.assertEqual(art.giacenza_quantita, 10.0)
        self.assertEqual(other.giacenza_quantita, 0.0)


class InventarioHelpersTests(SimpleTestCase):
    @patch("apps.articoli.giacenza.connection")
    def test_giacenze_non_nulle_sql(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("VA22", 12.0), ("", 3.0)]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        result = giacenze_non_nulle()

        self.assertEqual(result, {"VA22": 12.0})
        sql = cursor.execute.call_args[0][0]
        self.assertIn("HAVING", sql)
        self.assertIn("Flag_CD", sql)
        self.assertNotIn("DataRegistraz", sql)
        self.assertEqual(cursor.execute.call_args[0][1], [])

    @patch("apps.articoli.giacenza.connection")
    def test_giacenze_non_nulle_filtra_periodo(self, mock_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("VA22", 4.0)]
        mock_connection.cursor.return_value.__enter__.return_value = cursor

        data_da = date(2025, 1, 1)
        data_a = date(2025, 12, 31)
        result = giacenze_non_nulle(data_da=data_da, data_a=data_a)

        self.assertEqual(result, {"VA22": 4.0})
        sql = cursor.execute.call_args[0][0]
        self.assertIn("DataRegistraz", sql)
        self.assertIn("movimentit", sql)
        # Inventario alla data di chiusura: usa solo data_a.
        self.assertEqual(cursor.execute.call_args[0][1], [data_a])

    def test_parse_inventario_periodo_scambia_date_invertite(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"data_da": "2025-12-31", "data_a": "2025-01-01"},
        )
        data_da, data_a = parse_inventario_periodo(request)
        self.assertEqual(data_da, date(2025, 1, 1))
        self.assertEqual(data_a, date(2025, 12, 31))

    def test_inventario_periodo_label(self):
        self.assertEqual(
            inventario_periodo_label(date(2025, 1, 1), date(2025, 6, 30)),
            "dal 01/01/2025 al 30/06/2025",
        )
        self.assertEqual(inventario_periodo_label(None, None), "")

    def test_inventario_periodo_anno(self):
        self.assertEqual(
            inventario_periodo_anno(2025),
            (date(2025, 1, 1), date(2025, 12, 31)),
        )

    def test_inventario_preset_urls(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"categoria_da": "1", "rottura": "1"},
        )
        urls = inventario_preset_urls(request, oggi=date(2026, 8, 24))
        self.assertIn("data_da=2026-01-01", urls["corrente"])
        self.assertIn("data_a=2026-12-31", urls["corrente"])
        self.assertIn("categoria_da=1", urls["corrente"])
        self.assertIn("rottura=1", urls["corrente"])
        self.assertIn("data_da=2025-01-01", urls["precedente"])
        self.assertIn("data_a=2025-12-31", urls["precedente"])

    def test_inventario_active_preset(self):
        self.assertEqual(
            inventario_active_preset(date(2026, 1, 1), date(2026, 12, 31), oggi=date(2026, 8, 24)),
            "corrente",
        )
        self.assertEqual(
            inventario_active_preset(date(2025, 1, 1), date(2025, 12, 31), oggi=date(2026, 8, 24)),
            "precedente",
        )
        self.assertIsNone(
            inventario_active_preset(date(2025, 1, 1), date(2025, 6, 30), oggi=date(2026, 8, 24)),
        )

    def test_parse_inventario_categorie_scambia_invertite(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"categoria_da": "9", "categoria_a": "1"},
        )
        cat_da, cat_a = parse_inventario_categorie(request)
        self.assertEqual(cat_da, "1")
        self.assertEqual(cat_a, "9")

    def test_inventario_categorie_label(self):
        self.assertEqual(
            inventario_categorie_label("1", "9"),
            "da categoria 1 a categoria 9",
        )
        self.assertEqual(inventario_categorie_label("", ""), "")

    def test_inventario_print_subtitle_include_categorie(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"categoria_da": "1", "categoria_a": "9"},
        )
        view = ArticoloInventarioPrintView()
        view.request = request
        view._inventario_categoria_da = "1"
        view._inventario_categoria_a = "9"
        subtitle = view.get_print_subtitle()
        self.assertIn("da categoria 1 a categoria 9", subtitle)

    def test_inventario_print_filter_summary_include_periodo(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"data_da": "2025-01-01", "data_a": "2025-12-31"},
        )
        view = ArticoloInventarioPrintView()
        view.request = request
        view._inventario_data_da = date(2025, 1, 1)
        view._inventario_data_a = date(2025, 12, 31)
        summary = view.get_filter_summary()
        self.assertIn("01/01/2025", summary)
        self.assertIn("31/12/2025", summary)

    @patch("apps.articoli.views.attach_inventario_articoli")
    @patch.object(ArticoloInventarioPrintView, "get_print_queryset")
    def test_inventario_print_passa_data_a_ad_attach(self, mock_print_qs, mock_attach):
        art = MagicMock(codice="102")
        qs = MagicMock()
        qs.order_by.return_value = [art]
        mock_print_qs.return_value = qs
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"data_da": "2025-01-01", "data_a": "2025-12-31", "q": "102"},
        )
        view = ArticoloInventarioPrintView()
        view.setup(request)
        view.request = request
        view._inventario_data_a = date(2025, 12, 31)
        view._inventario_stocks = {"102": 5.0}
        view.get_queryset()
        self.assertEqual(mock_attach.call_args.kwargs.get("data_a"), date(2025, 12, 31))

    def test_inventario_columns_match_4d(self):
        labels = [col["label"] for col in ArticoloInventarioPrintView.print_columns]
        self.assertEqual(
            labels,
            [
                "Articolo",
                "Cat.",
                "Descrizione",
                "UM",
                "Giacenza",
                "Prezzo ultimo\nacquisto",
                "Valore a\nprezzo ultimo",
                "Prezzo medio\ndi acquisto",
                "Valore a\nprezzo medio",
            ],
        )
        self.assertEqual(ArticoloInventarioPrintView.print_title, "Valori Articoli")

    def test_costo_inventario_prefers_prezzo_medio(self):
        art = MagicMock(prezzo_medio_acquisto=2.5, listino1=10.0)
        self.assertEqual(costo_inventario(art), 2.5)

    def test_costo_inventario_falls_back_to_listino(self):
        art = MagicMock(prezzo_medio_acquisto=None, listino1=8.0)
        self.assertEqual(costo_inventario(art), 8.0)

    @patch("apps.articoli.giacenza.prezzi_movimento_per_codici", return_value={})
    def test_attach_inventario_articoli(self, _mock_mov):
        art = MagicMock(
            codice="va22",
            prezzo_ult_car=3.0,
            prezzo_medio_acquisto=2.0,
            listino1=10.0,
        )
        attach_inventario_articoli([art], {"VA22": 5.0})
        self.assertEqual(art.giacenza_quantita, 5.0)
        # Senza movimenti: nessun prezzo da anagrafica.
        self.assertEqual(art.prezzo_ultimo_acquisto, 0.0)
        self.assertEqual(art.valore_prezzo_ultimo, 0.0)
        self.assertEqual(art.prezzo_medio_inventario, 0.0)
        self.assertEqual(art.valore_prezzo_medio, 0.0)
        # Costo inventario resta fallback anagrafica (valorizzazione generica).
        self.assertEqual(art.costo_inventario, 2.0)
        self.assertEqual(art.valore_inventario, 10.0)

    @patch(
        "apps.articoli.giacenza.prezzi_movimento_per_codici",
        return_value={
            "D4237": {
                "ultimo_carico": 38.4167,
                "medio_carico": 38.415,
                "giacenza_iniziale": 38.4167,
            }
        },
    )
    def test_attach_inventario_fallback_prezzo_ultimo_inf(self, _mock_mov):
        art = MagicMock(
            codice="D4237",
            prezzo_ult_car=float("inf"),
            prezzo_medio_acquisto=38.415,
            listino1=154.0,
        )
        attach_inventario_articoli([art], {"D4237": 1.0})
        self.assertEqual(art.prezzo_ultimo_acquisto, 38.417)
        self.assertAlmostEqual(art.valore_prezzo_ultimo, 38.417, places=3)
        self.assertEqual(art.prezzo_medio_inventario, 38.415)

    def test_attach_inventario_valore_usa_prezzo_arrotondato(self):
        """Il valore deve coincidere con qty × prezzo stampato (3 decimali)."""
        with patch(
            "apps.articoli.giacenza.prezzi_movimento_per_codici",
            return_value={"40102": {"ultimo_carico": 3.4115, "medio_carico": 3.4115}},
        ):
            art = MagicMock(
                codice="40102",
                prezzo_ult_car=3.0,
                prezzo_medio_acquisto=3.0,
                listino1=0,
            )
            attach_inventario_articoli([art], {"40102": 39.0})
        self.assertEqual(art.prezzo_ultimo_acquisto, 3.412)
        self.assertEqual(art.prezzo_medio_inventario, 3.412)
        self.assertAlmostEqual(art.valore_prezzo_ultimo, 133.068, places=3)
        self.assertAlmostEqual(art.valore_prezzo_medio, 133.068, places=3)
        self.assertEqual(format_it_number(art.valore_prezzo_ultimo, decimals=2), "133,07")

    def test_round_prezzo_inventario_half_up(self):
        """9,0245 → 9,025 (commerciale), non 9,024 (banker's di round())."""
        from apps.articoli.giacenza import _round_prezzo_inventario

        self.assertEqual(_round_prezzo_inventario(9.0245), 9.025)
        self.assertEqual(_round_prezzo_inventario(9.0157), 9.016)
        self.assertEqual(_round_prezzo_inventario(3.4115), 3.412)

    def test_prezzo_valido_rejects_inf(self):
        self.assertFalse(_prezzo_valido(float("inf")))
        self.assertTrue(_prezzo_valido(38.415))

    def test_resolve_prezzo_ultimo_ignora_giacenza_e_anagrafica(self):
        art = MagicMock(
            prezzo_ult_car=0.6,
            prezzo_medio_acquisto=0.679,
            listino1=154.0,
        )
        mov = {"giacenza_iniziale": 38.4167}
        self.assertEqual(_resolve_prezzo_ultimo(art, mov), 0.0)

    def test_resolve_prezzo_ultimo_prefers_ultimo_carico(self):
        art = MagicMock(
            prezzo_ult_car=0.6,
            prezzo_medio_acquisto=0.679,
            listino1=3.84,
        )
        mov = {"ultimo_carico": 1.1, "giacenza_iniziale": 0.6}
        self.assertEqual(_resolve_prezzo_ultimo(art, mov), 1.1)

    def test_resolve_prezzo_medio_prefers_medio_carico(self):
        art = MagicMock(
            prezzo_ult_car=float("inf"),
            prezzo_medio_acquisto=38.415,
            listino1=154.0,
        )
        mov = {
            "medio_carico": 9.58,
            "giacenza_iniziale": 40.0,
            "ultimo_carico": 40.0,
        }
        self.assertEqual(_resolve_prezzo_medio(art, mov), 9.58)

    def test_resolve_prezzo_medio_senza_movimenti_non_usa_anagrafica(self):
        art = MagicMock(
            prezzo_ult_car=float("inf"),
            prezzo_medio_acquisto=38.415,
            listino1=154.0,
        )
        mov = {"giacenza_iniziale": 40.0, "ultimo_carico": 40.0}
        self.assertEqual(_resolve_prezzo_medio(art, mov), 0.0)

    def test_attach_inventario_senza_ultimo_usa_solo_medio_movimenti(self):
        """Come CA1502830: carico diverso aggiorna solo medio."""
        with patch(
            "apps.articoli.giacenza.prezzi_movimento_per_codici",
            return_value={"CA1502830": {"medio_carico": 0.2378}},
        ):
            art = MagicMock(
                codice="CA1502830",
                prezzo_ult_car=0.0,
                prezzo_medio_acquisto=0.178,
                listino1=0,
            )
            attach_inventario_articoli([art], {"CA1502830": 150.0})
        self.assertEqual(art.prezzo_ultimo_acquisto, 0.0)
        self.assertEqual(art.valore_prezzo_ultimo, 0.0)
        self.assertEqual(art.prezzo_medio_inventario, 0.238)
        self.assertAlmostEqual(art.valore_prezzo_medio, 35.7, places=2)

    @patch(
        "apps.articoli.giacenza.prezzi_movimento_per_codici",
        return_value={
            "102": {
                "ultimo_carico": 9.7,
                "medio_carico": 9.58,
                "giacenza_iniziale": 9.4123,
            }
        },
    )
    def test_attach_inventario_usa_medio_carico(self, _mock_mov):
        art = MagicMock(
            codice="102",
            prezzo_ult_car=7.95,
            prezzo_medio_acquisto=9.7,
            listino1=0,
        )
        attach_inventario_articoli([art], {"102": 5.0}, data_a=date(2025, 12, 31))
        self.assertEqual(art.prezzo_ultimo_acquisto, 9.7)
        self.assertEqual(art.prezzo_medio_inventario, 9.58)
        self.assertEqual(art.valore_prezzo_ultimo, 48.5)
        self.assertAlmostEqual(art.valore_prezzo_medio, 47.9, places=2)
    @patch(
        "apps.articoli.giacenza.prezzi_movimento_per_codici",
        return_value={"D4237": {"ultimo_carico": 38.4167, "giacenza_iniziale": 38.4167}},
    )
    def test_prezzo_ultimo_acquisto_articolo_fallback(self, _mock_mov):
        art = MagicMock(
            codice="D4237",
            prezzo_ult_car=float("inf"),
            prezzo_medio_acquisto=38.415,
            listino1=154.0,
        )
        from apps.articoli.giacenza import prezzo_ultimo_acquisto_articolo

        self.assertEqual(prezzo_ultimo_acquisto_articolo(art), 38.4167)

    @patch("apps.articoli.giacenza.prezzi_movimento_per_codici", return_value={})
    def test_attach_inventario_giacenza_negativa(self, _mock_mov):
        art = MagicMock(
            codice="NEG1",
            prezzo_ult_car=2.0,
            prezzo_medio_acquisto=1.5,
            listino1=10.0,
        )
        attach_inventario_articoli([art], {"NEG1": -4.0})
        self.assertEqual(art.giacenza_quantita, -4.0)
        self.assertEqual(art.prezzo_ultimo_acquisto, 0.0)
        self.assertEqual(art.prezzo_medio_inventario, 0.0)
        self.assertEqual(art.valore_prezzo_ultimo, 0.0)
        self.assertEqual(art.valore_prezzo_medio, 0.0)
        self.assertEqual(art.valore_inventario, 0.0)
        self.assertEqual(inventario_row_class(art), "eureka-print-row--giacenza-negativa")

    def test_inventario_row_classes_prezzo_zero(self):
        art = MagicMock(
            giacenza_quantita=3.0,
            prezzo_ultimo_acquisto=0.0,
            prezzo_medio_inventario=0.0,
        )
        classes = inventario_row_classes(art)
        self.assertIn("eureka-print-row--prezzo-zero-ultimo", classes)
        self.assertIn("eureka-print-row--prezzo-zero-medio", classes)
        self.assertNotIn("eureka-print-row--prezzo-discrepanza", classes)

    def test_inventario_row_classes_discrepanza(self):
        art = MagicMock(
            giacenza_quantita=2.0,
            prezzo_ultimo_acquisto=10.0,
            prezzo_medio_inventario=5.0,
        )
        self.assertIn(
            "eureka-print-row--prezzo-discrepanza",
            inventario_row_classes(art, soglia=0.25),
        )
        ok = MagicMock(
            giacenza_quantita=2.0,
            prezzo_ultimo_acquisto=10.0,
            prezzo_medio_inventario=8.0,
        )
        self.assertNotIn(
            "eureka-print-row--prezzo-discrepanza",
            inventario_row_classes(ok, soglia=0.25),
        )
        # Con soglia più bassa (10%) 20% di scarto diventa anomalia.
        self.assertIn(
            "eureka-print-row--prezzo-discrepanza",
            inventario_row_classes(ok, soglia=0.10),
        )

    def test_inventario_filter_giacenza_non_zero(self):
        zero = MagicMock(giacenza_quantita=0.0)
        pos = MagicMock(giacenza_quantita=2.0)
        neg = MagicMock(giacenza_quantita=-1.0)
        self.assertEqual(
            inventario_filter_giacenza_non_zero([zero, pos, neg]),
            [pos, neg],
        )

    def test_inventario_filter_solo_anomalie(self):
        bad = MagicMock(
            giacenza_quantita=1.0,
            prezzo_ultimo_acquisto=0.0,
            prezzo_medio_inventario=2.0,
        )
        good = MagicMock(
            giacenza_quantita=1.0,
            prezzo_ultimo_acquisto=10.0,
            prezzo_medio_inventario=9.5,
        )
        filtered = inventario_filter_solo_anomalie([bad, good], soglia=0.25)
        self.assertEqual(filtered, [bad])

    def test_inventario_want_solo_anomalie(self):
        self.assertTrue(
            inventario_want_solo_anomalie(
                RequestFactory().get("/stampe/inventario/", {"solo_anomalie": "1"})
            )
        )
        self.assertFalse(
            inventario_want_solo_anomalie(RequestFactory().get("/stampe/inventario/"))
        )

    def test_inventario_want_ignora_anomalie(self):
        self.assertTrue(
            inventario_want_ignora_anomalie(
                RequestFactory().get("/stampe/inventario/", {"ignora_anomalie": "1"})
            )
        )
        self.assertFalse(
            inventario_want_ignora_anomalie(RequestFactory().get("/stampe/inventario/"))
        )

    def test_inventario_discrepanza_soglia(self):
        self.assertEqual(inventario_discrepanza_soglia(pct=25), 0.25)
        self.assertEqual(inventario_discrepanza_soglia(pct=10), 0.10)

    def test_inventario_anomalia_counts(self):
        rows = [
            MagicMock(
                giacenza_quantita=1.0,
                prezzo_ultimo_acquisto=0.0,
                prezzo_medio_inventario=2.0,
            ),
            MagicMock(
                giacenza_quantita=1.0,
                prezzo_ultimo_acquisto=10.0,
                prezzo_medio_inventario=5.0,
            ),
            MagicMock(
                giacenza_quantita=-1.0,
                prezzo_ultimo_acquisto=0.0,
                prezzo_medio_inventario=0.0,
            ),
        ]
        self.assertEqual(
            inventario_anomalia_counts(rows, soglia=0.25),
            {
                "giacenza_negativa": 1,
                "prezzo_zero_ultimo": 1,
                "prezzo_zero_medio": 0,
                "prezzo_discrepanza": 1,
            },
        )
    def test_inventario_totali_esclude_valori_giacenza_negativa(self):
        pos = MagicMock(giacenza_quantita=5.0, valore_prezzo_ultimo=10.0, valore_prezzo_medio=8.0)
        neg = MagicMock(giacenza_quantita=-2.0, valore_prezzo_ultimo=0.0, valore_prezzo_medio=0.0)
        self.assertEqual(
            inventario_totali([pos, neg]),
            {"giacenza": 3.0, "valore_ultimo": 10.0, "valore_medio": 8.0},
        )

    def test_inventario_totali(self):
        art = MagicMock(giacenza_quantita=5.0, valore_prezzo_ultimo=15.0, valore_prezzo_medio=10.0)
        self.assertEqual(
            inventario_totali([art]),
            {"giacenza": 5.0, "valore_ultimo": 15.0, "valore_medio": 10.0},
        )

    def test_inventario_want_rottura(self):
        self.assertTrue(
            inventario_want_rottura(RequestFactory().get("/stampe/inventario/", {"rottura": "1"}))
        )
        self.assertFalse(
            inventario_want_rottura(RequestFactory().get("/stampe/inventario/"))
        )

    def test_inventario_gruppi_per_categoria(self):
        a1 = MagicMock(codice="A", cat_omogenea="1")
        a2 = MagicMock(codice="B", cat_omogenea="1")
        a3 = MagicMock(codice="C", cat_omogenea="2")
        gruppi = inventario_gruppi_per_categoria([a1, a2, a3])
        self.assertEqual(len(gruppi), 2)
        self.assertEqual(gruppi[0][0], "1")
        self.assertEqual(gruppi[0][1], [a1, a2])
        self.assertEqual(gruppi[1][0], "2")
        self.assertEqual(gruppi[1][1], [a3])

    def test_inventario_sort_per_categoria(self):
        a = MagicMock(codice="B2", cat_omogenea="2")
        b = MagicMock(codice="A1", cat_omogenea="1")
        c = MagicMock(codice="A2", cat_omogenea="1")
        ordered = inventario_sort_per_categoria([a, c, b])
        self.assertEqual([x.codice for x in ordered], ["A1", "A2", "B2"])

    def test_inventario_sort_articoli_per_descrizione(self):
        a = MagicMock(codice="Z1", descrizione="Zeta", cat_omogenea="1")
        b = MagicMock(codice="A1", descrizione="Alfa", cat_omogenea="1")
        ordered = inventario_sort_articoli([a, b], "descrizione", "asc")
        self.assertEqual([x.codice for x in ordered], ["A1", "Z1"])

    def test_inventario_sort_articoli_per_categoria_label(self):
        a = MagicMock(
            codice="A1",
            cat_omogenea="2",
            categoria_label="Utensili",
        )
        b = MagicMock(
            codice="B1",
            cat_omogenea="1",
            categoria_label="Abbigliamento",
        )
        ordered = inventario_sort_articoli([a, b], "categoria_label", "asc")
        self.assertEqual([x.codice for x in ordered], ["B1", "A1"])

    def test_inventario_sort_articoli_rottura_mantiene_gruppi(self):
        a = MagicMock(codice="B2", descrizione="Beta", cat_omogenea="2")
        b = MagicMock(codice="A2", descrizione="Alfa", cat_omogenea="1")
        c = MagicMock(codice="A1", descrizione="Zeta", cat_omogenea="1")
        ordered = inventario_sort_articoli(
            [a, c, b], "descrizione", "asc", rottura=True
        )
        self.assertEqual([x.codice for x in ordered], ["A2", "A1", "B2"])

    def test_inventario_sort_label(self):
        self.assertEqual(inventario_sort_label("codice"), "Codice articolo")
        self.assertEqual(inventario_sort_label("unknown"), "")

    def test_format_it_number(self):
        self.assertEqual(format_it_number(2172.7, decimals=2), "2.172,70")
        self.assertEqual(format_it_number(0.01, decimals=3), "0,010")
        # Arrotondamento commerciale (.5 → su), non float binario.
        self.assertEqual(format_it_number(71.235, decimals=2), "71,24")
        self.assertEqual(format_it_number(45 * 1.583, decimals=2), "71,24")

    def test_inventario_print_filter_summary_include_ricerca(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"q": "RO702N"},
        )
        view = ArticoloInventarioPrintView()
        view.request = request
        self.assertIn('Ricerca: "RO702N"', view.get_filter_summary())

    def test_filter_summary_include_rottura(self):
        request = RequestFactory().get("/stampe/inventario/", {"rottura": "1"})
        view = ArticoloInventarioPrintView()
        view.request = request
        view._inventario_rottura = True
        self.assertIn("Rottura per categoria", view.get_filter_summary())

    def test_filter_summary_include_ignora_anomalie(self):
        request = RequestFactory().get(
            "/stampe/inventario/", {"ignora_anomalie": "1"}
        )
        view = ArticoloInventarioPrintView()
        view.request = request
        view._inventario_ignora_anomalie = True
        self.assertIn("Ignora anomalie", view.get_filter_summary())
        self.assertNotIn("Solo anomalie", view.get_filter_summary())

    def test_filter_summary_include_ordinamento(self):
        request = RequestFactory().get(
            "/stampe/inventario/",
            {"sort": "descrizione", "dir": "desc", "anteprima": "1"},
        )
        view = ArticoloInventarioPrintView()
        view.request = request
        self.assertIn("Ordina: Descrizione articolo ↓", view.get_filter_summary())
