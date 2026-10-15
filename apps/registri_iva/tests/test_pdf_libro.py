from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pypdf import PdfReader
import io

from apps.registri_iva.libro_registro import (
    LibroRegistroIvaCella,
    LibroRegistroIvaDati,
    LibroRegistroIvaRiepilogoVoce,
    LibroRegistroIvaRiga,
)
from apps.registri_iva.pdf_libro import (
    RIGHE_PER_PAGINA_PDF,
    chunk_righe_libro,
)
from apps.registri_iva.pdf_libro_reportlab import build_libro_pdf


def _riga_vendite(prot: int) -> LibroRegistroIvaRiga:
    texts = [
        str(prot),
        "01/01/2026",
        "Cliente Test",
        "1",
        "01/01/2026",
        "22%",
        "100,00",
        "22",
        "22,00",
        "122,00",
    ]
    return LibroRegistroIvaRiga(
        cells=[LibroRegistroIvaCella(text=t) for t in texts]
    )


class ChunkRigheLibroTests(SimpleTestCase):
    def test_empty(self):
        pages = chunk_righe_libro([], pagina_da=3)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].numero, 3)
        self.assertTrue(pages[0].is_last)

    def test_fills_pages(self):
        rows = list(range(RIGHE_PER_PAGINA_PDF * 2 + 10))
        pages = chunk_righe_libro(rows, pagina_da=1)
        self.assertGreaterEqual(len(pages), 3)
        self.assertEqual(pages[0].numero, 1)
        self.assertFalse(pages[0].is_last)
        self.assertTrue(pages[-1].is_last)
        total = sum(len(p.righe) for p in pages)
        self.assertEqual(total, len(rows))


class LibroPdfConteggioPagineTests(SimpleTestCase):
    def test_riepilogo_aggiunge_fogli_reali(self):
        """Il conteggio deve riflettere i fogli PDF stampati, incluso il riepilogo."""
        libro_senza = LibroRegistroIvaDati(
            registro=None,
            registro_label="Vendite",
            periodo_label="Gennaio 2026",
            anno=2026,
            righe=[_riga_vendite(i) for i in range(1, 6)],
        )
        pdf_senza = build_libro_pdf(
            libro=libro_senza,
            azienda_header={"ragione_sociale": "Demo SpA"},
            pagina_da=1,
        )
        self.assertIsNone(pdf_senza.pagina_riepilogo)
        self.assertEqual(pdf_senza.num_pages, pdf_senza.pagine_movimenti)
        self.assertEqual(len(PdfReader(io.BytesIO(pdf_senza.data)).pages), pdf_senza.num_pages)

        libro_con = LibroRegistroIvaDati(
            registro=None,
            registro_label="Vendite",
            periodo_label="Gennaio 2026",
            anno=2026,
            righe=list(libro_senza.righe),
            riepilogo=[
                LibroRegistroIvaRiepilogoVoce(
                    descrizione="Aliquota 22%",
                    imponibile=500.0,
                    iva=110.0,
                    iva_deducibile=110.0,
                )
            ],
            totale_imponibile=500.0,
            totale_iva=110.0,
            totale_iva_deducibile=110.0,
        )
        pdf_con = build_libro_pdf(
            libro=libro_con,
            azienda_header={"ragione_sociale": "Demo SpA"},
            pagina_da=1,
        )
        self.assertEqual(pdf_con.pagine_movimenti, pdf_senza.pagine_movimenti)
        self.assertGreater(pdf_con.num_pages, pdf_senza.num_pages)
        self.assertEqual(pdf_con.pagina_riepilogo, pdf_senza.num_pages + 1)
        self.assertEqual(pdf_con.ultima_pagina, pdf_con.pagina_da + pdf_con.num_pages - 1)
        self.assertEqual(len(PdfReader(io.BytesIO(pdf_con.data)).pages), pdf_con.num_pages)

    def test_pagina_da_sposta_numerazione(self):
        libro = LibroRegistroIvaDati(
            registro=None,
            registro_label="Vendite",
            periodo_label="Gennaio 2026",
            anno=2026,
            righe=[_riga_vendite(1)],
            riepilogo=[
                LibroRegistroIvaRiepilogoVoce("22%", 100.0, 22.0, iva_deducibile=22.0)
            ],
        )
        pdf = build_libro_pdf(
            libro=libro,
            azienda_header={"ragione_sociale": "Demo SpA"},
            pagina_da=10,
        )
        self.assertEqual(pdf.pagina_da, 10)
        self.assertEqual(pdf.pagina_riepilogo, 10 + pdf.pagine_movimenti)
        self.assertEqual(pdf.ultima_pagina, 10 + pdf.num_pages - 1)


class LibroPdfEndpointTests(TestCase):
    def test_requires_login(self):
        url = reverse("registri_iva:libro_pdf")
        r = self.client.get(url, {"anteprima": "1", "registro": "X"})
        self.assertIn(r.status_code, (302, 403))

    def test_requires_anteprima(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user("pdfuser", password="x")
        self.client.force_login(user)
        url = reverse("registri_iva:libro_pdf")
        r = self.client.get(url, {"registro": "X"})
        self.assertEqual(r.status_code, 400)
