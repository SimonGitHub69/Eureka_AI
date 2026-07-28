"""Avvia Eureka in HTTPS (necessario per service worker / offline su iPad)."""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERT_FILE = ROOT / "certs" / "eureka-local.pem"
KEY_FILE = ROOT / "certs" / "eureka-local-key.pem"
HOST = os.environ.get("EUREKA_HTTPS_HOST", "0.0.0.0")
PORT = int(os.environ.get("EUREKA_HTTPS_PORT", "8443"))


def main() -> None:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("Certificati mancanti. Esegui: python scripts/gen_https_cert.py")
        sys.exit(1)

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.servers.basehttp import (
        WSGIRequestHandler,
        WSGIServer,
        get_internal_wsgi_application,
    )

    django.setup()

    class Handler(WSGIRequestHandler):
        protocol_version = "HTTP/1.1"

    httpd = WSGIServer((HOST, PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.set_app(StaticFilesHandler(get_internal_wsgi_application()))

    print(f"Eureka HTTPS  https://192.168.69.12:{PORT}/")
    print(f"              https://127.0.0.1:{PORT}/")
    print("iPad: apri HTTPS → avanza sul certificato → Aggiungi a Home.")
    print("Poi: Dati offline → Scarica dati. Senza Wi‑Fi resta quella pagina.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStop.")


if __name__ == "__main__":
    main()
