"""The optional installer must not overwrite unknown provider layouts."""

from pathlib import Path
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply_v06_provider_patch.py"
spec = importlib.util.spec_from_file_location("v06_installer", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_patch_fails_without_known_v05_sections():
    with pytest.raises(ValueError, match="Unexpected providers.py layout"):
        module.patch_provider("class OpenAILanguage: pass\n")


def test_patch_preserves_unrelated_code_and_is_idempotent():
    source = """before\n""" + module.OLD_IMPORT + """other\n""" + module.OLD_CLIENT + """kwargs = {\n""" + module.OLD_KWARGS + """after\n"""
    updated = module.patch_provider(source)
    assert "before" in updated and "after" in updated
    assert "build_llm_http_client(timeout=60.0)" in updated
    assert 'kwargs["base_url"] = base_url' in updated
    assert module.patch_provider(updated) == updated
