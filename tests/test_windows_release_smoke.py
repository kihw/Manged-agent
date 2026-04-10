from __future__ import annotations

import httpx
import pytest

from scripts.smoke_test_windows_release import wait_for_healthcheck


def test_release_smoke_healthcheck_ignores_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, *, timeout: float, trust_env: bool):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["trust_env"] = trust_env
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr("scripts.smoke_test_windows_release.httpx.get", fake_get)

    wait_for_healthcheck("http://127.0.0.1:8080", 0.1)

    assert captured["url"] == "http://127.0.0.1:8080/healthz"
    assert captured["trust_env"] is False
