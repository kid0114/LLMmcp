from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlparse

from shared.errors import PermissionDeniedError
from shared.settings import get_settings

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def validate_outbound_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise PermissionDeniedError("Only http/https URLs are allowed")

    host = parsed.hostname
    if not host:
        raise PermissionDeniedError("URL hostname is missing")

    normalized_host = host.lower()
    if normalized_host in _BLOCKED_HOSTNAMES:
        raise PermissionDeniedError("Localhost and loopback hosts are blocked")

    try:
        ip = ip_address(normalized_host)
    except ValueError:
        ip = None

    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise PermissionDeniedError("Private or local network addresses are blocked")

    settings = get_settings()
    if settings.allowlist_domains and not any(
        normalized_host == domain or normalized_host.endswith(f".{domain}")
        for domain in settings.allowlist_domains
    ):
        raise PermissionDeniedError("Domain is not in ALLOWLIST_DOMAINS")


def validate_local_path(path: str, root: Path) -> Path:
    candidate = Path(path)
    normalized_root = root.resolve()
    resolved = (normalized_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    if normalized_root not in (resolved, *resolved.parents):
        raise PermissionDeniedError("Local file path is outside LOCAL_FILE_ROOT")

    return resolved
