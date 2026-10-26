#!/usr/bin/env python3
"""Apply a small, checked V0.6 provider edit to an existing V0.5 checkout.

Protects local modifications: if expected V0.5 code isn't found, NO provider
file is changed and an actionable error is printed. The original is backed up.
It never reads/writes .env, API keys, SQLite databases or user data.
"""

from __future__ import annotations

import sys
from pathlib import Path


OLD_IMPORT = '''        import os
        import httpx2
        from langchain_openai import ChatOpenAI
'''
NEW_IMPORT = '''        import os
        from langchain_openai import ChatOpenAI
        from .network import build_llm_http_client
'''
OLD_CLIENT = '''        # Earlier network diagnostics showed this Mac could reach GLM through IPv4.
        self._http_client = httpx2.Client(
            transport=httpx2.HTTPTransport(local_address="0.0.0.0"),
            trust_env=False,
            timeout=60.0,
        )
'''
NEW_CLIENT = '''        # Preserve the working V0.5 IPv4 route unless a proxy is configured.
        self._http_client = build_llm_http_client(timeout=60.0)
'''
OLD_KWARGS = '''            "http_client": self._http_client,
        }
        if model.lower().startswith("glm-"):
'''
NEW_KWARGS = '''            "http_client": self._http_client,
        }
        # Explicitly bind endpoint and credentials resolved from the environment.
        base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        if model.lower().startswith("glm-"):
'''


def patch_provider(original: str) -> str:
    """Return new text or raise instead of blindly overwriting unrecognized code."""
    if "build_llm_http_client(timeout=60.0)" in original:
        if 'kwargs["base_url"] = base_url' not in original:
            raise ValueError("Partially modified provider; inspect providers.py manually.")
        return original
    changes = ((OLD_IMPORT, NEW_IMPORT), (OLD_CLIENT, NEW_CLIENT), (OLD_KWARGS, NEW_KWARGS))
    for old, _ in changes:
        if original.count(old) != 1:
            raise ValueError("Unexpected providers.py layout; no files changed. Ask for a manual diff.")
    updated = original
    for old, new in changes:
        updated = updated.replace(old, new, 1)
    return updated


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    target = root / "src" / "researchflow" / "providers.py"
    try:
        original = target.read_text(encoding="utf-8")
        updated = patch_provider(original)
    except (OSError, ValueError) as exc:
        print(f"Could not safely patch providers.py: {exc}", file=sys.stderr)
        return 2

    # Independently preserve existing .gitignore rules, including custom ignores.
    ignore = root / ".gitignore"
    if updated != original:
        backup = target.with_name("providers.py.v05.bak")
        if backup.exists():
            print("Backup already exists; refusing to overwrite it.", file=sys.stderr)
            return 2
        backup.write_text(original, encoding="utf-8")
        target.write_text(updated, encoding="utf-8")
        print("Patched providers.py; backup: src/researchflow/providers.py.v05.bak")
    else:
        print("providers.py already has V0.6 model network support; no changes.")

    existing = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    additions = [".env.*", "!.env.example", "*.bak", "eval/results/", "*.sqlite", "*.sqlite-shm", "*.sqlite-wal"]
    missing = [line for line in additions if line not in existing.splitlines()]
    if missing:
        with ignore.open("a", encoding="utf-8") as out:
            if existing and not existing.endswith("\n"):
                out.write("\n")
            out.write("\n# V0.6: local credentials and generated artifacts\n")
            out.write("\n".join(missing) + "\n")
        print(f"Extended .gitignore with {len(missing)} local-artifact patterns (kept existing rules).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
