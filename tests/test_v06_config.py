"""V0.6 configuration diagnostics and transport policy: no real network."""

import pytest

from researchflow.config_doctor import _safe_endpoint, diagnose
from researchflow.network import configured_llm_proxy, build_llm_http_client


def test_shell_model_wins_and_doctor_warns_without_key_leak():
    file_vars = {
        "RESEARCHFLOW_MODE": "live",
        "OPENAI_MODEL": "qwen3.8-chat",
        "OPENAI_BASE_URL": "https://api.llm.ustc.edu.cn/v1",
        "OPENAI_API_KEY": "file-SECRET",
        "TAVILY_API_KEY": "tavily-SECRET",
    }
    shell_vars = {"OPENAI_MODEL": "deepseek-v4-flash", "OPENAI_API_KEY": "shell-SECRET"}
    lines, warnings = diagnose(file_vars, shell_vars)
    display = "\n".join(lines + warnings)
    assert "OPENAI_MODEL: deepseek-v4-flash [shell]" in display
    assert "unset OPENAI_MODEL" in display
    assert "file-SECRET" not in display
    assert "shell-SECRET" not in display
    assert "tavily-SECRET" not in display


def test_mock_without_keys_has_no_warning():
    _, warnings = diagnose({"RESEARCHFLOW_MODE": "mock"}, {})
    assert warnings == []


def test_live_missing_keys_is_diagnosed():
    _, warnings = diagnose({"RESEARCHFLOW_MODE": "live"}, {})
    assert any("OPENAI_API_KEY" in x for x in warnings)
    assert any("TAVILY_API_KEY" in x for x in warnings)


def test_url_display_drops_embedded_credentials_and_query():
    visible = _safe_endpoint("https://u:secret@example.com:443/v1?key=SECRET#SECRET")
    assert visible == "https://example.com:443/v1"


@pytest.mark.parametrize("bad", [
    "socks5://127.0.0.1:7890",
    "http://127.0.0.1",
    "http://user:secret@127.0.0.1:7890",
    "http://127.0.0.1:invalid",
    "https://127.0.0.1:7890",
    "http://127.0.0.1:7890/anything",
])
def test_invalid_proxy_rejected_without_raw_secret(bad):
    with pytest.raises(ValueError) as error:
        configured_llm_proxy({"RESEARCHFLOW_HTTP_PROXY": bad})
    assert "secret" not in str(error.value)


def test_proxy_can_be_set_explicitly():
    assert configured_llm_proxy({"RESEARCHFLOW_HTTP_PROXY": "http://127.0.0.1:7890"}) == "http://127.0.0.1:7890"
    assert configured_llm_proxy({}) is None


def test_proxy_client_selects_explicit_route(monkeypatch):
    """Use a fake httpx2 client so tests never access a proxy or the network."""
    import sys
    from types import SimpleNamespace

    recorded = []
    class FakeClient:
        def __init__(self, **kwargs):
            recorded.append(kwargs)
    class FakeTransport:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setitem(sys.modules, "httpx2", SimpleNamespace(Client=FakeClient, HTTPTransport=FakeTransport))
    monkeypatch.setenv("RESEARCHFLOW_HTTP_PROXY", "http://127.0.0.1:7890")
    build_llm_http_client()
    assert recorded[-1]["proxy"] == "http://127.0.0.1:7890"
    assert recorded[-1]["trust_env"] is False

    monkeypatch.delenv("RESEARCHFLOW_HTTP_PROXY")
    build_llm_http_client()
    assert recorded[-1]["transport"].kwargs == {"local_address": "0.0.0.0"}
    assert recorded[-1]["trust_env"] is False


def test_language_provider_passes_model_key_and_base_url_explicitly(monkeypatch):
    """Pure constructor test, with fakes: no LangChain import or API calls."""
    import sys
    from types import SimpleNamespace
    from researchflow.providers import OpenAILanguage

    observed = {}
    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            observed.update(kwargs)
    class FakeHttpClient:
        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=FakeChatOpenAI))
    monkeypatch.setattr("researchflow.network.build_llm_http_client", lambda **kwargs: FakeHttpClient())
    monkeypatch.setenv("OPENAI_MODEL", "stale-ignored")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.llm.ustc.edu.cn/v1")
    monkeypatch.setenv("RESEARCHFLOW_LLM_RETRIES", "0")

    language = OpenAILanguage("qwen3.8-chat")
    assert observed["model"] == "qwen3.8-chat"
    assert observed["base_url"] == "https://api.llm.ustc.edu.cn/v1"
    assert observed["api_key"] == "test-key"
    assert "extra_body" not in observed
    language.close()
