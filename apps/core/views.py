from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView

from django.db import connection

from apps.core.forms import ComandoVocaleForm, Configurazione4DForm
from apps.core.models import ComandoVocale, Configurazione4D
from apps.core.pagination import PerPageListMixin, filter_query_from_request
from apps.core.quattro_d import config_from_post, test_4d_connection
from apps.core.sync_anagrafiche import sync_clienti_fornitori


class ParametriPermissionMixin(PermissionRequiredMixin):
    permission_required = "core.access_parametri_4d"
    raise_exception = True


class Parametri4DView(LoginRequiredMixin, ParametriPermissionMixin, View):
    template_name = "core/configurazione_4d_form.html"
    success_url = reverse_lazy("core:parametri_4d")

    def get_context(self, form=None):
        return {
            "form": form
            or Configurazione4DForm(instance=Configurazione4D.get_solo()),
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


def _pg_table_count(table: str) -> int:
    try:
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            return cur.fetchone()[0]
    except Exception:
        return 0


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
