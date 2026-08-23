from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.dashboard",
    "apps.fatture",
    "apps.documenti",
    "apps.anagrafiche",
    "apps.articoli",
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
    "apps.core.middleware.BindClientPcMiddleware",
]

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

# Groq (solo se AI_BACKEND=groq) — API key gratuita da https://console.groq.com/
GROQ_API_KEY = env("GROQ_API_KEY", default="")
GROQ_MODEL = env("GROQ_MODEL", default="groq/compound-mini")
# Cap massimo dei token in uscita per velocizzare le risposte Groq e risparmiare quota TPD.
# Puoi sovrascriverlo via env var GROQ_MAX_TOKENS.
GROQ_MAX_TOKENS = env("GROQ_MAX_TOKENS", default=550)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/admin/login/"

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
    CSRF_COOKIE_HTTPONLY = True
