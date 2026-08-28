from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ConfigurazioneProgramma
from apps.core.programma import is_documento_menu_enabled
from apps.documenti.models import TestaDocumento, TipoDocumento


class ParametriDocumentoMaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="paramuser",
            password="testpass123",
        )
        self.client.login(username="paramuser", password="testpass123")
        TipoDocumento.objects.get_or_create(
            codice="ORV",
            defaults={
                "label": "Ordini vendita",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "clifor_tipo": "C",
                "attivo": True,
            },
        )

    def test_list_ok(self):
        url = reverse("documenti:parametri_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ORV")

    def test_list_sort_by_codice_desc(self):
        TipoDocumento.objects.update_or_create(
            codice="AAA",
            defaults={
                "label": "Primo",
                "categoria": TipoDocumento.CATEGORIA_ALTRO,
                "clifor_tipo": "C",
                "attivo": True,
                "ordine": 1,
            },
        )
        TipoDocumento.objects.update_or_create(
            codice="ZZZ",
            defaults={
                "label": "Ultimo",
                "categoria": TipoDocumento.CATEGORIA_ALTRO,
                "clifor_tipo": "C",
                "attivo": True,
                "ordine": 99,
            },
        )
        url = reverse("documenti:parametri_list")
        response = self.client.get(url, {"sort": "codice", "dir": "desc"})
        self.assertEqual(response.status_code, 200)
        codes = [p.codice for p in response.context["parametri"]]
        self.assertEqual(codes[0], "ZZZ")
        self.assertLess(codes.index("ZZZ"), codes.index("AAA"))

    def test_create_custom_ordine_vendita(self):
        url = reverse("documenti:parametri_create")
        response = self.client.post(
            url,
            {
                "codice": "or2",
                "label": "Ordini vendita 2",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "clifor_tipo": "C",
                "attivo": "on",
                "ordine": "15",
                "scadenze": TipoDocumento.SCADENZE_FACOLTATIVE,
            },
        )
        self.assertEqual(response.status_code, 302)
        tipo = TipoDocumento.objects.get(codice="OR2")
        self.assertEqual(tipo.categoria, TipoDocumento.CATEGORIA_ORDINI)
        self.assertEqual(tipo.clifor_tipo, "C")
        self.assertEqual(tipo.scadenze, TipoDocumento.SCADENZE_FACOLTATIVE)
        self.assertEqual(tipo.label, "Ordini vendita 2")
        self.assertEqual(tipo.colonne_riga.count(), 8)
        campi = list(tipo.colonne_riga.order_by("posizione").values_list("campo", flat=True))
        self.assertEqual(campi[0], "numero_riga")
        self.assertEqual(campi[1], "codice")

    def test_colonne_riga_save_custom_layout(self):
        tipo = TipoDocumento.objects.get(codice="ORV")
        tipo.colonne_riga.all().delete()
        url = reverse("documenti:parametri_colonne", kwargs={"codice": "ORV"})
        prefix = "colonne_riga"
        payload = {
            f"{prefix}-TOTAL_FORMS": "3",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-campo": "codice",
            f"{prefix}-0-posizione": "10",
            f"{prefix}-0-etichetta": "Art.",
            f"{prefix}-1-campo": "descrizione",
            f"{prefix}-1-posizione": "20",
            f"{prefix}-2-campo": "quantita",
            f"{prefix}-2-posizione": "30",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        campi = list(
            tipo.colonne_riga.order_by("posizione").values_list("campo", "etichetta")
        )
        self.assertEqual(campi[0], ("codice", "Art."))
        self.assertEqual([c[0] for c in campi], ["codice", "descrizione", "quantita"])

    def test_document_form_uses_custom_column_order(self):
        tipo = TipoDocumento.objects.get(codice="ORV")
        tipo.colonne_riga.all().delete()
        from apps.documenti.models import ColonnaRigaDocumento

        ColonnaRigaDocumento.objects.create(
            tipo_doc=tipo, campo="descrizione", posizione=10
        )
        ColonnaRigaDocumento.objects.create(
            tipo_doc=tipo, campo="codice", posizione=20
        )
        url = reverse("documenti:create", kwargs={"tipo_doc": "ORV"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        pos_desc = html.find("</i>Descrizione")
        pos_codice = html.find("</i>Codice")
        self.assertGreater(pos_desc, 0)
        self.assertGreater(pos_codice, pos_desc)

    def test_custom_ordine_follows_doc_orv_flag(self):
        TipoDocumento.objects.create(
            codice="OR2",
            label="Ordini vendita 2",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            clifor_tipo="C",
            attivo=True,
        )
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_orv = True
        cfg.save()
        self.assertTrue(is_documento_menu_enabled("OR2"))
        list_url = reverse("documenti:list", kwargs={"tipo_doc": "OR2"})
        self.assertEqual(self.client.get(list_url).status_code, 200)

        cfg.doc_orv = False
        cfg.save()
        self.assertFalse(is_documento_menu_enabled("OR2"))
        self.assertEqual(self.client.get(list_url).status_code, 403)

    def test_custom_ordine_acquisto_follows_doc_ora(self):
        TipoDocumento.objects.create(
            codice="OA2",
            label="Ordini acquisto 2",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            clifor_tipo="F",
            attivo=True,
        )
        cfg = ConfigurazioneProgramma.get_solo()
        cfg.doc_ora = False
        cfg.save()
        self.assertFalse(is_documento_menu_enabled("OA2"))
        cfg.doc_ora = True
        cfg.save()
        self.assertTrue(is_documento_menu_enabled("OA2"))

    def test_delete_blocked_when_documents_exist(self):
        tipo = TipoDocumento.objects.create(
            codice="OR2",
            label="Ordini vendita 2",
            categoria=TipoDocumento.CATEGORIA_ORDINI,
            clifor_tipo="C",
            attivo=True,
        )
        TestaDocumento.objects.create(tipo_doc=tipo, id_4d=1, numero=1)
        url = reverse("documenti:parametri_delete", kwargs={"codice": "OR2"})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TipoDocumento.objects.filter(codice="OR2").exists())

    def test_form_has_scadenze_combo(self):
        url = reverse("documenti:parametri_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scadenze")
        self.assertContains(response, "Facoltative")
        self.assertContains(response, "Obbligatorie")
        self.assertContains(response, "Testo mail")

    def test_create_scadenze_obbligatorie(self):
        url = reverse("documenti:parametri_create")
        response = self.client.post(
            url,
            {
                "codice": "OR3",
                "label": "Ordini 3",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "clifor_tipo": "C",
                "attivo": "on",
                "ordine": "16",
                "scadenze": TipoDocumento.SCADENZE_OBBLIGATORIE,
            },
        )
        self.assertEqual(response.status_code, 302)
        tipo = TipoDocumento.objects.get(codice="OR3")
        self.assertTrue(tipo.scadenze_obbligatorie)
        self.assertEqual(tipo.scadenze_label, "Obbligatorie")

    def test_create_with_serie(self):
        url = reverse("documenti:parametri_create")
        response = self.client.post(
            url,
            {
                "codice": "OR4",
                "label": "Ordini 4",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "clifor_tipo": "C",
                "attivo": "on",
                "ordine": "17",
                "scadenze": TipoDocumento.SCADENZE_FACOLTATIVE,
                "serie": "ff",
            },
        )
        self.assertEqual(response.status_code, 302)
        tipo = TipoDocumento.objects.get(codice="OR4")
        self.assertEqual(tipo.serie, "FF")
        detail = self.client.get(reverse("documenti:parametri_detail", kwargs={"codice": "OR4"}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "FF")

    def test_create_with_testo_mail(self):
        url = reverse("documenti:parametri_create")
        response = self.client.post(
            url,
            {
                "codice": "OR5",
                "label": "Ordini 5",
                "categoria": TipoDocumento.CATEGORIA_ORDINI,
                "clifor_tipo": "C",
                "attivo": "on",
                "ordine": "18",
                "scadenze": TipoDocumento.SCADENZE_FACOLTATIVE,
                "testo_mail": "Gentile {cliente}, in allegato il documento {numero}.",
            },
        )
        self.assertEqual(response.status_code, 302)
        tipo = TipoDocumento.objects.get(codice="OR5")
        self.assertIn("{numero}", tipo.testo_mail)
        detail = self.client.get(reverse("documenti:parametri_detail", kwargs={"codice": "OR5"}))
        self.assertContains(detail, "Testo mail")
        self.assertContains(detail, "{numero}")
