import logging
import threading
import uuid
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.staticfiles import finders
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView

from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

from apps.core.forms import (
    ComandoVocaleForm,
    Configurazione4DForm,
    ConfigurazionePCForm,
    ConfigurazioneProgrammaForm,
    ParametriContabiliForm,
    ParametriMailForm,
)
from apps.core.models import (
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
    ParametriContabili,
    ParametriMail,
    SPESE_CONTROPARTITA_FIELDS,
)
from apps.core.pagination import PerPageListMixin, filter_query_from_request, store_ai_filter
from apps.core.sorting import SortableListMixin
from apps.core.pc import (
    bind_nome_pc,
    detect_client_pc_name,
    get_nome_pc_from_request,
    is_valid_pc_name,
    normalize_nome_pc,
    register_device_for_request,
)
from apps.core.quattro_d import config_from_post, test_4d_connection
from apps.core.sync_4d import quote_ident
from apps.core.sync_incremental import clear_all_watermarks, sync_full_from_request
from apps.core.sync_anagrafiche import sync_clienti_fornitori
from apps.categorie.sync import sync_categorie
from apps.condizioni.sync import sync_condizioni
from apps.aliquote.sync import sync_aliquote
from apps.registri_iva.sync import sync_registri_iva
from apps.banche.sync import sync_banche
from apps.sconti.sync import sync_sconti
from apps.valute.sync import sync_valute
from apps.zone.sync import sync_zone
from apps.vettori.sync import sync_vettori
from apps.causali_trasp.sync import sync_causali_trasp
from apps.destinazioni.sync import sync_destinazioni
from apps.distinte_base.sync import sync_distinte_base
from apps.aziende.sync import sync_aziende
from apps.fatture.sync import sync_fatture
from apps.documenti.bridge import (
    FattureMirrorUnavailable,
    fatture_mirror_available,
    sync_fatture_mirror_to_unified,
)
from apps.documenti.models import TipoDocumento
from apps.documenti.sync import (
    FATTURE_TIPI,
    ensure_documenti_tables,
    sync_documenti_as_sync_result,
    sync_tab_porto,
)
from apps.gruppi_articoli.sync import sync_gruppi_articoli
from apps.gruppi_magazzini.sync import sync_gruppi_magazzini
from apps.magazzini.sync import sync_magazzini
from apps.causali_magazzino.sync import sync_causali_magazzino
from apps.carbon.sync import sync_carbon
from apps.lavorazioni_extra.sync import sync_lavorazioni_extra
from apps.stampi.sync import sync_stampi
from apps.articoli.sync import sync_articoli
from apps.operatori.sync import sync_operatori
from apps.timbrature.sync import sync_timbrature
from apps.pdc.sync import sync_pdc
from apps.primanota.sync import sync_primanota
from apps.causali_contabili.sync import sync_causali_contabili
from apps.raggruppamento_conti.sync import sync_raggruppamento_conti
from apps.raggruppamento_clifor.sync import sync_raggruppamento_clifor
from apps.core.programma import (
    describe_sync_documenti_tipi,
    get_documenti_menu_flags,
    is_documento_menu_enabled,
)


SYNC_4D_STEPS = (
    {
        "key": "anagrafiche",
        "label": "Anagrafiche",
        "description": "Clienti, Fornitori, Agenti",
        "runner": sync_clienti_fornitori,
        "tables": ("clienti", "fornitori", "agenti"),
    },
    {
        "key": "raggruppamento_clifor",
        "label": "Raggruppamento Clienti-Fornitori",
        "description": "Gruppo_Cli_For",
        "runner": sync_raggruppamento_clifor,
        "tables": ("raggruppamento_clifor",),
    },
    {
        "key": "aziende",
        "label": "Azienda",
        "description": "Azienda",
        "runner": sync_aziende,
        "tables": ("aziende",),
    },
    {
        "key": "categorie",
        "label": "Categorie",
        "description": "CatMerce",
        "runner": sync_categorie,
        "tables": ("categorie",),
    },
    {
        "key": "condizioni",
        "label": "Condizioni di Pagamento",
        "description": "CondizioniPag",
        "runner": sync_condizioni,
        "tables": ("condizioni",),
    },
    {
        "key": "porto",
        "label": "Porto",
        "description": "TabPorto",
        "runner": sync_tab_porto,
        "tables": ("tab_porto",),
    },
    {
        "key": "aliquote",
        "label": "Aliquote IVA",
        "description": "AliquoteIva",
        "runner": sync_aliquote,
        "tables": ("aliquote",),
    },
    {
        "key": "registri_iva",
        "label": "Registri IVA",
        "description": "RegistriIva",
        "runner": sync_registri_iva,
        "tables": ("registri_iva",),
    },
    {
        "key": "banche",
        "label": "Banche",
        "description": "Banche",
        "runner": sync_banche,
        "tables": ("banche",),
    },
    {
        "key": "sconti",
        "label": "Sconti",
        "description": "Sconti",
        "runner": sync_sconti,
        "tables": ("sconti",),
    },
    {
        "key": "valute",
        "label": "Valute",
        "description": "Valuta / Valuta_Det",
        "runner": sync_valute,
        "tables": ("valuta", "valuta_det"),
    },
    {
        "key": "zone",
        "label": "Zone",
        "description": "Zone",
        "runner": sync_zone,
        "tables": ("zone",),
    },
    {
        "key": "vettori",
        "label": "Spedizionieri",
        "description": "Spedizionieri (Vettori 4D)",
        "runner": sync_vettori,
        "tables": ("vettori",),
    },
    {
        "key": "causali_trasp",
        "label": "Causali trasporto",
        "description": "CausaliTrasp",
        "runner": sync_causali_trasp,
        "tables": ("causali_trasp",),
    },
    {
        "key": "destinazioni",
        "label": "DestCliFor",
        "description": "Destinazioni diverse",
        "runner": sync_destinazioni,
        "tables": ("DestCliFor",),
    },
    {
        "key": "gruppi_articoli",
        "label": "Gruppi articoli",
        "description": "GruppoArt",
        "runner": sync_gruppi_articoli,
        "tables": ("gruppi_articoli",),
    },
    {
        "key": "articoli",
        "label": "Articoli",
        "description": "Articoli",
        "runner": sync_articoli,
        "tables": ("articoli",),
    },
    {
        "key": "distinte_base",
        "label": "Distinte base",
        "description": "Distinte_Base",
        "runner": sync_distinte_base,
        "tables": ("distinte_base",),
    },
    {
        "key": "gruppi_magazzini",
        "label": "Gruppi Magazzini",
        "description": "RaggMagazzini",
        "runner": sync_gruppi_magazzini,
        "tables": ("gruppi_magazzini",),
    },
    {
        "key": "magazzini",
        "label": "Magazzini",
        "description": "Magazzini",
        "runner": sync_magazzini,
        "tables": ("magazzini",),
    },
    {
        "key": "causali_magazzino",
        "label": "Causali magazzino",
        "description": "CausaliMaga",
        "runner": sync_causali_magazzino,
        "tables": ("causali_maga",),
    },
    {
        "key": "stampi",
        "label": "Stampi",
        "description": "TabStampi",
        "runner": sync_stampi,
        "tables": ("stampi",),
    },
    {
        "key": "carbon",
        "label": "CARBON",
        "description": "Reparti, Lavorazioni_Partite, TabStampi_Seriali_Partite",
        "runner": sync_carbon,
        "tables": ("reparti", "lavorazioni_partite", "stampi_seriali_partite"),
    },
    {
        "key": "lavorazioni_extra",
        "label": "Lavorazioni extra",
        "description": "TabLavorazioniExtra",
        "runner": sync_lavorazioni_extra,
        "tables": ("lavorazioni_extra",),
    },
    {
        "key": "operatori",
        "label": "Operatori",
        "description": "Operatori",
        "runner": sync_operatori,
        "tables": ("operatori",),
    },
    {
        "key": "timbrature",
        "label": "Timbrature",
        "description": "Timbrature",
        "runner": sync_timbrature,
        "tables": ("timbrature",),
    },
    {
        "key": "pdc",
        "label": "Piano dei Conti",
        "description": "PDC",
        "runner": sync_pdc,
        "tables": ("pdc",),
    },
    {
        "key": "causali_contabili",
        "label": "Causali Contabili",
        "description": "CausaliC",
        "runner": sync_causali_contabili,
        "tables": ("causali_contabili",),
    },
    {
        "key": "raggruppamento_conti",
        "label": "Raggruppamento Conti",
        "description": "Raggruppamento",
        "runner": sync_raggruppamento_conti,
        "tables": ("raggruppamento_conti",),
    },
    {
        "key": "primanota",
        "label": "Primanota",
        "description": "Primanota e Primanota_Dettaglio",
        "runner": sync_primanota,
        "tables": ("primanota", "primanota_dettaglio"),
    },
    {
        "key": "fatture",
        "label": "Fatture",
        "description": "Fatture e Fatture_Dettaglio",
        "runner": sync_fatture,
        "tables": ("fatture", "fatture_dettaglio"),
    },
    {
        "key": "documenti",
        "label": "Documenti unificati",
        "description": "Teste/righe documenti (ORV, ORA, PRV, DDT, FAT, NCR, NDB)",
        "runner": sync_documenti_as_sync_result,
        "tables": ("teste_documenti", "righe_documenti"),
    },
)

SYNC_4D_STEP_KEYS = frozenset(step["key"] for step in SYNC_4D_STEPS)

_SYNC_4D_TASKS: dict[str, dict] = {}
_SYNC_4D_LOCK = threading.Lock()

# Task "running" senza avanzamento oltre questa soglia → considerati bloccati.
_SYNC_4D_STALE_AFTER = timedelta(hours=2)
# Dopo "Blocca", se il runner non termina entro questa soglia → scaduto.
_SYNC_4D_CANCEL_STALE_AFTER = timedelta(minutes=5)

# Tabelle mirror PostgreSQL importate da 4D (azzerabili).
MIRROR_4D_TABLES = tuple(
    dict.fromkeys(table for step in SYNC_4D_STEPS for table in step["tables"])
)


class ParametriPermissionMixin(PermissionRequiredMixin):
    permission_required = "core.access_parametri_4d"
    raise_exception = True


class ParametriProgrammaView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/configurazione_programma_form.html"
    success_url = reverse_lazy("core:parametri_programma")

    def get_context(self, form=None):
        return {
            "form": form
            or ConfigurazioneProgrammaForm(instance=ConfigurazioneProgramma.get_solo()),
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        instance = ConfigurazioneProgramma.get_solo()
        form = ConfigurazioneProgrammaForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Parametri programma salvati correttamente.")
            return redirect(self.success_url)
        return render(request, self.template_name, self.get_context(form=form))


class ParametriContabiliView(LoginRequiredMixin, View):
    """Maschera singleton Parametri contabili (aliquota spese + contropartite PDC)."""

    template_name = "core/parametri_contabili_form.html"
    success_url = reverse_lazy("core:parametri_contabili")

    def _linked_labels(self, form) -> dict[str, str]:
        from apps.articoli.lookups import resolve_descrizione

        data = form.data if form.is_bound else None
        instance = form.instance

        def _code(field_name: str) -> str:
            if data is not None:
                return (data.get(field_name) or "").strip()
            return (getattr(instance, field_name, None) or "").strip()

        labels = {
            "iva": resolve_descrizione("iva", _code("aliquota_iva_spese")),
        }
        for name, _label in SPESE_CONTROPARTITA_FIELDS:
            labels[name] = resolve_descrizione("pdc", _code(name))
        return labels

    def get_context(self, form=None):
        instance = ParametriContabili.get_solo()
        form = form or ParametriContabiliForm(instance=instance)
        return {
            "form": form,
            "labels": self._linked_labels(form),
            "spese_fields": SPESE_CONTROPARTITA_FIELDS,
            "lookup_url": reverse("articoli:lookup_codice"),
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        instance = ParametriContabili.get_solo()
        form = ParametriContabiliForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Parametri contabili salvati correttamente.")
            return redirect(self.success_url)
        return render(request, self.template_name, self.get_context(form=form))


class ParametriMailView(LoginRequiredMixin, ParametriPermissionMixin, View):
    """Maschera singleton Parametri mail (SMTP per invio automatico)."""

    template_name = "core/parametri_mail_form.html"
    success_url = reverse_lazy("core:parametri_mail")

    def get_context(self, form=None):
        instance = ParametriMail.get_solo()
        return {
            "form": form or ParametriMailForm(instance=instance),
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        from apps.core.mail import test_mail_connection

        action = (request.POST.get("action") or "save").strip()
        instance = ParametriMail.get_solo()
        form = ParametriMailForm(request.POST, instance=instance)

        if action == "test":
            if form.is_valid():
                cfg = form.save(commit=False)
            else:
                try:
                    porta = int(request.POST.get("porta") or instance.porta or 587)
                except (TypeError, ValueError):
                    porta = instance.porta or 587
                try:
                    timeout = int(
                        request.POST.get("timeout_secondi")
                        or instance.timeout_secondi
                        or 30
                    )
                except (TypeError, ValueError):
                    timeout = instance.timeout_secondi or 30
                cfg = ParametriMail(
                    server_smtp=(request.POST.get("server_smtp") or "").strip(),
                    porta=porta,
                    usa_tls="usa_tls" in request.POST,
                    usa_ssl="usa_ssl" in request.POST,
                    utente=(request.POST.get("utente") or "").strip(),
                    password=(request.POST.get("password") or "").strip()
                    or instance.password,
                    mittente=(request.POST.get("mittente") or "").strip(),
                    nome_mittente=(request.POST.get("nome_mittente") or "").strip(),
                    reply_to=(request.POST.get("reply_to") or "").strip(),
                    copia_nascosta=(request.POST.get("copia_nascosta") or "").strip(),
                    email_test=(request.POST.get("email_test") or "").strip(),
                    timeout_secondi=timeout,
                    attiva=True,
                )
            result = test_mail_connection(cfg)
            if result.ok:
                messages.success(request, result.message)
            else:
                messages.error(request, result.message)
            return render(request, self.template_name, self.get_context(form=form))

        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Parametri mail salvati correttamente.")
            return redirect(self.success_url)
        return render(request, self.template_name, self.get_context(form=form))


class Parametri4DView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/configurazione_4d_form.html"
    success_url = reverse_lazy("core:parametri_4d")

    def get_context(self, form=None):
        sync_counts = _sync_4d_counts()
        doc_menu_flags = get_documenti_menu_flags()
        tipi_qs = TipoDocumento.objects.filter(attivo=True)
        sync_steps = [
            {
                "key": step["key"],
                "label": step["label"],
                "description": (
                    describe_sync_documenti_tipi()
                    if step["key"] == "documenti"
                    else step["description"]
                ),
                "tables": [
                    {"name": table, "count": sync_counts.get(table, 0)}
                    for table in step["tables"]
                ],
            }
            for step in SYNC_4D_STEPS
        ]
        return {
            "form": form
            or Configurazione4DForm(instance=Configurazione4D.get_solo()),
            "sync_counts": sync_counts,
            "sync_steps": sync_steps,
            "doc_menu_flags": doc_menu_flags,
            "tipi_con_flags": [
                {
                    "tipo": tipo,
                    "enabled": doc_menu_flags.get(tipo.codice, True),
                }
                for tipo in tipi_qs
            ],
            "fatture_mirror_available": fatture_mirror_available(),
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        action = (request.POST.get("action") or "save").strip()
        instance = Configurazione4D.get_solo()

        if action == "test":
            config = config_from_post(request.POST, instance)
            result = test_4d_connection(config)
            form = Configurazione4DForm(request.POST, instance=instance)

            if result.ok:
                messages.success(request, result.message)
            else:
                messages.error(request, result.message)

            return render(request, self.template_name, self.get_context(form=form))

        form = Configurazione4DForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Parametri 4D salvati correttamente.")
            return redirect(self.success_url)

        return render(request, self.template_name, self.get_context(form=form))


class Sync4DStartView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        selected_steps, documenti_tipos, documenti_from_mirror, error = (
            _parse_sync_4d_selection(request)
        )
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)

        with _SYNC_4D_LOCK:
            _expire_stale_sync_4d_tasks_locked()
            running = _find_running_sync_4d_task_locked()
            if running:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Sincronizzazione già in corso.",
                        "task_id": running["id"],
                    },
                    status=409,
                )
            task = _new_sync_4d_task(
                request.user,
                selected_steps=selected_steps,
                documenti_tipos=documenti_tipos,
                documenti_from_mirror=documenti_from_mirror,
                sync_full=sync_full_from_request(request),
            )
            _SYNC_4D_TASKS[task["id"]] = task

        thread = threading.Thread(
            target=_run_sync_4d_task,
            args=(task["id"],),
            daemon=True,
        )
        thread.start()
        return JsonResponse({"ok": True, "task_id": task["id"]})


class Sync4DStatusView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def get(self, request, task_id, *args, **kwargs):
        with _SYNC_4D_LOCK:
            _expire_stale_sync_4d_tasks_locked()
        snapshot = _sync_4d_task_snapshot(task_id)
        if not snapshot:
            return JsonResponse({"ok": False, "error": "Task non trovato."}, status=404)
        return JsonResponse({"ok": True, "task": snapshot})


class Sync4DCancelView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        task_id = request.POST.get("task_id")
        if not task_id:
            return JsonResponse({"ok": False, "error": "ID task mancante."}, status=400)

        with _SYNC_4D_LOCK:
            _expire_stale_sync_4d_tasks_locked()
            task = _SYNC_4D_TASKS.get(task_id)
            if not task or task["status"] != "running":
                return JsonResponse(
                    {"ok": False, "error": "Nessuna sincronizzazione attiva da interrompere."},
                    status=404,
                )
            task["cancel_requested"] = True
            task["cancel_requested_at"] = timezone.now().isoformat()
            task["message"] = "Interruzione richiesta, attendere..."

        return JsonResponse({"ok": True, "message": "Interruzione richiesta."})


class Sync4DClearView(LoginRequiredMixin, ParametriPermissionMixin, View):
    """Azzera tutte le tabelle mirror PostgreSQL importate da 4D."""

    def post(self, request, *args, **kwargs):
        with _SYNC_4D_LOCK:
            _expire_stale_sync_4d_tasks_locked()
            running = _find_running_sync_4d_task_locked()
            if running:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            "Impossibile azzerare: sincronizzazione in corso. "
                            "Attendi la fine o usa «Blocca sincronizzazione», "
                            "poi riprova."
                        ),
                        "task_id": running["id"],
                    },
                    status=409,
                )

        counts_before = {table: _pg_table_count(table) for table in MIRROR_4D_TABLES}
        cleared, errors = _clear_mirror_4d_tables()
        watermarks_cleared = clear_all_watermarks()
        counts_after = {table: _pg_table_count(table) for table in MIRROR_4D_TABLES}

        if errors:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Azzeramento incompleto: " + "; ".join(errors),
                    "cleared": cleared,
                    "errors": errors,
                    "counts_before": counts_before,
                    "counts_after": counts_after,
                },
                status=500,
            )

        return JsonResponse(
            {
                "ok": True,
                "message": f"Azzerate {len(cleared)} tabelle mirror PostgreSQL "
                f"({watermarks_cleared} watermark reset).",
                "cleared": cleared,
                "counts_before": counts_before,
                "counts_after": counts_after,
            }
        )


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _mark_sync_4d_task_stale_locked(task: dict, reason: str) -> None:
    """Caller must hold _SYNC_4D_LOCK."""
    if task.get("status") not in ("running", "pending"):
        return
    task["status"] = "error"
    task["current_step"] = ""
    task["message"] = reason
    task["finished_at"] = timezone.now().isoformat()
    task["errors"] = list(task.get("errors") or []) + [reason]
    for step in task.get("steps") or []:
        if step.get("status") in ("running", "pending"):
            step["status"] = "error"
            step["message"] = reason


def _expire_stale_sync_4d_tasks_locked() -> list[str]:
    """Expire stuck running/pending tasks. Caller must hold _SYNC_4D_LOCK."""
    now = timezone.now()
    expired: list[str] = []
    for task in list(_SYNC_4D_TASKS.values()):
        if task.get("status") not in ("running", "pending"):
            continue
        started = _parse_iso_dt(task.get("started_at")) or _parse_iso_dt(
            task.get("created_at")
        )
        cancel_at = _parse_iso_dt(task.get("cancel_requested_at"))
        if task.get("cancel_requested") and cancel_at is None:
            # Task creati prima di cancel_requested_at: usa started_at come fallback.
            cancel_at = started
        reason = None
        if task.get("cancel_requested") and cancel_at and (
            now - cancel_at >= _SYNC_4D_CANCEL_STALE_AFTER
        ):
            reason = (
                "Sincronizzazione bloccata dopo interruzione "
                f"(>{int(_SYNC_4D_CANCEL_STALE_AFTER.total_seconds())}s): task scaduto."
            )
        elif started and (now - started >= _SYNC_4D_STALE_AFTER):
            reason = (
                "Sincronizzazione bloccata "
                f"(>{int(_SYNC_4D_STALE_AFTER.total_seconds() // 3600)}h): task scaduto."
            )
        elif not started and task.get("status") == "pending":
            # Task creato ma thread mai partito / crash prima di started_at.
            created = _parse_iso_dt(task.get("created_at"))
            if created and (now - created >= timedelta(minutes=2)):
                reason = "Avvio sync non riuscito: task scaduto."
        if reason:
            _mark_sync_4d_task_stale_locked(task, reason)
            expired.append(task["id"])
            logger.warning("Sync 4D task %s scaduto: %s", task["id"], reason)
    return expired


def _find_running_sync_4d_task_locked() -> dict | None:
    """Caller must hold _SYNC_4D_LOCK. Call expire first."""
    return next(
        (
            task
            for task in _SYNC_4D_TASKS.values()
            if task.get("status") in ("running", "pending")
        ),
        None,
    )


def _clear_mirror_4d_tables() -> tuple[list[str], list[str]]:
    cleared: list[str] = []
    errors: list[str] = []
    with connection.cursor() as cur:
        for table in MIRROR_4D_TABLES:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {quote_ident(table)} CASCADE;")
                cleared.append(table)
            except Exception as exc:
                errors.append(f"{table}: {exc}")
    return cleared, errors


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


def _sync_4d_counts() -> dict[str, int]:
    return {table: _pg_table_count(table) for table in MIRROR_4D_TABLES}


def _parse_sync_4d_selection(
    request,
) -> tuple[list[str], list[str], bool, str | None]:
    """Parse step/tipo selection from POST. Returns (steps, doc_tipos, from_mirror, error)."""
    steps = request.POST.getlist("steps")
    doc_tipos_raw = request.POST.getlist("tipos")
    from_mirror = request.POST.get("from_fatture_mirror") == "on"

    selected_steps = [s.strip() for s in steps if s.strip() in SYNC_4D_STEP_KEYS]
    if not selected_steps:
        return [], [], False, "Selezionare almeno uno step da sincronizzare."

    documenti_tipos = [
        t.strip().upper()
        for t in doc_tipos_raw
        if t.strip() and is_documento_menu_enabled(t.strip().upper())
    ]

    if "documenti" in selected_steps and not documenti_tipos and not from_mirror:
        return (
            selected_steps,
            [],
            False,
            "Selezionare almeno un tipo documento o il bridge mirror fatture.",
        )

    return selected_steps, documenti_tipos, from_mirror, None


def _sync_4d_step_state(task: dict, key: str) -> dict | None:
    for step in task["steps"]:
        if step["key"] == key:
            return step
    return None


def _sync_4d_documenti_step(
    task_id: str,
    *,
    tipos: list[str],
    from_mirror: bool,
    full: bool = False,
):
    """Run documenti sync step with optional tipo filter and mirror bridge.

    ODBC (4D → teste/righe documenti) is the primary path. Bridge from PostgreSQL
    ``fatture`` mirror is optional: if requested but tables are missing, skip with
    a warning and still run ODBC (including full sync when no tipi were selected).
    """
    from apps.core.sync_4d import SyncResult, TableSyncResult

    cancel_check = lambda: _sync_4d_cancel_requested(task_id)
    parts: list[str] = []
    tables: list[TableSyncResult] = []
    ok = True

    try:
        ensure_documenti_tables()
    except Exception as exc:
        return SyncResult(
            ok=False,
            tables=[],
            message=f"Impossibile preparare tabelle documenti: {exc}",
        )

    mirror_present = fatture_mirror_available() if from_mirror else False
    # Bridge-only (no tipi) skips ODBC only when the mirror actually exists.
    run_odbc = bool(tipos) or not from_mirror or not mirror_present
    if run_odbc:
        result = sync_documenti_as_sync_result(
            only=tipos if tipos else None,
            cancel_check=cancel_check,
            full=full,
        )
        tables.extend(result.tables)
        if result.message:
            parts.append(result.message)
        ok = ok and result.ok

    if from_mirror and not cancel_check():
        mirror_tipos = [t for t in FATTURE_TIPI if is_documento_menu_enabled(t)]
        if tipos:
            mirror_tipos = [t for t in mirror_tipos if t in tipos]
        if not mirror_tipos:
            parts.append(
                "Bridge mirror fatture: nessun tipo FAT/NCR/NDB selezionato o abilitato."
            )
        else:
            try:
                n_teste, n_righe = sync_fatture_mirror_to_unified(tipos=mirror_tipos)
            except FattureMirrorUnavailable as exc:
                # Warning only — never fail the step for a missing mirror.
                parts.append(str(exc))
                tables.append(
                    TableSyncResult(
                        source="fatture_mirror",
                        target="teste_documenti",
                        rows=0,
                        ok=True,
                        message=str(exc),
                    )
                )
            else:
                parts.append(
                    f"Bridge mirror fatture ({', '.join(mirror_tipos)}): "
                    f"{n_teste} testate, {n_righe} righe."
                )
                tables.append(
                    TableSyncResult(
                        source="fatture_mirror",
                        target="teste_documenti",
                        rows=n_teste,
                        ok=True,
                        message=parts[-1],
                    )
                )

    if cancel_check():
        ok = False
        if not parts:
            parts.append("Interrotto dall'utente.")

    message = "\n".join(parts) if parts else "Sync documenti completato."
    return SyncResult(ok=ok, tables=tables, message=message)


def _new_sync_4d_task(
    user,
    *,
    selected_steps: list[str] | None = None,
    documenti_tipos: list[str] | None = None,
    documenti_from_mirror: bool = False,
    sync_full: bool = False,
) -> dict:
    selected_set = set(selected_steps or [step["key"] for step in SYNC_4D_STEPS])
    steps = [
        {
            "key": spec["key"],
            "label": spec["label"],
            "description": spec["description"],
            "status": "pending" if spec["key"] in selected_set else "skipped",
            "message": "" if spec["key"] in selected_set else "Non selezionato.",
            "rows": {},
        }
        for spec in SYNC_4D_STEPS
    ]
    return {
        "id": uuid.uuid4().hex,
        "status": "pending",
        "progress_pct": 0,
        "current_step": "",
        "started_by": getattr(user, "username", ""),
        "created_at": timezone.now().isoformat(),
        "started_at": "",
        "finished_at": "",
        "message": "",
        "cancel_requested": False,
        "cancel_requested_at": "",
        "selected_steps": list(selected_set),
        "documenti_tipos": list(documenti_tipos or []),
        "documenti_from_mirror": documenti_from_mirror,
        "sync_full": sync_full,
        "steps": steps,
        "counts_before": _sync_4d_counts(),
        "counts_after": {},
        "errors": [],
    }


def _sync_4d_task_snapshot(task_id: str) -> dict | None:
    with _SYNC_4D_LOCK:
        task = _SYNC_4D_TASKS.get(task_id)
        if not task:
            return None
        return {
            **task,
            "steps": [dict(step) for step in task["steps"]],
            "counts_before": dict(task["counts_before"]),
            "counts_after": dict(task["counts_after"]),
            "errors": list(task["errors"]),
        }


def _sync_4d_cancel_requested(task_id: str) -> bool:
    with _SYNC_4D_LOCK:
        task = _SYNC_4D_TASKS.get(task_id)
        return bool(task and task.get("cancel_requested"))


def _run_sync_4d_task(task_id: str) -> None:
    with _SYNC_4D_LOCK:
        task = _SYNC_4D_TASKS[task_id]
        task["status"] = "running"
        task["started_at"] = timezone.now().isoformat()
        selected_keys = task.get("selected_steps") or [s["key"] for s in SYNC_4D_STEPS]
        documenti_tipos = task.get("documenti_tipos") or []
        documenti_from_mirror = task.get("documenti_from_mirror", False)
        sync_full = task.get("sync_full", False)

    selected_specs = [s for s in SYNC_4D_STEPS if s["key"] in selected_keys]
    total = len(selected_specs)
    completed = 0

    try:
        for spec in selected_specs:
            if _sync_4d_cancel_requested(task_id):
                with _SYNC_4D_LOCK:
                    task = _SYNC_4D_TASKS[task_id]
                    step = _sync_4d_step_state(task, spec["key"])
                    if step and step["status"] == "pending":
                        step["status"] = "error"
                        step["message"] = "Interrotto dall'utente."
                    task["status"] = "cancelled"
                    task["current_step"] = ""
                    task["message"] = "Sincronizzazione interrotta dall'utente."
                    task["finished_at"] = timezone.now().isoformat()
                    task["counts_after"] = _sync_4d_counts()
                return

            with _SYNC_4D_LOCK:
                task = _SYNC_4D_TASKS[task_id]
                step = _sync_4d_step_state(task, spec["key"])
                if step:
                    step["status"] = "running"
                task["current_step"] = spec["label"]
                task["progress_pct"] = max(1, int((completed / total) * 100)) if total else 0
                task["message"] = f"Sync {spec['label']} in corso..."

            if spec["key"] == "documenti":
                result = _sync_4d_documenti_step(
                    task_id,
                    tipos=documenti_tipos,
                    from_mirror=documenti_from_mirror,
                    full=sync_full,
                )
            else:
                result = spec["runner"](full=sync_full)
            rows = {table.target: table.rows for table in result.tables}
            # Prefer the aggregated step message (ODBC + optional bridge warning).
            table_messages = "\n".join(
                table.message for table in result.tables if table.message
            )
            step_message = result.message or table_messages

            if _sync_4d_cancel_requested(task_id):
                with _SYNC_4D_LOCK:
                    task = _SYNC_4D_TASKS[task_id]
                    step = _sync_4d_step_state(task, spec["key"])
                    if step:
                        step["status"] = "error"
                        step["message"] = step_message or "Interrotto dall'utente."
                    task["status"] = "cancelled"
                    task["current_step"] = ""
                    task["message"] = "Sincronizzazione interrotta dall'utente."
                    task["finished_at"] = timezone.now().isoformat()
                    task["counts_after"] = _sync_4d_counts()
                return

            with _SYNC_4D_LOCK:
                task = _SYNC_4D_TASKS[task_id]
                step = _sync_4d_step_state(task, spec["key"])
                if step:
                    step["status"] = "done" if result.ok else "error"
                    step["message"] = step_message
                    step["rows"] = rows
                if not result.ok:
                    task["errors"].append(result.message)

            completed += 1
            with _SYNC_4D_LOCK:
                task = _SYNC_4D_TASKS[task_id]
                task["progress_pct"] = int((completed / total) * 100) if total else 100

            if not result.ok:
                with _SYNC_4D_LOCK:
                    task = _SYNC_4D_TASKS[task_id]
                    task["status"] = "error"
                    task["message"] = result.message
                    task["finished_at"] = timezone.now().isoformat()
                    task["counts_after"] = _sync_4d_counts()
                return

        with _SYNC_4D_LOCK:
            task = _SYNC_4D_TASKS[task_id]
            task["status"] = "done"
            task["current_step"] = ""
            task["message"] = "Sincronizzazione 4D completata."
            task["progress_pct"] = 100
            task["finished_at"] = timezone.now().isoformat()
            task["counts_after"] = _sync_4d_counts()
    except Exception as exc:
        logger.exception("Sync 4D task %s fallito", task_id)
        with _SYNC_4D_LOCK:
            task = _SYNC_4D_TASKS.get(task_id)
            if not task:
                return
            if task.get("status") in ("running", "pending"):
                err = f"Errore sync: {exc}"
                step_key = None
                for step in task.get("steps") or []:
                    if step.get("status") == "running":
                        step["status"] = "error"
                        step["message"] = err
                        step_key = step.get("key")
                        break
                task["status"] = "error"
                task["current_step"] = ""
                task["message"] = err
                task["finished_at"] = timezone.now().isoformat()
                task["errors"] = list(task.get("errors") or []) + [err]
                try:
                    task["counts_after"] = _sync_4d_counts()
                except Exception:
                    pass
                if step_key:
                    logger.error("Sync 4D step fallito: %s — %s", step_key, exc)

class SyncAnagraficheView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/sync_anagrafiche.html"

    def get_context(self, last_message: str = ""):
        return {
            "clienti_count": _pg_table_count("clienti"),
            "fornitori_count": _pg_table_count("fornitori"),
            "agenti_count": _pg_table_count("agenti"),
            "last_message": last_message,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        result = sync_clienti_fornitori(full=sync_full_from_request(request))
        message = "\n".join(t.message for t in result.tables) or result.message

        if result.ok:
            messages.success(request, result.message)
        else:
            messages.error(request, result.message)

        return render(
            request,
            self.template_name,
            self.get_context(last_message=message),
        )


class ComandiVocaliListView(
    LoginRequiredMixin, ParametriPermissionMixin, SortableListMixin, PerPageListMixin, ListView
):
    model = ComandoVocale
    template_name = "core/comandi_vocali_list.html"
    context_object_name = "comandi"
    sortable_fields = (
        "ordine",
        "frase",
        "azione",
        "destinazione",
        "query",
        "match_mode",
        "attivo",
    )
    default_sort = "ordine"
    default_dir = "asc"
    sort_tiebreaker = "frase"
    paginate_by = 50

    def get_queryset(self):
        return self.apply_sorting(ComandoVocale.objects.filter(is_active=True))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_query"] = filter_query_from_request(self.request)
        return context


class ComandoVocaleFormView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/comando_vocale_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        if pk is None:
            return None
        return get_object_or_404(ComandoVocale, pk=pk, is_active=True)

    def get_context(self, form=None, obj=None):
        obj = obj if obj is not None else self.get_object()
        return {
            "form": form or ComandoVocaleForm(instance=obj),
            "comando": obj,
            "is_edit": obj is not None,
        }

    def get(self, request, pk=None):
        return render(request, self.template_name, self.get_context())

    def post(self, request, pk=None):
        obj = self.get_object()
        form = ComandoVocaleForm(request.POST, instance=obj)

        if form.is_valid():
            saved = form.save(commit=False)
            if not saved.pk:
                saved.created_by = request.user
            saved.updated_by = request.user
            saved.save()
            messages.success(
                request,
                "Comando vocale aggiornato." if obj else "Comando vocale creato.",
            )
            return redirect("core:comandi_vocali_list")

        return render(request, self.template_name, self.get_context(form=form, obj=obj))


class ComandoVocaleDeleteView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ComandoVocale, pk=pk, is_active=True)
        obj.soft_delete(user=request.user)
        messages.success(request, f'Comando "{obj.frase}" eliminato.')
        return redirect("core:comandi_vocali_list")


class ComandoVocaleDuplicateView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ComandoVocale, pk=pk, is_active=True)
        copy = obj.duplicate(user=request.user)
        messages.success(
            request,
            f'Comando duplicato come "{copy.frase}". Controlla i dettagli e attivalo se necessario.',
        )
        return redirect("core:comando_vocale_edit", pk=copy.pk)


class ConfigurazionePCListView(
    LoginRequiredMixin, ParametriPermissionMixin, SortableListMixin, PerPageListMixin, ListView
):
    model = ConfigurazionePC
    template_name = "core/configurazione_pc_list.html"
    context_object_name = "postazioni"
    sortable_fields = (
        "nome_pc",
        "descrizione",
        "assistente_vocale_attivo",
        "navbar_fissa",
        "liste_fisse",
    )
    default_sort = "nome_pc"
    default_dir = "asc"
    sort_tiebreaker = "nome_pc"
    paginate_by = 20

    def get_queryset(self):
        queryset = ConfigurazionePC.objects.filter(is_active=True)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(nome_pc__icontains=q)
                | Q(descrizione__icontains=q)
                | Q(note__icontains=q)
            )
        return self.apply_sorting(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_query"] = filter_query_from_request(self.request)
        context["nome_pc_rilevato"] = detect_client_pc_name(self.request)
        return context


class ConfigurazionePCCreateView(LoginRequiredMixin, ParametriPermissionMixin, CreateView):
    model = ConfigurazionePC
    form_class = ConfigurazionePCForm
    template_name = "core/configurazione_pc_form.html"

    def get_detected_nome_pc(self):
        return detect_client_pc_name(self.request) or get_nome_pc_from_request(self.request)

    def get(self, request, *args, **kwargs):
        """Se il dispositivo è già identificato, registra in automatico."""
        nome = normalize_nome_pc(self.get_detected_nome_pc())
        auto = (request.GET.get("auto") or "1").strip() != "0"
        if auto and is_valid_pc_name(nome):
            existing = ConfigurazionePC.objects.filter(
                is_active=True, nome_pc__iexact=nome
            ).first()
            if existing:
                response = redirect("core:configurazione_pc_update", pk=existing.pk)
                bind_nome_pc(request, response, existing.nome_pc)
                messages.info(
                    request,
                    f'Postazione "{existing.nome_pc}" già presente: collegata a questo dispositivo.',
                )
                return response

            cfg = register_device_for_request(request, user=request.user)
            if cfg:
                response = redirect("core:configurazione_pc_update", pk=cfg.pk)
                bind_nome_pc(request, response, cfg.nome_pc)
                messages.success(
                    request,
                    f'Postazione "{cfg.nome_pc}" creata automaticamente per questo dispositivo.',
                )
                return response

        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["nome_pc_readonly"] = False
        kwargs["forced_nome_pc"] = ""
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        nome_pc = self.get_detected_nome_pc()
        if nome_pc:
            initial["nome_pc"] = nome_pc
        programma = ConfigurazioneProgramma.get_solo()
        initial.setdefault("assistente_vocale_attivo", programma.assistente_vocale_attivo)
        initial.setdefault("navbar_fissa", programma.navbar_fissa)
        initial.setdefault("liste_fisse", programma.liste_fisse)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        detected = self.get_detected_nome_pc()
        context["nome_pc_rilevato"] = detected
        context["nome_pc_auto"] = True
        context["bind_this_device"] = True
        context["awaiting_device_id"] = not bool(detected)
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        bind_this = (self.request.POST.get("bind_this_device") or "").strip() in {
            "1",
            "on",
            "true",
            "yes",
        }
        if bind_this:
            bind_nome_pc(self.request, response, form.instance.nome_pc)
            messages.success(
                self.request,
                f'Postazione "{form.instance.nome_pc}" creata e collegata a questo dispositivo.',
            )
        else:
            messages.success(self.request, "Postazione PC creata correttamente.")
        return response

    def get_success_url(self):
        return reverse("core:configurazione_pc_list")


class ConfigurazionePCUpdateView(LoginRequiredMixin, ParametriPermissionMixin, UpdateView):
    model = ConfigurazionePC
    form_class = ConfigurazionePCForm
    template_name = "core/configurazione_pc_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["nome_pc_readonly"] = True
        return kwargs

    def get_queryset(self):
        return ConfigurazionePC.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nome_pc_auto"] = False
        context["bind_this_device"] = True
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        bind_this = (self.request.POST.get("bind_this_device") or "").strip() in {
            "1",
            "on",
            "true",
            "yes",
        }
        if bind_this:
            bind_nome_pc(self.request, response, form.instance.nome_pc)
            messages.success(
                self.request,
                f'Postazione aggiornata e collegata a questo dispositivo.',
            )
        else:
            messages.success(self.request, "Postazione PC aggiornata correttamente.")
        return response

    def get_success_url(self):
        return reverse("core:configurazione_pc_list")


class ConfigurazionePCBindView(LoginRequiredMixin, ParametriPermissionMixin, View):
    """Collega la postazione scelta a questo browser/dispositivo (cookie)."""

    def post(self, request, *args, **kwargs):
        postazione = get_object_or_404(ConfigurazionePC, pk=kwargs["pk"], is_active=True)
        response = redirect("core:configurazione_pc_list")
        bind_nome_pc(request, response, postazione.nome_pc)
        messages.success(
            request,
            f'Questo dispositivo usa ora la postazione "{postazione.nome_pc}".',
        )
        return response


class ConfigurazionePCDeleteView(LoginRequiredMixin, ParametriPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        postazione = get_object_or_404(ConfigurazionePC, pk=kwargs["pk"], is_active=True)
        postazione.soft_delete(user=request.user)
        messages.success(request, "Postazione PC eliminata correttamente.")
        return redirect("core:configurazione_pc_list")


class OfflineHubView(LoginRequiredMixin, View):
    """Hub sync SQLite locale + classifica offline (iPad)."""

    template_name = "core/offline.html"

    def get(self, request, *args, **kwargs):
        from apps.core.offline import default_from_date, offline_meta

        meta = offline_meta()
        return render(
            request,
            self.template_name,
            {
                "offline_meta": meta,
                "from_date": meta["from_date"],
                "default_from": default_from_date().isoformat(),
            },
        )


class OfflineSyncApiView(LoginRequiredMixin, View):
    """API chunked: dataset=meta|clienti|fatture|geo."""

    def get(self, request, *args, **kwargs):
        from apps.core.offline import sync_chunk_response

        return sync_chunk_response(request)


class CarbonHubView(LoginRequiredMixin, View):
    """Hub verso la dashboard CARBON (seriali per reparto)."""

    template_name = "core/carbon.html"

    def get(self, request, *args, **kwargs):
        from django.conf import settings

        carbon_url = (getattr(settings, "CARBON_URL", "") or "").strip()
        return render(
            request,
            self.template_name,
            {"carbon_url": carbon_url},
        )


class ServiceWorkerView(View):
    """Serve sw.js dalla root (scope /). Login non richiesto: asset pubblico."""

    def get(self, request, *args, **kwargs):
        path = finders.find("eureka/js/sw.js")
        if not path:
            raise Http404("service worker non trovato")
        response = FileResponse(open(path, "rb"), content_type="application/javascript")
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class HelperOpenApiView(LoginRequiredMixin, View):
    """Proxy verso l'helper locale: apre il file col programma predefinito."""

    def post(self, request, *args, **kwargs):
        import base64
        import json

        from apps.core.open_helper import friendly_error, open_file

        try:
            data = json.loads(request.body.decode("utf-8"))
            filename = (data.get("filename") or "export.bin").strip()
            content = base64.b64decode(data.get("content_b64") or "")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({"ok": False, "error": "Payload non valido"}, status=400)

        try:
            result = open_file(filename, content)
            return JsonResponse(result)
        except RuntimeError as exc:
            return JsonResponse({"ok": False, "error": friendly_error(str(exc))}, status=503)
        except Exception as exc:
            return JsonResponse({"ok": False, "error": friendly_error(str(exc))}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AiAssistantView(View):
    """Endpoint API per l'assistente AI."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False, "errore": "Accesso non autorizzato."}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        import json as _json
        from apps.core.ai_assistant import ask_ai

        try:
            body = _json.loads(request.body.decode("utf-8"))
            prompt = (body.get("prompt") or "").strip()
        except (ValueError, TypeError):
            return JsonResponse({"ok": False, "errore": "Payload non valido."}, status=400)

        if not prompt:
            return JsonResponse({"ok": False, "errore": "Richiesta vuota."}, status=400)

        limit = body.get("limit", 200)
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 200
        if limit < 1:
            limit = 200

        result = ask_ai(prompt, limit=limit)
        link = result.pop("link", None)
        table = result.pop("table", None)

        if link and result.get("risultati"):
            from django.urls import reverse, NoReverseMatch
            url_name = link["url_name"]
            pk_col = link["pk_column"]
            pk_param = link.get("pk_param", "pk")
            urls = {}
            pk_list = []
            for row in result["risultati"]:
                pk_val = row.get(pk_col)
                if pk_val is None:
                    continue
                pk_str = str(pk_val).strip()
                if not pk_str:
                    continue
                pk_list.append(pk_str)
                if pk_str not in urls:
                    try:
                        urls[pk_str] = reverse(url_name, kwargs={pk_param: pk_str})
                    except (NoReverseMatch, ValueError, TypeError):
                        pass
            if urls:
                result["detail_urls"] = urls
                result["detail_pk_column"] = pk_col

            from apps.core.ai_assistant import TABLE_LIST_ROUTES
            if table and table in TABLE_LIST_ROUTES and pk_list:
                ai_token = store_ai_filter(request, table=table, pks=pk_list)
                try:
                    result["list_url"] = (
                        reverse(TABLE_LIST_ROUTES[table]) + f"?ai=1&ai_token={ai_token}"
                    )
                except (NoReverseMatch, ValueError):
                    pass

        status = 200 if result.get("ok") else 422
        return JsonResponse(result, status=status)


class HelperShareApiView(LoginRequiredMixin, View):
    """Proxy verso l'helper locale: apre la maschera Condividi di Windows."""

    def post(self, request, *args, **kwargs):
        import base64
        import json

        from apps.core.open_helper import friendly_error, share_file

        try:
            data = json.loads(request.body.decode("utf-8"))
            filename = (data.get("filename") or "export.bin").strip()
            content = base64.b64decode(data.get("content_b64") or "")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({"ok": False, "error": "Payload non valido"}, status=400)

        try:
            result = share_file(filename, content)
            return JsonResponse(result)
        except RuntimeError as exc:
            return JsonResponse({"ok": False, "error": friendly_error(str(exc))}, status=503)
        except Exception as exc:
            return JsonResponse({"ok": False, "error": friendly_error(str(exc))}, status=500)
