"""Binding postazione PC da querystring (?pc=NOME), cookie o COMPUTERNAME locale."""

from apps.core.pc import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    SESSION_KEY,
    _is_request_from_this_machine,
    get_local_system_pc_name,
    is_valid_pc_name,
    normalize_nome_pc,
    normalize_remote_ip,
)
from apps.core.open_helper import ensure_started as _ensure_open_helper_started


class BindClientPcMiddleware:
    """
    Associa la richiesta al nome postazione corretto:
    - PC Windows server/locale → COMPUTERNAME
    - iPad/browser remoto → cookie/query ?pc= (es. IPAD-XXXX)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _ensure_open_helper_started()
        from_query = normalize_nome_pc(
            request.GET.get("pc") or request.GET.get("nome_pc") or ""
        )
        set_cookie_name = ""
        clear_cookie = False

        remote = normalize_remote_ip(request.META.get("REMOTE_ADDR"))
        local_name = ""
        if _is_request_from_this_machine(remote):
            local_name = get_local_system_pc_name()

        if local_name:
            # Sul PC che esegue Eureka i parametri devono seguire il nome macchina
            request.session[SESSION_KEY] = local_name
            set_cookie_name = local_name
        elif is_valid_pc_name(from_query):
            request.session[SESSION_KEY] = from_query
            set_cookie_name = from_query
        else:
            cookie_val = normalize_nome_pc(request.COOKIES.get(COOKIE_NAME))
            session_val = normalize_nome_pc(request.session.get(SESSION_KEY))

            if cookie_val and is_valid_pc_name(cookie_val):
                if session_val != cookie_val:
                    request.session[SESSION_KEY] = cookie_val
            elif cookie_val and not is_valid_pc_name(cookie_val):
                clear_cookie = True

            if session_val and not is_valid_pc_name(session_val):
                request.session.pop(SESSION_KEY, None)

        response = self.get_response(request)

        if set_cookie_name:
            response.set_cookie(
                COOKIE_NAME,
                set_cookie_name,
                max_age=COOKIE_MAX_AGE,
                samesite="Lax",
                httponly=False,
            )
        elif clear_cookie:
            response.delete_cookie(COOKIE_NAME)

        return response
