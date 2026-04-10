from __future__ import annotations

import socket
from pathlib import Path

import pytest
import httpx

from app.desktop import (
    DesktopLaunchConfig,
    build_child_command,
    build_dashboard_url,
    build_settings_env,
    launch_background_desktop,
    resolve_launch_binding,
    select_listen_port,
    wait_for_healthcheck,
)


def test_select_listen_port_falls_back_when_preferred_port_is_busy() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        preferred_port = occupied.getsockname()[1]

        selected = select_listen_port(preferred_port=preferred_port)

    assert selected != preferred_port
    assert selected > 0


def test_select_listen_port_rejects_busy_explicit_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        explicit_port = occupied.getsockname()[1]

        with pytest.raises(ValueError, match="already in use"):
            select_listen_port(preferred_port=8080, explicit_port=explicit_port)


def test_resolve_launch_binding_requires_secret_for_lan() -> None:
    with pytest.raises(ValueError, match="admin secret"):
        resolve_launch_binding(DesktopLaunchConfig(allow_lan=True))


def test_wait_for_healthcheck_retries_until_ready() -> None:
    attempts = {"count": 0}

    def probe(_: str) -> bool:
        attempts["count"] += 1
        return attempts["count"] >= 3

    wait_for_healthcheck("http://127.0.0.1:8080/healthz", timeout_seconds=1.0, interval_seconds=0.01, probe=probe)

    assert attempts["count"] == 3


def test_build_dashboard_url_bootstraps_admin_secret_for_browser() -> None:
    url = build_dashboard_url("127.0.0.1", 8123, admin_secret="top-secret")

    assert url == "http://127.0.0.1:8123/dashboard?admin_secret=top-secret"


def test_build_child_command_uses_script_entrypoint_when_not_frozen(tmp_path: Path) -> None:
    script_path = tmp_path / "managed_agent.py"

    command = build_child_command(
        executable=Path("C:/Python/python.exe"),
        entrypoint_script=script_path,
        config=DesktopLaunchConfig(explicit_port=8123, headless=False),
        frozen=False,
    )

    assert command == [
        str(Path("C:/Python/python.exe")),
        str(script_path),
        "--headless",
        "--port",
        "8123",
    ]


def test_build_settings_env_enforces_sqlite_and_admin_auth_for_lan() -> None:
    env = build_settings_env(
        base_env={"DATABASE_URL": "postgresql://db.example/managed-agent"},
        config=DesktopLaunchConfig(allow_lan=True, admin_secret="top-secret"),
    )

    assert env["MANAGED_AGENT_STORAGE_BACKEND"] == "sqlite"
    assert env["MANAGED_AGENT_ENFORCE_ADMIN_AUTH"] == "true"
    assert env["MANAGED_AGENT_ADMIN_SECRET"] == "top-secret"


def test_launch_background_desktop_waits_for_health_and_opens_browser(tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_popen(command: list[str], *, env: dict[str, str]) -> None:
        calls["command"] = command
        calls["env"] = env

    def fake_wait(url: str) -> None:
        calls["healthcheck_url"] = url

    def fake_open(url: str) -> None:
        calls["browser_url"] = url

    launch_background_desktop(
        config=DesktopLaunchConfig(allow_lan=True, admin_secret="top-secret", no_browser=False),
        executable=Path("C:/Managed Agent/Managed Agent.exe"),
        entrypoint_script=tmp_path / "managed_agent.py",
        frozen=True,
        base_env={},
        popen=fake_popen,
        wait_for_server=fake_wait,
        open_browser=fake_open,
        chosen_port=8123,
    )

    assert calls["healthcheck_url"] == "http://127.0.0.1:8123/healthz"
    assert calls["browser_url"] == "http://127.0.0.1:8123/dashboard?admin_secret=top-secret"
    assert "--headless" in calls["command"]


def test_wait_for_healthcheck_ignores_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, *, timeout: float, trust_env: bool):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["trust_env"] = trust_env
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.desktop.httpx.get", fake_get)

    wait_for_healthcheck("http://127.0.0.1:8080/healthz", timeout_seconds=0.1, interval_seconds=0.01)

    assert captured["url"] == "http://127.0.0.1:8080/healthz"
    assert captured["trust_env"] is False
