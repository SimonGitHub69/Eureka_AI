from functools import wraps

from django.core.exceptions import PermissionDenied

from apps.core.programma import is_documento_menu_enabled, is_extra_enabled


class RequireDocumentoMenuMixin:
    """Blocca l'accesso se il tipo documento non è abilitato nei parametri programma."""

    documento_menu_codice: str = ""

    def dispatch(self, request, *args, **kwargs):
        codice = self.documento_menu_codice or kwargs.get("tipo_doc", "").upper()
        if codice and not is_documento_menu_enabled(codice):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class RequireExtraMixin:
    """Blocca l'accesso se la personalizzazione extra non è abilitata."""

    extra_codice: str = "CARBON"

    def dispatch(self, request, *args, **kwargs):
        if not is_extra_enabled(self.extra_codice):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def require_extra(codice: str = "CARBON"):
    """Decorator per view-function: stesso controllo di RequireExtraMixin."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not is_extra_enabled(codice):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
