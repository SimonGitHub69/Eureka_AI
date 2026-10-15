from pathlib import Path
import json
import socket
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])


def _csrf_origins_from_hosts(hosts: list[str]) -> list[str]:
    """Origini CSRF tipiche per accesso locale/LAN (Django 4+ richiede lo schema)."""
    ports = ("8000", "8443")
    out: list[str] = []
    seen: set[str] = set()
    for host in hosts:
        h = (host or "").strip().strip("[]")
        if not h or h == "*":
            continue
        for scheme in ("http", "https"):
            for port in ports:
                origin = f"{scheme}://{h}:{port}"
                if origin not in seen:
                    seen.add(origin)
                    out.append(origin)
    return out


def _discover_lan_hosts() -> list[str]:
    """Hostname .local + IP LAN attuali (DHCP: ricalcolati a ogni avvio del processo)."""
    found: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        h = (value or "").strip().strip("[]")
        if not h or h in seen or h == "*":
            return
        seen.add(h)
        found.append(h)

    try:
        short = socket.gethostname().split(".")[0].strip()
        if short:
            add(short)
            add(f"{short}.local")
    except Exception:
        pass

    try:
        # Non invia traffico: rivela l'IP della rotta di default (tipico Wi‑Fi LAN).
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            add(ip)
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                add(ip)
    except Exception:
        pass

    return found


CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not CSRF_TRUSTED_ORIGINS:
    # Server Mac / installazioni minime: senza questa lista i POST falliscono (403 CSRF).
    CSRF_TRUSTED_ORIGINS = _csrf_origins_from_hosts(ALLOWED_HOSTS)

# Token CSRF in sessione (non in cookie separato): evita 403 "CSRF cookie not set"
# su Safari / client Mac quando il cookie csrftoken non viene accettato.
CSRF_USE_SESSIONS = True

# LAN / DHCP: a ogni avvio Waitress aggiunge IP e nome.local correnti
# (altrimenti i client Mac vedono Bad Request 400 / 403 CSRF quando l'IP Wi‑Fi cambia).
# Anche con ALLOWED_HOSTS=* bisogna aggiornare CSRF_TRUSTED_ORIGINS: Django 4+
# richiede l'origine esatta (schema+host+porta), il wildcard non basta.
if env.bool("EUREKA_AUTO_LAN_HOSTS", default=True):
    _lan = _discover_lan_hosts()
    if "*" not in ALLOWED_HOSTS:
        for _h in _lan:
            if _h not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append(_h)
    for _origin in _csrf_origins_from_hosts(_lan):
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)



def _read_app_version() -> str:
    pkg = BASE_DIR / "package.json"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        ver = str(data.get("version") or "").strip()
        if ver:
            return ver
    except Exception:
        pass
    return "1.0.45"


EUREKA_VERSION = env("EUREKA_VERSION", default=_read_app_version())
# Logout automatico alla chiusura finestra: OFF di default.
# Su Mac (Chrome --app / Safari) pagehide scatta anche al cambio menu e
# invalidava la sessione. Attivare solo se serve davvero: EUREKA_LOGOUT_ON_CLOSE=1
EUREKA_LOGOUT_ON_CLOSE = env.bool("EUREKA_LOGOUT_ON_CLOSE", default=False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core.apps.CoreConfig",
    "apps.dashboard",
    "apps.fatture",
    "apps.documenti",
    "apps.anagrafiche",
    "apps.articoli",
    "apps.set_articoli",
    "apps.distinte_base",
    "apps.categorie",
    "apps.condizioni",
    "apps.aliquote",
    "apps.registri_iva",
    "apps.banche",
    "apps.sconti",
    "apps.valute",
    "apps.zone",
    "apps.vettori",
    "apps.causali_trasp",
    "apps.destinazioni",
    "apps.aziende",
    "apps.gruppi_articoli",
    "apps.gruppi_magazzini",
    "apps.magazzini",
    "apps.depositi",
    "apps.causali_magazzino",
    "apps.movimenti",
    "apps.stampi",
    "apps.operatori",
    "apps.timbrature",
    "apps.schede_lavorazione",
    "apps.agenda",
    "apps.carbon",
    "apps.lavorazioni_extra",
    "apps.geografia",
    "apps.pdc",
    "apps.primanota",
    "apps.causali_contabili",
    "apps.raggruppamento_conti",
    "apps.raggruppamento_clifor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.PreserveEmbedMiddleware",
    "apps.core.middleware.BindClientPcMiddleware",
    "apps.core.middleware.PostLoginAppRedirectMiddleware",
]

# Consenti iframe same-origin (multi-finestra)
X_FRAME_OPTIONS = "SAMEORIGIN"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.voice_commands",
                "apps.core.context_processors.integrations",
                "apps.core.context_processors.programma_documenti",
                "apps.core.context_processors.ai_debug_flags",
                "apps.core.context_processors.list_back",
                "apps.core.context_processors.app_version",
                "apps.core.context_processors.sync_prompt",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("LANGUAGE_CODE", default="it-it")
TIME_ZONE = env("TIME_ZONE", default="Europe/Rome")

USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
# In sviluppo: servi anche da STATICFILES_DIRS (junction static/vendor → node_modules)
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=True)

# Dashboard produzione CARBON (app separata)
CARBON_URL = env("CARBON_URL", default="http://127.0.0.1:8001/").strip()

# AI Assistant — "ollama" (locale, gratuito), "openai" oppure "groq"
AI_BACKEND = env("AI_BACKEND", default="groq")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini")
OLLAMA_URL = env("OLLAMA_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="qwen2.5:3b")
# Timeout (secondi) per fallback Groq -> Ollama su rate limit / TPD.
OLLAMA_FALLBACK_TIMEOUT = env("OLLAMA_FALLBACK_TIMEOUT", default=5)

# Groq (solo se AI_BACKEND=groq) — API key gratuita da https://console.groq.com/
GROQ_API_KEY = env("GROQ_API_KEY", default="")
GROQ_MODEL = env("GROQ_MODEL", default="groq/compound-mini")
# Cap massimo dei token in uscita per velocizzare le risposte Groq e risparmiare quota TPD.
# Puoi sovrascriverlo via env var GROQ_MAX_TOKENS.
GROQ_MAX_TOKENS = env("GROQ_MAX_TOKENS", default=550)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/uscita/"

from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SESSION_COOKIE_HTTPONLY = True
    # Con CSRF_USE_SESSIONS il cookie csrftoken non è usato per la verifica;
    # resta leggibile da JS dove serve (meta/header), senza bloccare il login.
    CSRF_COOKIE_HTTPONLY = False
