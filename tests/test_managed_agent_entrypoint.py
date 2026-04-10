from __future__ import annotations

from pathlib import Path

import managed_agent
from app.desktop import DesktopLaunchConfig, DesktopBinding
from app.runtime import RuntimePaths


def test_run_headless_disables_uvicorn_console_logging(tmp_path: Path, monkeypatch) -> None:
    runtime_paths = RuntimePaths(
        project_root=tmp_path,
        bundle_root=tmp_path,
        templates_dir=tmp_path / "templates",
        openapi_path=tmp_path / "openapi.yaml",
        app_home=tmp_path / "home",
        data_dir=tmp_path / "home" / "data",
        cache_dir=tmp_path / "home" / "cache",
        logs_dir=tmp_path / "home" / "logs",
        config_dir=tmp_path / "home" / "config",
        frozen=True,
    )
    for path in (runtime_paths.templates_dir, runtime_paths.data_dir, runtime_paths.cache_dir, runtime_paths.logs_dir, runtime_paths.config_dir):
        path.mkdir(parents=True, exist_ok=True)
    runtime_paths.openapi_path.write_text("openapi: 3.1.0\n", encoding="utf-8")

    captured: dict[str, object] = {}

    monkeypatch.setattr(managed_agent, "resolve_runtime_paths", lambda: runtime_paths)
    monkeypatch.setattr(managed_agent, "resolve_launch_binding", lambda config: DesktopBinding(listen_host="127.0.0.1", browser_host="127.0.0.1"))
    monkeypatch.setattr(managed_agent, "select_listen_port", lambda **_: 8123)
    monkeypatch.setattr(managed_agent, "resolve_settings", lambda **_: object())
    monkeypatch.setattr(managed_agent, "create_app", lambda **_: "app-instance")

    def fake_uvicorn_run(app, *, host: str, port: int, log_level: str, log_config, access_log: bool):
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["log_level"] = log_level
        captured["log_config"] = log_config
        captured["access_log"] = access_log

    monkeypatch.setattr(managed_agent.uvicorn, "run", fake_uvicorn_run)

    exit_code = managed_agent.run_headless(DesktopLaunchConfig(headless=True, no_browser=True))

    assert exit_code == 0
    assert captured["app"] == "app-instance"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8123
    assert captured["log_level"] == "info"
    assert captured["log_config"] is None
    assert captured["access_log"] is False
