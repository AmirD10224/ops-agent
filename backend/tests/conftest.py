"""Test fixtures and global setup."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import respx
from anthropic import AsyncAnthropic

# Hard-set env BEFORE app modules import. Otherwise pydantic-settings caches
# real keys from a developer's .env and tests start hitting live APIs.
os.environ["APP_ENV"] = "test"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["TAVILY_API_KEY"] = "test-tavily-key"
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> None:
    from backend.app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
async def store(tmp_db_path: str) -> AsyncIterator:
    from backend.app.store import RunStore

    s = RunStore(tmp_db_path)
    await s.init()
    return s


@pytest.fixture
def broker() -> object:
    from backend.app.sse import EventBroker

    return EventBroker()


@pytest.fixture
def respx_mock() -> AsyncIterator[respx.Router]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture(autouse=True)
def _reset_anthropic() -> None:
    from backend.app import clients

    clients.reset_anthropic_for_tests()


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> FakeAnthropic:
    """Replaces clients.get_anthropic() with a scriptable fake."""
    fake = FakeAnthropic()

    def _get() -> AsyncAnthropic:  # type: ignore[return-value]
        return fake  # type: ignore[return-value]

    monkeypatch.setattr("backend.app.clients.get_anthropic", _get)
    monkeypatch.setattr("backend.app.agent.llm.get_anthropic", _get)
    return fake


# --------------------------- Fakes -----------------------------------------


class _FakeUsage:
    def __init__(self, in_tok: int, out_tok: int) -> None:
        self.input_tokens = in_tok
        self.output_tokens = out_tok


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text: str, in_tok: int = 100, out_tok: int = 200) -> None:
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage(in_tok, out_tok)


class _FakeMessages:
    def __init__(self, parent: FakeAnthropic) -> None:
        self._p = parent

    async def create(self, **kwargs: object) -> _FakeMessage:
        if not self._p._scripted:
            raise RuntimeError("FakeAnthropic has no responses queued")
        text, in_tok, out_tok = self._p._scripted.pop(0)
        return _FakeMessage(text, in_tok, out_tok)


class FakeAnthropic:
    def __init__(self) -> None:
        self._scripted: list[tuple[str, int, int]] = []
        self.messages = _FakeMessages(self)

    def queue(self, text: str, *, in_tok: int = 100, out_tok: int = 200) -> None:
        self._scripted.append((text, in_tok, out_tok))
