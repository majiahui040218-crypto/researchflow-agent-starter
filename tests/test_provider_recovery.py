"""Offline tests: fake model errors, never make real API calls."""

from types import SimpleNamespace
import pytest

from researchflow.providers import OpenAILanguage, ProviderCallError, _provider_error


class FakeApiException(Exception):
    def __init__(self, provider_code="1305", status_code=429):
        super().__init__("RAW SECRET: do not persist this")
        self.status_code = status_code
        self.body = {"code": provider_code}


def test_glm_1305_is_classified_without_raw_message():
    failure = _provider_error(FakeApiException("1305"))
    assert failure.code == "MODEL_BUSY"
    assert failure.retryable
    assert "RAW SECRET" not in str(failure)


def test_glm_1302_never_retries():
    failure = _provider_error(FakeApiException("1302"))
    assert failure.code == "ACCOUNT_RATE_LIMIT"
    assert not failure.retryable


def test_other_auth_and_timeouts():
    assert _provider_error(FakeApiException("x", 401)).code == "MODEL_AUTH_FAILED"
    assert _provider_error(TimeoutError("unsafe details")).code == "MODEL_TIMEOUT"


def test_wrapped_sdk_error():
    try:
        try:
            raise FakeApiException("1305")
        except FakeApiException as exc:
            raise RuntimeError("LangChain wrapper") from exc
    except RuntimeError as outer:
        assert _provider_error(outer).code == "MODEL_BUSY"


def test_default_no_retry():
    class AlwaysBusy:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            raise FakeApiException("1305")

    language = OpenAILanguage.__new__(OpenAILanguage)
    language._retry_attempts = 0
    language._model = AlwaysBusy()
    with pytest.raises(ProviderCallError) as failure:
        language.plan("LangGraph vs CrewAI")
    assert failure.value.code == "MODEL_BUSY"
    assert language._model.calls == 1


def test_one_bounded_retry(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    class RecoveringModel:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                raise FakeApiException("1305")
            return SimpleNamespace(content='{"queries":["LangGraph docs"]}')

    language = OpenAILanguage.__new__(OpenAILanguage)
    language._retry_attempts = 1
    language._model = RecoveringModel()
    assert language.plan("LangGraph vs CrewAI") == ["LangGraph docs"]
    assert language._model.calls == 2
    assert sleeps == [3.0]
