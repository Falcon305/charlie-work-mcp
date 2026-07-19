from __future__ import annotations

from datetime import UTC, datetime

from cryptography import x509

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


def _expiries(text: str) -> list[datetime]:
    if "-----BEGIN CERTIFICATE-----" not in text:
        return []
    try:
        certs = x509.load_pem_x509_certificates(text.encode("utf-8"))
    except (ValueError, TypeError):
        return []
    return [cert.not_valid_after_utc for cert in certs]


def scan(files: list[SourceFile], now: datetime | None = None) -> list[ToilItem]:
    reference = now or datetime.now(UTC)
    items: list[ToilItem] = []
    for file in files:
        if not file.path.lower().endswith(_CERT_SUFFIXES):
            continue
        expiries = _expiries(file.text)
        multiple = len(expiries) > 1
        for index, expires in enumerate(expiries):
            days_left = (expires - reference).days
            if days_left > CERT_WARN_DAYS:
                continue
            state = "expired" if days_left < 0 else f"expires in {days_left} days"
            position = f" (cert {index + 1} in bundle)" if multiple else ""
            items.append(
                ToilItem(
                    id=make_id(
                        ToilKind.expiring_cert, file.path, index + 1 if multiple else None, str(expires.date())
                    ),
                    kind=ToilKind.expiring_cert,
                    path=file.path,
                    line=None,
                    title=f"TLS certificate {state}{position}",
                    evidence=f"notAfter={expires.date().isoformat()}",
                    severity=_severity_for(days_left),
                    effort=3,
                    staleness_days=days_left,
                )
            )
    return items
