"""Explicit, opt-in LLM HTTP proxy configuration.

Default behavior intentionally matches V0.5: IPv4 direct, ignoring ambient
HTTP(S)_PROXY variables. RESEARCHFLOW_HTTP_PROXY opts in to a specific proxy.
No external connections are made when this module is imported.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit


def configured_llm_proxy(env=None) -> str | None:
    """Return a validated proxy URL or None; never include its value in errors."""
    values = os.environ if env is None else env
    raw = (values.get("RESEARCHFLOW_HTTP_PROXY") or "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        valid = (
            parts.scheme == "http"
            and bool(parts.hostname)
            and parts.port is not None
            and not parts.username
            and not parts.password
            and not parts.path.strip("/")
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "RESEARCHFLOW_HTTP_PROXY must be an http://host:port URL "
            "without credentials or a path"
        )
    return raw


def build_llm_http_client(*, timeout: float = 60.0):
    """Build the client with the same HTTP implementation used by providers."""
    import httpx2

    proxy = configured_llm_proxy()
    if proxy is not None:
        return httpx2.Client(proxy=proxy, trust_env=False, timeout=timeout)
    return httpx2.Client(
        transport=httpx2.HTTPTransport(local_address="0.0.0.0"),
        trust_env=False,
        timeout=timeout,
    )
