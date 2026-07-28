import threading
import uuid

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

from apps.core.forms import (
    ComandoVocaleForm,
    Configurazione4DForm,
    ConfigurazionePCForm,
    ConfigurazioneProgrammaForm,
)
from apps.core.models import (
    ComandoVocale,
    Configurazione4D,
    ConfigurazionePC,
    ConfigurazioneProgramma,
)
from apps.core.pagination import PerPageListMixin, filter_query_from_request
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
from apps.core.sync_anagrafiche import sync_clienti_fornitori
from apps.categorie.sync import sync_categorie
from apps.condizioni.sync import sync_condizioni
from apps.aziende.sync import sync_aziende
from apps.fatture.sync import sync_fatture
from apps.gruppi_articoli.sync import sync_gruppi_articoli
from apps.gruppi_magazzini.sync import sync_gruppi_magazzini
from apps.magazzini.sync import sync_magazzini
from apps.carbon.sync import sync_carbon
from apps.lavorazioni_extra.sync import sync_lavorazioni_extra
from apps.stampi.sync import sync_stampi
from apps.articoli.sync import sync_articoli
from apps.operatori.sync import sync_operatori
from apps.timbrature.sync import sync_timbrature


SYNC_4D_STEPS = (
    {
        "key": "anagrafiche",
        "label": "Anagrafiche",
        "description": "Clienti, Fornitori, Agenti",
        "runner": sync_clienti_fornitori,
        "tables": ("clienti", "fornitori", "agenti"),
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
        "label": "Condizioni",
        "description": "CondizioniPag",
        "runner": sync_condizioni,
        "tables": ("condizioni",),
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
        "key": "gruppi_magazzini",
        "label": "Raggruppamenti magazzini",
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
        "key": "fatture",
        "label": "Fatture",
        "description": "Fatture e Fatture_Dettaglio",
        "runner": sync_fatture,
        "tables": ("fatture", "fatture_dettaglio"),
    },
)

_SYNC_4D_TASKS: dict[str, dict] = {}
_SYNC_4D_LOCK = threading.Lock()

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
        form = ConfigurazioneProgrammaForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            if not obj.created_by:
                obj.created_by = request.user
            obj.save()
            messages.success(request, "Parametri programma salvati correttamente.")
            return redirect(self.success_url)
        return render(request, self.template_name, self.get_context(form=form))


class Parametri4DView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/configurazione_4d_form.html"
    success_url = reverse_lazy("core:parametri_4d")

    def get_context(self, form=None):
        sync_counts = _sync_4d_counts()
        sync_steps = [
            {
                "key": step["key"],
                "label": step["label"],
                "description": step["description"],
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
        with _SYNC_4D_LOCK:
            running = next(
                (task for task in _SYNC_4D_TASKS.values() if task["status"] == "running"),
                None,
            )
            if running:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Sincronizzazione già in corso.",
                        "task_id": running["id"],
                    },
                    status=409,
                )
            task = _new_sync_4d_task(request.user)
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
        snapshot = _sync_4d_task_snapshot(task_id)
        if not snapshot:
            return JsonResponse({"ok": False, "error": "Task non trovato."}, status=404)
        return JsonResponse({"ok": True, "task": snapshot})


class Sync4DClearView(LoginRequiredMixin, ParametriPermissionMixin, View):
    """Azzera tutte le tabelle mirror PostgreSQL importate da 4D."""

    def post(self, request, *args, **kwargs):
        with _SYNC_4D_LOCK:
            running = next(
                (task for task in _SYNC_4D_TASKS.values() if task["status"] == "running"),
                None,
            )
            if running:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Impossibile azzerare: sincronizzazione in corso.",
                        "task_id": running["id"],
                    },
                    status=409,
                )

        counts_before = {table: _pg_table_count(table) for table in MIRROR_4D_TABLES}
        cleared, errors = _clear_mirror_4d_tables()
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
                "message": f"Azzerate {len(cleared)} tabelle mirror PostgreSQL.",
                "cleared": cleared,
                "counts_before": counts_before,
                "counts_after": counts_after,
            }
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


def _new_sync_4d_task(user) -> dict:
    steps = [
        {
            "key": spec["key"],
            "label": spec["label"],
            "description": spec["description"],
            "status": "pending",
            "message": "",
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
        "started_at": "",
        "finished_at": "",
        "message": "",
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


def _run_sync_4d_task(task_id: str) -> None:
    total = len(SYNC_4D_STEPS)
    with _SYNC_4D_LOCK:
        task = _SYNC_4D_TASKS[task_id]
        task["status"] = "running"
        task["started_at"] = timezone.now().isoformat()
    completed = 0

    for index, spec in enumerate(SYNC_4D_STEPS):
        with _SYNC_4D_LOCK:
            task = _SYNC_4D_TASKS[task_id]
            step = task["steps"][index]
            step["status"] = "running"
            task["current_step"] = spec["label"]
            task["progress_pct"] = max(1, int((completed / total) * 100))
            task["message"] = f"Sync {spec['label']} in corso..."

        result = spec["runner"]()
        rows = {table.target: table.rows for table in result.tables}
        step_message = "\n".join(table.message for table in result.tables) or result.message

        with _SYNC_4D_LOCK:
            task = _SYNC_4D_TASKS[task_id]
            step = task["steps"][index]
            step["status"] = "done" if result.ok else "error"
            step["message"] = step_message
            step["rows"] = rows
            if not result.ok:
                task["errors"].append(result.message)

        completed += 1
        with _SYNC_4D_LOCK:
            task = _SYNC_4D_TASKS[task_id]
            task["progress_pct"] = int((completed / total) * 100)

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
        result = sync_clienti_fornitori()
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


class ComandiVocaliListView(LoginRequiredMixin, ParametriPermissionMixin, PerPageListMixin, ListView):
    model = ComandoVocale
    template_name = "core/comandi_vocali_list.html"
    context_object_name = "comandi"
    paginate_by = 50

    def get_queryset(self):
        return ComandoVocale.objects.filter(is_active=True).order_by("ordine", "frase")

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


class ConfigurazionePCListView(LoginRequiredMixin, ParametriPermissionMixin, PerPageListMixin, ListView):
    model = ConfigurazionePC
    template_name = "core/configurazione_pc_list.html"
    context_object_name = "postazioni"
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
        return queryset.order_by("nome_pc")

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
