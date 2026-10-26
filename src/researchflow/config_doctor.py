"""Offline configuration diagnostic. Never prints credentials or raw exceptions.

Usage: python -m researchflow.config_doctor
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from .network import configured_llm_proxy


_DEFAULTS = {
    "RESEARCHFLOW_MODE": "mock",
    "OPENAI_MODEL": "gpt-4o-mini",
    "OPENAI_BASE_URL": "(provider default)",
    "RESEARCHFLOW_HTTP_PROXY": "(not configured: IPv4 direct)",
}
_FIELDS = (
    "RESEARCHFLOW_MODE",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "RESEARCHFLOW_HTTP_PROXY",
)
_KEYS = ("OPENAI_API_KEY", "TAVILY_API_KEY")


def _safe_endpoint(value: str) -> str:
    """Hide userinfo, query, and fragment, which can contain secrets."""
    if value.startswith("("):
        return value
    parts = urlsplit(value)
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        return "(invalid URL)"
    host = parts.hostname
    if ":" in host:
        host = f"[{host}]"
    try:
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "(invalid URL)"
    return f"{parts.scheme}://{host}{port}{parts.path}"


def diagnose(file_vars: dict, shell_vars: dict) -> tuple[list[str], list[str]]:
    """Pure function: lines and warnings; shell env takes priority over .env."""
    lines: list[str] = []
    warnings: list[str] = []
    effective: dict[str, str] = {}

    for key in _FIELDS:
        file_value = str(file_vars.get(key) or "").strip()
        shell_value = str(shell_vars.get(key) or "").strip()
        if shell_value:
            value, source = shell_value, "shell"
        elif file_value:
            value, source = file_value, ".env"
        else:
            value, source = _DEFAULTS[key], "default"
        effective[key] = value
        visible = _safe_endpoint(value) if key.endswith("BASE_URL") or key.endswith("HTTP_PROXY") else value
        lines.append(f"{key}: {visible} [{source}]")
        if shell_value and file_value and shell_value != file_value:
            warnings.append(
                f"{key} differs between shell and .env; shell wins. "
                f"Use 'unset {key}' to prefer .env."
            )

    for key in _KEYS:
        file_value = str(file_vars.get(key) or "").strip()
        shell_value = str(shell_vars.get(key) or "").strip()
        present = bool(shell_value or file_value)
        source = "shell" if shell_value else (".env" if file_value else "missing")
        lines.append(f"{key}: {'set' if present else 'NOT SET'} [{source}]")
        if shell_value and file_value and shell_value != file_value:
            warnings.append(f"{key} differs between shell and .env (values hidden); shell wins.")
        if effective["RESEARCHFLOW_MODE"].lower() == "live" and not present:
            warnings.append(f"{key} is required by the current live research/tool CLI.")

    if effective["RESEARCHFLOW_MODE"].lower() not in {"mock", "live"}:
        warnings.append("RESEARCHFLOW_MODE must be 'mock' or 'live'.")
    try:
        configured_llm_proxy({"RESEARCHFLOW_HTTP_PROXY":
            "" if effective["RESEARCHFLOW_HTTP_PROXY"].startswith("(") else effective["RESEARCHFLOW_HTTP_PROXY"]})
    except ValueError:
        warnings.append("RESEARCHFLOW_HTTP_PROXY has an invalid format (value hidden).")
    return lines, warnings


def main() -> int:
    # No load_dotenv here: we deliberately compare both sources before loading.
    env_file = Path(".env")
    file_vars = dotenv_values(env_file) if env_file.is_file() else {}
    lines, warnings = diagnose(file_vars, os.environ)
    print("ResearchFlow configuration (offline; NO API calls):")
    for line in lines:
        print("  " + line)
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print("  - " + warning)
        return 1
    print("No configuration conflicts detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
