"""Utility QR code per badge operatori."""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_payload_operatore(codice: str) -> str:
    return f"DIP-{str(codice or '').strip()}"


def qr_png_data_uri(payload: str, *, box_size: int = 8, border: int = 2) -> str:
    """Genera un data-URI PNG del QR code."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
