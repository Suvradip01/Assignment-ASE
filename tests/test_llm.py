"""Offline tests for provider routing, response validation and privacy."""

import json
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from engine.llm import check_text, classify_reply


def _fake_groq(
    monkeypatch: pytest.MonkeyPatch,
    result: dict[str, object],
    captured: dict[str, object],
) -> None:
    """Install a fake Groq client that records its request without networking."""

    class FakeCompletions:
        def create(self, **kwargs: object) -> object:
            captured.update(kwargs)
            message = SimpleNamespace(content=json.dumps(result))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeGroq:
        def __init__(self, **kwargs: object) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))


def test_groq_result_is_validated_and_text_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful provider request caches only derived text features."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    captured: dict[str, object] = {}
    _fake_groq(
        monkeypatch,
        {"address_score": 0.8, "name_fake": False, "address_language": "en"},
        captured,
    )
    row = {
        "customer_name": "Asha Sample",
        "address": "12 Test Road",
        "city": "Delhi",
        "state": "Delhi",
        "phone": "9999999999",
        "order_id": "private-id",
        "order_value": 9999,
    }
    result = check_text([row], tmp_path / "cache.jsonl", allow_api=True)[0]
    request_text = captured["messages"][1]["content"]
    assert result["llm_source"] == "groq" and result["address_score"] == 0.8
    assert (
        "private-id" not in request_text
        and "9999999999" not in request_text
        and "9999" not in request_text
    )
    assert captured["max_completion_tokens"] == 256
    assert "phone" not in (tmp_path / "cache.jsonl").read_text(encoding="utf-8")


def test_groq_failure_uses_local_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider exception does not escape to the caller."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")

    class BrokenClient:
        def __init__(self, **kwargs: object) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **params: (_ for _ in ()).throw(
                        RuntimeError("offline")
                    )
                )
            )

    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=BrokenClient))
    result = check_text(
        [{"customer_name": "asdf", "address": "xyz"}],
        tmp_path / "cache.jsonl",
        allow_api=True,
    )[0]
    assert result["llm_source"] == "rules" and result["name_fake"] is True


def test_unclear_reply_classification_redacts_phone_and_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only redacted reply text is sent for optional intent classification."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    captured: dict[str, object] = {}
    _fake_groq(monkeypatch, {"intent": "confirm"}, captured)
    outcome = classify_reply(
        "I paid ₹649, call me at 9876543210", "AWAITING_CONFIRMATION"
    )
    request_text = captured["messages"][1]["content"]
    assert outcome == "confirm"
    assert "9876543210" not in request_text and "649" not in request_text
