from __future__ import annotations

from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from ..constants import CERT_WARN_DAYS
from ..models import SourceFile, ToilItem, ToilKind, make_id

_CERT_SUFFIXES = (".pem", ".crt", ".cer", ".cert")


def _severity_for(days_left: int) -> int:
    if days_left <= 0:
        return 5
    if days_left <= 7:
        return 5
    if days_left <= 14:
        return 4
    if days_left <= CERT_WARN_DAYS:
        return 3
    return 2


def _parse_expiry(text: str) -> datetime | None:
    marker = "-----BEGIN CERTIFICATE-----"
    if marker not in text:
        return None
    try:
        cert = x509.load_pem_x509_certificate(text.encode("utf-8"), default_backend())
    except (ValueError, TypeError):
        return None
    expires = cert.not_valid_after_utc
    return expires


def scan(files: list[SourceFile], now: datetime | None = None) -> list[ToilItem]:
    reference = now or datetime.now(timezone.utc)
    items: list[ToilItem] = []
    for file in files:
        if not file.path.lower().endswith(_CERT_SUFFIXES):
            continue
        expires = _parse_expiry(file.text)
        if expires is None:
            continue
        days_left = (expires - reference).days
        if days_left > CERT_WARN_DAYS:
            continue
        state = "expired" if days_left < 0 else f"expires in {days_left} days"
        items.append(
            ToilItem(
                id=make_id(ToilKind.expiring_cert, file.path, None, str(expires.date())),
                kind=ToilKind.expiring_cert,
                path=file.path,
                line=None,
                title=f"TLS certificate {state}",
                evidence=f"notAfter={expires.date().isoformat()}",
                severity=_severity_for(days_left),
                effort=3,
                staleness_days=days_left,
            )
        )
    return items
