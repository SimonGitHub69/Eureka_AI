"""Test contatori documento: CRUD e numerazione condivisa/separata."""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ConfigurazioneProgramma
from apps.documenti.models import ContatoreDocumento, TestaDocumento, TipoDocumento
from apps.documenti.numerazione import (
    allocate_next_numero,
    initial_numerazione,
    label_contatore_serie,
    next_numero_documento,
    peek_next_numero,
    serie_default_for,
)


def _tipo(codice, **defaults):
    defaults.setdefault("label", codice)
    defaults.setdefault("categoria", TipoDocumento.CATEGORIA_ALTRO)
    defaults.setdefault("clifor_tipo", "C")
    defaults.setdefault("attivo", True)
    obj, _ = TipoDocumento.objects.update_or_create(codice=codice, defaults=defaults)
    return obj


class ContatoreDocumentoCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="contuser",
            password="testpass123",
        )
        self.client.login(username="contuser", password="testpass123")

    def test_list_ok(self):
        ContatoreDocumento.objects.create(codice="CFAT", label="Fatture", ultimo_numero=10)
        url = reverse("documenti:contatori_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CFAT")
        self.assertContains(response, "Contatori")

    def test_create_contatore(self):
        url = reverse("documenti:contatori_create")
        response = self.client.post(
            url,
            {
                "codice": "ord",
                "label": "Ordini vendita",
                "tipo_contatore": "DOCUMENTI",
                "esercizio": "2026",
                "ultimo_numero": "5",
                "serie_default": "a",
            },
        )
        self.assertEqual(response.status_code, 302)
        c = ContatoreDocumento.objects.get(codice="ORD")
        self.assertEqual(c.label, "Ordini vendita")
        self.assertEqual(c.tipo_contatore, ContatoreDocumento.TIPO_DOCUMENTI)
        self.assertEqual(c.esercizio, 2026)
        self.assertEqual(c.ultimo_numero, 5)
        self.assertEqual(c.serie_default, "A")

    def test_create_contatore_primanota(self):
        url = reverse("documenti:contatori_create")
        response = self.client.post(
            url,
            {
                "codice": "pn",
                "label": "Primanota",
                "tipo_contatore": "PRIMANOTA",
                "esercizio": "2026",
                "ultimo_numero": "0",
                "serie_default": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        c = ContatoreDocumento.objects.get(codice="PN")
        self.assertEqual(c.tipo_contatore, ContatoreDocumento.TIPO_PRIMANOTA)

    def test_edit_contatore(self):
        c = ContatoreDocumento.objects.create(codice="CDDT", label="Bolle", ultimo_numero=0)
        url = reverse("documenti:contatori_edit", kwargs={"pk": c.pk})
        response = self.client.post(
            url,
            {
                "codice": "CDDT",
                "label": "DDT / Bolle",
                "tipo_contatore": "DOCUMENTI",
                "esercizio": "2025",
                "ultimo_numero": "100",
                "serie_default": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.label, "DDT / Bolle")
        self.assertEqual(c.esercizio, 2025)
        self.assertEqual(c.ultimo_numero, 100)

    def test_edit_saves_tipo_contatore(self):
        c = ContatoreDocumento.objects.create(
            codice="PN",
            label="Primanota",
            tipo_contatore=ContatoreDocumento.TIPO_DOCUMENTI,
            esercizio=2026,
        )
        url = reverse("documenti:contatori_edit", kwargs={"pk": c.pk})
        response = self.client.post(
            url,
            {
                "codice": "PN",
                "label": "Primanota",
                "tipo_contatore": "PRIMANOTA",
                "esercizio": "2026",
                "ultimo_numero": "0",
                "serie_default": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.tipo_contatore, ContatoreDocumento.TIPO_PRIMANOTA)

    def test_same_codice_allowed_for_different_year_or_tipo(self):
        ContatoreDocumento.objects.create(
            codice="PN",
            label="PN 2025",
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=2025,
        )
        ContatoreDocumento.objects.create(
            codice="PN",
            label="PN 2026",
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=2026,
        )
        ContatoreDocumento.objects.create(
            codice="PN",
            label="PN documenti",
            tipo_contatore=ContatoreDocumento.TIPO_DOCUMENTI,
            esercizio=2026,
        )
        self.assertEqual(ContatoreDocumento.objects.filter(codice="PN").count(), 3)

    def test_duplicate_prefill_next_esercizio(self):
        src = ContatoreDocumento.objects.create(
            codice="PN",
            label="Primanota 2026",
            tipo_contatore=ContatoreDocumento.TIPO_PRIMANOTA,
            esercizio=2026,
            ultimo_numero=44,
            serie_default="A",
        )
        url = reverse("documenti:contatori_duplicate", kwargs={"pk": src.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("codice"), "PN")
        self.assertEqual(form.initial.get("tipo_contatore"), ContatoreDocumento.TIPO_PRIMANOTA)
        self.assertEqual(form.initial.get("esercizio"), 2027)
        self.assertEqual(form.initial.get("ultimo_numero"), 0)
        self.assertEqual(form.initial.get("serie_default"), "A")
        self.assertContains(response, "Duplica contatore")

    def test_delete_blocked_when_tipo_linked(self):
        c = ContatoreDocumento.objects.create(codice="CLINK", label="Linkato")
        _tipo("T1", contatore=c)
        url = reverse("documenti:contatori_delete", kwargs={"pk": c.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ContatoreDocumento.objects.filter(pk=c.pk).exists())

    def test_delete_ok_when_unused(self):
        c = ContatoreDocumento.objects.create(codice="TMP", label="Temporaneo")
        url = reverse("documenti:contatori_delete", kwargs={"pk": c.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ContatoreDocumento.objects.filter(pk=c.pk).exists())

    def test_sidebar_contatori_link(self):
        response = self.client.get(reverse("documenti:contatori_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("documenti:contatori_list"))
        self.assertContains(response, "Contatori")


class ContatoreNumerazioneTests(TestCase):
    def setUp(self):
        self.shared = ContatoreDocumento.objects.create(
            codice="VEND",
            label="Vendite",
            ultimo_numero=0,
            serie_default="V",
        )
        self.sep_a = ContatoreDocumento.objects.create(
            codice="CORV", label="Solo ORV", ultimo_numero=0
        )
        self.sep_b = ContatoreDocumento.objects.create(
            codice="CORA", label="Solo ORA", ultimo_numero=0
        )
        self.tipo_fat = _tipo(
            "FAT",
            label="Fatture",
            categoria=TipoDocumento.CATEGORIA_FATTURE,
            contatore=self.shared,
        )
        self.tipo_ncr = _tipo(
            "NCR",
            label="Note credito",
            categoria=TipoDocumento.CATEGORIA_NOTE_CREDITO,
            contatore=self.shared,
        )
        self.tipo_orv = _tipo(
            "ORV",
            label="Ordini vendita",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            contatore=self.sep_a,
        )
        self.tipo_ora = _tipo(
            "ORA",
            label="Ordini acquisto",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            clifor_tipo="F",
            contatore=self.sep_b,
        )
        self.tipo_legacy = _tipo(
            "PRV",
            label="Preventivi",
            categoria=TipoDocumento.CATEGORIA_PREVENTIVI,
            contatore=None,
        )

    def test_shared_counter_increments_across_tipi(self):
        n1 = allocate_next_numero(self.tipo_fat)
        n2 = allocate_next_numero(self.tipo_ncr)
        n3 = allocate_next_numero(self.tipo_fat)
        self.assertEqual([n1, n2, n3], [1, 2, 3])
        self.shared.refresh_from_db()
        self.assertEqual(self.shared.ultimo_numero, 3)

    def test_separate_counters_are_independent(self):
        a1 = allocate_next_numero(self.tipo_orv)
        b1 = allocate_next_numero(self.tipo_ora)
        a2 = allocate_next_numero(self.tipo_orv)
        self.assertEqual(a1, 1)
        self.assertEqual(b1, 1)
        self.assertEqual(a2, 2)
        self.sep_a.refresh_from_db()
        self.sep_b.refresh_from_db()
        self.assertEqual(self.sep_a.ultimo_numero, 2)
        self.assertEqual(self.sep_b.ultimo_numero, 1)

    def test_legacy_without_contatore_uses_max_per_tipo(self):
        TestaDocumento.objects.create(
            tipo_doc=self.tipo_legacy, id_4d=1, numero=7, alfa=""
        )
        TestaDocumento.objects.create(
            tipo_doc=self.tipo_legacy, id_4d=2, numero=12, alfa=""
        )
        n = allocate_next_numero(self.tipo_legacy, "")
        self.assertEqual(n, 13)
        self.assertEqual(next_numero_documento("PRV", ""), 13)

    def test_existing_document_numbers_untouched(self):
        TestaDocumento.objects.create(
            tipo_doc=self.tipo_fat, id_4d=1, numero=50, alfa="OLD"
        )
        allocate_next_numero(self.tipo_fat)
        doc = TestaDocumento.objects.get(tipo_doc=self.tipo_fat, id_4d=1)
        self.assertEqual(doc.numero, 50)
        self.assertEqual(doc.alfa, "OLD")

    def test_peek_does_not_increment(self):
        self.shared.ultimo_numero = 100
        self.shared.save(update_fields=["ultimo_numero"])
        self.assertEqual(peek_next_numero(self.tipo_fat), 101)
        self.shared.refresh_from_db()
        self.assertEqual(self.shared.ultimo_numero, 100)
        self.assertEqual(
            initial_numerazione(self.tipo_fat),
            {"numero": 101, "alfa": "V", "contatore_scelto": self.shared.pk},
        )

    def test_serie_tipo_overrides_contatore(self):
        self.tipo_fat.serie = "X"
        self.tipo_fat.save(update_fields=["serie"])
        self.assertEqual(
            initial_numerazione(self.tipo_fat),
            {"numero": 1, "alfa": "X", "contatore_scelto": self.shared.pk},
        )
        self.tipo_fat.serie = ""
        self.tipo_fat.save(update_fields=["serie"])
        self.assertEqual(serie_default_for(self.tipo_fat), "V")

    def test_serie_tipo_without_contatore(self):
        self.tipo_legacy.serie = "p"
        self.tipo_legacy.save(update_fields=["serie"])
        self.assertEqual(serie_default_for(self.tipo_legacy), "p")
        self.assertEqual(
            initial_numerazione(self.tipo_legacy),
            {"numero": 1, "alfa": "p", "contatore_scelto": None},
        )

    def test_parametro_form_associates_contatore(self):
        user = get_user_model().objects.create_user(
            username="param2", password="testpass123"
        )
        self.client.login(username="param2", password="testpass123")
        url = reverse("documenti:parametri_edit", kwargs={"codice": "PRV"})
        response = self.client.post(
            url,
            {
                "codice": "PRV",
                "label": "Preventivi",
                "categoria": TipoDocumento.CATEGORIA_PREVENTIVI,
                "clifor_tipo": "C",
                "attivo": "on",
                "ordine": "0",
                "scadenze": TipoDocumento.SCADENZE_FACOLTATIVE,
                "contatore": str(self.shared.pk),
                "contatori": [str(self.shared.pk)],
                "serie": "b",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.tipo_legacy.refresh_from_db()
        self.assertEqual(self.tipo_legacy.contatore_id, self.shared.pk)
        self.assertEqual(self.tipo_legacy.serie, "B")
        self.assertEqual(
            list(self.tipo_legacy.contatori.values_list("codice", flat=True)),
            ["VEND"],
        )

def _righe_formset_empty():
    return {
        "righe-TOTAL_FORMS": "0",
        "righe-INITIAL_FORMS": "0",
        "righe-MIN_NUM_FORMS": "0",
        "righe-MAX_NUM_FORMS": "1000",
    }


class DocumentoCreateNumerazioneTests(TestCase):
    """Anteprima GET e allocazione atomica al salvataggio di Nuovo documento."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="docnum",
            password="testpass123",
        )
        self.client.login(username="docnum", password="testpass123")
        self.contatore = ContatoreDocumento.objects.create(
            codice="CPRV",
            label="Preventivi",
            ultimo_numero=100,
            serie_default="A",
        )
        self.tipo = _tipo(
            "PRV",
            label="Preventivi",
            categoria=TipoDocumento.CATEGORIA_PREVENTIVI,
            contatore=self.contatore,
        )
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_prv = True
        cfg.save(update_fields=["doc_prv"])

    def test_create_get_prefill_from_contatore(self):
        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("numero"), 101)
        self.assertEqual(form.initial.get("alfa"), "A")
        self.assertEqual(form.initial.get("contatore_scelto"), self.contatore.pk)
        self.assertIn("contatore_scelto", form.fields)
        self.assertContains(response, "101/A")
        self.assertContains(response, 'data-doc-numero-serie')
        data_doc = form.initial.get("data_documento")
        self.assertIsNotNone(data_doc)
        self.assertEqual(timezone.localtime(data_doc).date(), timezone.localdate())
        self.contatore.refresh_from_db()
        self.assertEqual(self.contatore.ultimo_numero, 100)

    def test_create_get_preview_senza_serie_niente_slash(self):
        self.contatore.serie_default = ""
        self.contatore.save(update_fields=["serie_default"])
        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("numero"), 101)
        self.assertEqual(form.initial.get("alfa"), "")
        self.assertContains(response, 'data-doc-summary-numero')
        self.assertNotContains(response, "101/")

    def test_create_get_prefill_serie_from_tipo(self):
        self.tipo.serie = "T"
        self.tipo.save(update_fields=["serie"])
        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("numero"), 101)
        self.assertEqual(form.initial.get("alfa"), "T")

    def test_create_post_allocates_and_increments(self):
        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        response = self.client.post(
            url,
            {
                "numero": "101",
                "alfa": "A",
                "contatore_scelto": str(self.contatore.pk),
                **_righe_formset_empty(),
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        doc = TestaDocumento.objects.get(tipo_doc=self.tipo)
        self.assertEqual(doc.numero, 101)
        self.assertEqual(doc.alfa, "A")
        self.contatore.refresh_from_db()
        self.assertEqual(self.contatore.ultimo_numero, 101)

    def test_two_creates_serialize_numbers(self):
        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        payload = {
            "numero": "101",
            "alfa": "A",
            "contatore_scelto": str(self.contatore.pk),
            **_righe_formset_empty(),
        }
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        # Secondo utente vede ancora 101 in anteprima ma riceve 102
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        numeri = list(
            TestaDocumento.objects.filter(tipo_doc=self.tipo)
            .order_by("numero")
            .values_list("numero", flat=True)
        )
        self.assertEqual(numeri, [101, 102])
        self.contatore.refresh_from_db()
        self.assertEqual(self.contatore.ultimo_numero, 102)

    def test_legacy_create_without_contatore(self):
        tipo = _tipo(
            "LEG",
            label="Legacy",
            categoria=TipoDocumento.CATEGORIA_ALTRO,
            contatore=None,
        )
        TestaDocumento.objects.create(tipo_doc=tipo, id_4d=1, numero=7, alfa="")
        url = reverse("documenti:create", kwargs={"tipo_doc": "LEG"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial.get("numero"), 8)
        self.assertNotIn("contatore_scelto", response.context["form"].fields)
        response = self.client.post(
            url,
            {"numero": "8", "alfa": "", **_righe_formset_empty()},
        )
        self.assertEqual(response.status_code, 302, response.content)
        doc = TestaDocumento.objects.filter(tipo_doc=tipo).exclude(id_4d=1).get()
        self.assertEqual(doc.numero, 8)

    def test_create_selects_serie_uses_matching_contatore(self):
        cont_a = ContatoreDocumento.objects.create(
            codice="PRVA",
            label="Preventivi A",
            ultimo_numero=10,
            serie_default="A",
        )
        cont_b = ContatoreDocumento.objects.create(
            codice="PRVB",
            label="Preventivi B",
            ultimo_numero=50,
            serie_default="B",
        )
        self.tipo.contatore = cont_a
        self.tipo.save(update_fields=["contatore"])
        self.tipo.contatori.set([cont_a, cont_b])

        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        form = get_resp.context["form"]
        self.assertEqual(form.initial.get("contatore_scelto"), cont_a.pk)
        self.assertEqual(form.initial.get("numero"), 11)
        self.assertEqual(form.initial.get("alfa"), "A")
        choices = {c.pk for c in form.fields["contatore_scelto"].queryset}
        self.assertEqual(choices, {cont_a.pk, cont_b.pk})

        post_b = self.client.post(
            url,
            {
                "numero": "51",
                "alfa": "X",
                "contatore_scelto": str(cont_b.pk),
                **_righe_formset_empty(),
            },
        )
        self.assertEqual(post_b.status_code, 302, post_b.content)
        doc_b = TestaDocumento.objects.get(tipo_doc=self.tipo)
        self.assertEqual(doc_b.numero, 51)
        self.assertEqual(doc_b.alfa, "B")
        cont_a.refresh_from_db()
        cont_b.refresh_from_db()
        self.assertEqual(cont_a.ultimo_numero, 10)
        self.assertEqual(cont_b.ultimo_numero, 51)

        post_a = self.client.post(
            url,
            {
                "numero": "11",
                "alfa": "",
                "contatore_scelto": str(cont_a.pk),
                **_righe_formset_empty(),
            },
        )
        self.assertEqual(post_a.status_code, 302, post_a.content)
        doc_a = (
            TestaDocumento.objects.filter(tipo_doc=self.tipo)
            .exclude(pk=doc_b.pk)
            .get()
        )
        self.assertEqual(doc_a.numero, 11)
        self.assertEqual(doc_a.alfa, "A")
        cont_a.refresh_from_db()
        self.assertEqual(cont_a.ultimo_numero, 11)

    def test_create_includes_contatori_from_tipi_affini(self):
        """Nuovo PRV offre anche contatori legati solo a Ordini (famiglia affini)."""
        cont_ord = ContatoreDocumento.objects.create(
            codice="CORD",
            label="Solo Ordini",
            ultimo_numero=20,
            serie_default="O",
        )
        tipo_orv = _tipo(
            "ORV",
            label="Ordini vendita",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            contatore=cont_ord,
        )
        tipo_orv.contatori.set([cont_ord])
        # Contatore PRV resta solo sul preventivo; ORD solo sull'ordine
        self.tipo.contatori.set([self.contatore])

        disponibili = self.tipo.contatori_disponibili()
        codes = {c.codice for c in disponibili}
        self.assertEqual(codes, {"CPRV", "CORD"})
        labels = {c.codice: label_contatore_serie(c) for c in disponibili}
        self.assertEqual(labels["CORD"], f"ORV · O — Solo Ordini ({cont_ord.esercizio})")
        self.assertEqual(labels["CPRV"], f"PRV · A — Preventivi ({self.contatore.esercizio})")

        # Fatture non entrano nella famiglia Preventivi/Ordini
        cont_fat = ContatoreDocumento.objects.create(
            codice="CFAT", label="Fatture", ultimo_numero=0, serie_default="F"
        )
        tipo_fat = _tipo(
            "FAT",
            label="Fatture",
            categoria=TipoDocumento.CATEGORIA_FATTURE,
            contatore=cont_fat,
        )
        tipo_fat.contatori.set([cont_fat])
        codes_after = {c.codice for c in self.tipo.contatori_disponibili()}
        self.assertEqual(codes_after, {"CPRV", "CORD"})

        url = reverse("documenti:create", kwargs={"tipo_doc": "PRV"})
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        form = get_resp.context["form"]
        choices = {c.pk for c in form.fields["contatore_scelto"].queryset}
        self.assertEqual(choices, {self.contatore.pk, cont_ord.pk})
        # Default resta il contatore del tipo corrente
        self.assertEqual(form.initial.get("contatore_scelto"), self.contatore.pk)

        post = self.client.post(
            url,
            {
                "numero": "21",
                "alfa": "X",
                "contatore_scelto": str(cont_ord.pk),
                **_righe_formset_empty(),
            },
        )
        self.assertEqual(post.status_code, 302, post.content)
        doc = TestaDocumento.objects.get(tipo_doc=self.tipo)
        self.assertEqual(doc.numero, 21)
        self.assertEqual(doc.alfa, "O")
        cont_ord.refresh_from_db()
        self.contatore.refresh_from_db()
        self.assertEqual(cont_ord.ultimo_numero, 21)
        self.assertEqual(self.contatore.ultimo_numero, 100)

    def test_fatture_affini_include_note_credito(self):
        cont_ncr = ContatoreDocumento.objects.create(
            codice="CNCR", label="NC", ultimo_numero=5, serie_default="N"
        )
        cont_fat = ContatoreDocumento.objects.create(
            codice="CFAT2", label="FAT", ultimo_numero=1, serie_default="F"
        )
        tipo_fat = _tipo(
            "FAT",
            label="Fatture",
            categoria=TipoDocumento.CATEGORIA_FATTURE,
            contatore=cont_fat,
        )
        tipo_fat.contatori.set([cont_fat])
        tipo_ncr = _tipo(
            "NCR",
            label="Note credito",
            categoria=TipoDocumento.CATEGORIA_NOTE_CREDITO,
            contatore=cont_ncr,
        )
        tipo_ncr.contatori.set([cont_ncr])
        codes = {c.codice for c in tipo_fat.contatori_disponibili()}
        self.assertEqual(codes, {"CFAT2", "CNCR"})
        # PRV non vede i contatori fatture
        self.assertNotIn(
            "CFAT2", {c.codice for c in self.tipo.contatori_disponibili()}
        )


def _contatore_label(codice, label, serie_default="", tipi=None):
    obj = SimpleNamespace(codice=codice, label=label, serie_default=serie_default)
    if tipi is not None:
        obj._tipi_origine_codici = tipi
    return obj


class LabelContatoreSerieTests(SimpleTestCase):
    def test_senza_serie_solo_codice_tipo(self):
        c = _contatore_label(
            "PRV", "Numero Preventivo", serie_default="", tipi=["PRV"]
        )
        self.assertEqual(label_contatore_serie(c), "PRV — Numero Preventivo")

    def test_serie_uguale_al_tipo_non_duplica(self):
        c = _contatore_label(
            "PRV", "Numero Preventivo", serie_default="PRV", tipi=["PRV"]
        )
        self.assertEqual(label_contatore_serie(c), "PRV — Numero Preventivo")

    def test_serie_uguale_al_tipo_case_insensitive(self):
        c = _contatore_label(
            "PRV", "Numero Preventivo", serie_default="prv", tipi=["PRV"]
        )
        self.assertEqual(label_contatore_serie(c), "PRV — Numero Preventivo")

    def test_serie_distinta_mostra_tipo_e_serie(self):
        c = _contatore_label(
            "PRV", "Numero Preventivo", serie_default="FF", tipi=["PRV"]
        )
        self.assertEqual(label_contatore_serie(c), "PRV · FF — Numero Preventivo")
