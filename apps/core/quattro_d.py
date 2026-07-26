from contextlib import contextmanager
from dataclasses import dataclass

from apps.core.models import Configurazione4D

ODBC_DRIVERS = (
    "4D ODBC Driver 64-bit",
    "4D ODBC Driver x64",
    "4D ODBC Driver 32-bit",
    "4D ODBC Driver",
)


@dataclass
class QuattroDTestResult:
    ok: bool
    message: str
    driver: str = ""


def get_4d_config():
    return Configurazione4D.get_solo()


def config_from_post(post, instance=None):
    instance = instance or Configurazione4D.get_solo()
    if not post:
        return instance

    password = (post.get("password") or "").strip()
    porta_raw = (post.get("porta") or "").strip()

    try:
        porta = int(porta_raw) if porta_raw else instance.porta
    except ValueError:
        porta = instance.porta

    return Configurazione4D(
        attiva=post.get("attiva") == "on",
        server=(post.get("server") or "").strip() or instance.server,
        porta=porta or 19812,
        utente=(post.get("utente") or "").strip() or instance.utente,
        password=password or instance.password,
        driver_odbc=(post.get("driver_odbc") or "").strip() or instance.driver_odbc,
        usa_ssl=post.get("usa_ssl") == "on",
        dsn=(post.get("dsn") or "").strip() or instance.dsn,
        note=(post.get("note") or "").strip() or instance.note,
    )


def escape_odbc_value(value):
    if value is None:
        return ""
    text = str(value)
    if any(char in text for char in (";", "{", "}", "=")):
        return "{" + text.replace("}", "}}") + "}"
    return text


def get_available_odbc_drivers(preferred=""):
    try:
        import pyodbc
    except ImportError:
        return []

    installed = pyodbc.drivers()
    preferred = (preferred or "").strip()
    if preferred and preferred in installed:
        return [preferred]

    known = [driver for driver in ODBC_DRIVERS if driver in installed]
    if known:
        return known

    return [driver for driver in installed if "4d" in driver.lower()]


def build_odbc_connection_string(config, driver):
    dsn = (config.dsn or "").strip()
    if dsn:
        parts = [f"DSN={escape_odbc_value(dsn)}"]
        utente = (config.utente or "").strip()
        if utente:
            parts.append(f"UID={escape_odbc_value(utente)}")
            parts.append(f"PWD={escape_odbc_value(config.password or '')}")
        return ";".join(parts) + ";"

    parts = [
        f"DRIVER={{{driver}}}",
        f"Server={escape_odbc_value((config.server or '').strip())}",
        f"Port={config.porta or 19812}",
        f"UID={escape_odbc_value((config.utente or '').strip())}",
        f"PWD={escape_odbc_value(config.password or '')}",
    ]
    if config.usa_ssl:
        parts.append("SSL=true")
    return ";".join(parts) + ";"


def format_4d_error(driver, error_text):
    normalized = (error_text or "").lower()

    if "login" in normalized or "password" in normalized or "authentication" in normalized:
        return "Accesso negato da 4D: utente o password non validi."

    if any(
        marker in normalized
        for marker in (
            "unable to establish",
            "impossibile",
            "timeout",
            "timed out",
            "network",
            "connection refused",
            "sql server",
        )
    ):
        return (
            "Server 4D non raggiungibile. Verifica host, porta SQL (default 19812), "
            "firewall e che il SQL Server di 4D sia avviato "
            f"(driver: {driver})."
        )

    return f"{driver}: {error_text}"


@contextmanager
def open_4d_connection(config=None, timeout=5):
    config = config or get_4d_config()
    if not config.attiva or not config.is_configured:
        raise RuntimeError("Collegamento 4D non attivo o incompleto.")

    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("Modulo pyodbc non installato.") from exc

    drivers_to_try = get_available_odbc_drivers(config.driver_odbc)
    if not drivers_to_try and not (config.dsn or "").strip():
        raise RuntimeError(
            "Nessun driver ODBC 4D trovato. Installa '4D ODBC Driver 64-bit' "
            "oppure configura un DSN."
        )

    if (config.dsn or "").strip():
        drivers_to_try = drivers_to_try or [""]

    errors = []
    for driver in drivers_to_try:
        try:
            connection_string = build_odbc_connection_string(config, driver)
            connection = pyodbc.connect(connection_string, timeout=timeout)
            try:
                yield connection
            finally:
                connection.close()
            return
        except Exception as exc:
            errors.append((driver or "DSN", str(exc)))

    driver, error_text = errors[0]
    raise RuntimeError(format_4d_error(driver, error_text))


def test_4d_connection(config=None, timeout=5):
    config = config or get_4d_config()

    if not config.is_configured:
        if (config.dsn or "").strip():
            msg = "Compila almeno il DSN."
        else:
            msg = "Compila server, utente e password, oppure indica un DSN."
        return QuattroDTestResult(ok=False, message=msg)

    try:
        import pyodbc
    except ImportError:
        return QuattroDTestResult(
            ok=False,
            message="Modulo pyodbc non installato. Esegui: pip install pyodbc",
        )

    drivers = get_available_odbc_drivers(config.driver_odbc)
    using_dsn = bool((config.dsn or "").strip())

    if not drivers and not using_dsn:
        return QuattroDTestResult(
            ok=False,
            message=(
                "Nessun driver ODBC 4D installato. "
                "Installa '4D ODBC Driver 64-bit' oppure configura un DSN di sistema."
            ),
        )

    if using_dsn and not drivers:
        drivers = [""]

    errors = []
    for driver in drivers:
        try:
            connection_string = build_odbc_connection_string(config, driver)
            connection = pyodbc.connect(connection_string, timeout=timeout)
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            except Exception:
                # Alcune versioni 4D non accettano SELECT 1: la connessione resta valida.
                pass
            connection.close()

            target = (
                f"DSN {config.dsn}"
                if using_dsn
                else f"{config.server}:{config.porta or 19812}"
            )
            driver_label = driver or "DSN"
            return QuattroDTestResult(
                ok=True,
                message=f"Connessione riuscita a {target} ({driver_label}).",
                driver=driver_label,
            )
        except Exception as exc:
            errors.append((driver or "DSN", str(exc)))

    driver, error_text = errors[0]
    return QuattroDTestResult(
        ok=False,
        message=format_4d_error(driver, error_text),
        driver=driver,
    )
