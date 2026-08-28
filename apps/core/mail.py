"""Helper SMTP da ParametriMail (invio automatico)."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from smtplib import SMTPAuthenticationError, SMTPConnectError, SMTPException
from typing import Sequence
from urllib.parse import urlparse

from django.core.mail import EmailMessage, get_connection

from apps.core.models import ParametriMail


@dataclass
class MailTestResult:
    ok: bool
    message: str


def get_parametri_mail() -> ParametriMail:
    return ParametriMail.get_solo()


def parse_address_list(raw: str | None) -> list[str]:
    text = (raw or "").replace(";", ",")
    return [p.strip() for p in text.split(",") if p.strip()]


def normalize_smtp_host(raw: str | None) -> tuple[str, int | None]:
    """Estrae hostname (e porta opzionale) da un valore incollato in maschera.

    Accetta ``smtp.gmail.com``, ``smtp.gmail.com:587``, ``smtp://host:465``.
    """
    text = (raw or "").strip().strip("/")
    if not text:
        return "", None

    if "://" in text:
        parsed = urlparse(text)
        host = (parsed.hostname or "").strip()
        return host, parsed.port

    if text.startswith("[") and "]:" in text:
        host, port_s = text.rsplit(":", 1)
        host = host.strip("[]")
        if port_s.isdigit():
            return host, int(port_s)
        return text.strip("[]"), None

    if text.count(":") == 1:
        host, port_s = text.rsplit(":", 1)
        if port_s.isdigit() and host and "@" not in host:
            return host.strip(), int(port_s)

    return text, None


def describe_mail_error(exc: BaseException, *, host: str = "") -> str:
    """Messaggio operatore per errori SMTP (DNS, autenticazione, TLS, …)."""
    shown = (host or "").strip() or "indicato"
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        errno = getattr(current, "errno", None)
        if isinstance(current, socket.gaierror) or errno in (11001, 11002, 11004, -2, 8):
            return (
                f"Impossibile trovare il server SMTP «{shown}» "
                "(nome host non valido o non risolto dalla rete). "
                "Inserisci solo l'hostname, ad esempio smtp.gmail.com, "
                "senza http:// e senza la porta nel nome."
            )
        if isinstance(current, TimeoutError) or errno in (110, 10060):
            return (
                f"Timeout verso il server SMTP «{shown}». "
                "Controlla host, porta, STARTTLS/SSL e il firewall."
            )
        if isinstance(current, ConnectionRefusedError) or errno in (111, 10061):
            return (
                f"Connessione rifiutata dal server SMTP «{shown}». "
                "Verifica la porta (587 STARTTLS o 465 SSL)."
            )
        if isinstance(current, SMTPAuthenticationError):
            return (
                "Autenticazione SMTP non riuscita: controlla utente e password "
                "(su Gmail/Microsoft serve una password per le app)."
            )
        if isinstance(current, (SMTPConnectError, ssl.SSLError)):
            return (
                f"Connessione TLS/SSL non riuscita verso «{shown}». "
                "Prova porta 587 con STARTTLS, oppure 465 con SSL/TLS (non entrambi)."
            )
        current = current.__cause__ or current.__context__

    if isinstance(exc, SMTPException):
        return f"Prova invio non riuscita: {exc}"
    return f"Prova invio non riuscita: {exc}"


def build_email_connection(cfg: ParametriMail | None = None):
    """Restituisce una connessione Django SMTP basata sui parametri salvati."""
    cfg = cfg or get_parametri_mail()
    host, port_from_host = normalize_smtp_host(cfg.server_smtp)
    port = port_from_host if port_from_host else int(cfg.porta or 587)
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=host,
        port=port,
        username=(cfg.utente or "").strip() or None,
        password=cfg.password or None,
        use_tls=bool(cfg.usa_tls),
        use_ssl=bool(cfg.usa_ssl),
        timeout=int(cfg.timeout_secondi or 30),
        fail_silently=False,
    )


def send_mail_automatica(
    *,
    subject: str,
    body: str,
    to: Sequence[str],
    cc: Sequence[str] | None = None,
    bcc: Sequence[str] | None = None,
    html: bool = False,
    cfg: ParametriMail | None = None,
    force: bool = False,
    attachments: Sequence[tuple[str, bytes | str, str]] | None = None,
) -> None:
    """Invia una email usando i Parametri mail.

    Se ``force=True`` (prova dalla maschera), ignora il flag ``attiva``.
    """
    cfg = cfg or get_parametri_mail()
    if not force and not cfg.attiva:
        raise RuntimeError("L'invio mail automatico è disattivato nei Parametri mail.")
    mittente = cfg.mittente_completo()
    if not mittente:
        raise RuntimeError("Email mittente non configurata nei Parametri mail.")
    host, _port = normalize_smtp_host(cfg.server_smtp)
    if not host:
        raise RuntimeError("Server SMTP non configurato nei Parametri mail.")

    recipients = [a for a in to if a]
    if not recipients:
        raise RuntimeError("Nessun destinatario indicato.")

    bcc_list = list(bcc or [])
    bcc_list.extend(parse_address_list(cfg.copia_nascosta))

    headers = {}
    reply = (cfg.reply_to or "").strip()
    if reply:
        headers["Reply-To"] = reply

    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=mittente,
        to=recipients,
        cc=list(cc or []),
        bcc=bcc_list,
        connection=build_email_connection(cfg),
        headers=headers or None,
    )
    if html:
        msg.content_subtype = "html"
    for item in attachments or []:
        filename, content, mimetype = item
        msg.attach(filename, content, mimetype)
    msg.send(fail_silently=False)


def test_mail_connection(cfg: ParametriMail | None = None) -> MailTestResult:
    """Prova connessione SMTP inviando una mail di test (anche se attiva=False)."""
    cfg = cfg or get_parametri_mail()
    host, _port = normalize_smtp_host(cfg.server_smtp)
    if not host:
        return MailTestResult(False, "Inserisci il server SMTP.")
    if "@" in host:
        return MailTestResult(
            False,
            "Nel campo Server SMTP inserisci l'hostname (es. smtp.gmail.com), "
            "non un indirizzo email.",
        )
    mittente = (cfg.mittente or "").strip()
    if not mittente:
        return MailTestResult(False, "Inserisci l'email mittente.")
    if cfg.usa_tls and cfg.usa_ssl:
        return MailTestResult(
            False,
            "Non è possibile usare insieme STARTTLS e SSL/TLS: scegline uno.",
        )

    dest = (cfg.email_test or "").strip() or mittente
    try:
        send_mail_automatica(
            subject="Eureka AI — prova invio mail",
            body=(
                "Questa è una email di prova inviata da Eureka AI.\n\n"
                "Se la ricevi, i Parametri mail sono configurati correttamente."
            ),
            to=[dest],
            cfg=cfg,
            force=True,
        )
    except Exception as exc:
        return MailTestResult(False, describe_mail_error(exc, host=host))

    extra = ""
    if not cfg.attiva:
        extra = " (L'invio automatico resta disattivato finché non attivi l'opzione.)"
    return MailTestResult(True, f"Email di prova inviata a {dest}.{extra}")
