from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

import uvicorn

from app.desktop import (
    DesktopLaunchConfig,
    build_settings_env,
    launch_background_desktop,
    resolve_launch_binding,
    select_listen_port,
    wait_for_healthcheck,
)
from app.main import create_app
from app.runtime import RuntimePaths, resolve_runtime_paths
from app.services.settings import resolve_settings

APP_NAME = "Managed Agent"
STATE_FILE = "desktop-state.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Managed Agent desktop launcher for Windows.")
    parser.add_argument("--headless", action="store_true", help="Run the local API server in the foreground.")
    parser.add_argument("--port", type=int, default=None, help="Listen on a specific port.")
    parser.add_argument("--allow-lan", action="store_true", help="Expose the local API on the LAN.")
    parser.add_argument("--admin-secret", default=None, help="Admin secret required when LAN mode is enabled.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard in a browser.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = DesktopLaunchConfig(
        explicit_port=args.port,
        allow_lan=args.allow_lan,
        admin_secret=args.admin_secret,
        headless=args.headless,
        no_browser=args.no_browser,
    )
    if config.headless:
        return run_headless(config)
    return launch_gui(config)


def launch_gui(config: DesktopLaunchConfig) -> int:
    runtime_paths = resolve_runtime_paths()
    ensure_runtime_directories(runtime_paths)
    binding = resolve_launch_binding(config)
    existing_dashboard_url = discover_running_dashboard(runtime_paths, config=config)
    if existing_dashboard_url is not None:
        if not config.no_browser:
            webbrowser.open(existing_dashboard_url)
        return 0

    chosen_port = select_listen_port(
        preferred_port=config.preferred_port,
        explicit_port=config.explicit_port,
        host=binding.listen_host,
    )
    launch_background_desktop(
        config=config,
        executable=Path(sys.executable),
        entrypoint_script=Path(__file__).resolve(),
        frozen=bool(getattr(sys, "frozen", False)),
        base_env=dict(os.environ),
        popen=spawn_background_process,
        wait_for_server=lambda url: wait_for_healthcheck(url, timeout_seconds=15.0),
        open_browser=webbrowser.open,
        chosen_port=chosen_port,
    )
    return 0


def run_headless(config: DesktopLaunchConfig) -> int:
    runtime_paths = resolve_runtime_paths()
    ensure_runtime_directories(runtime_paths)
    configure_logging(runtime_paths)
    binding = resolve_launch_binding(config)
    port = select_listen_port(
        preferred_port=config.preferred_port,
        explicit_port=config.explicit_port,
        host=binding.listen_host,
    )
    env = build_settings_env(base_env=dict(os.environ), config=config)
    settings = resolve_settings(env=env, runtime_paths=runtime_paths)
    state_file = runtime_paths.cache_dir / STATE_FILE
    write_server_state(state_file, binding=binding, port=port)
    app = create_app(settings=settings, runtime_paths=runtime_paths)
    try:
        uvicorn.run(
            app,
            host=binding.listen_host,
            port=port,
            log_level="info",
            log_config=None,
            access_log=False,
        )
    finally:
        state_file.unlink(missing_ok=True)
    return 0


def ensure_runtime_directories(runtime_paths: RuntimePaths) -> None:
    for directory in (
        runtime_paths.data_dir,
        runtime_paths.cache_dir,
        runtime_paths.logs_dir,
        runtime_paths.config_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def configure_logging(runtime_paths: RuntimePaths) -> None:
    log_file = runtime_paths.logs_dir / "managed-agent.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def write_server_state(state_file: Path, *, binding, port: int) -> None:
    state_file.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "listen_host": binding.listen_host,
                "browser_host": binding.browser_host,
                "port": port,
                "admin_required": binding.listen_host == "0.0.0.0",
                "started_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def discover_running_dashboard(runtime_paths: RuntimePaths, *, config: DesktopLaunchConfig) -> str | None:
    state_file = runtime_paths.cache_dir / STATE_FILE
    if not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        browser_host = str(state["browser_host"])
        port = int(state["port"])
        admin_required = bool(state.get("admin_required"))
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    try:
        wait_for_healthcheck(f"http://{browser_host}:{port}/healthz", timeout_seconds=1.0, interval_seconds=0.1)
    except TimeoutError:
        return None
    if admin_required and not config.admin_secret:
        return None
    return f"http://{browser_host}:{port}/dashboard" + (
        f"?admin_secret={config.admin_secret}" if admin_required and config.admin_secret else ""
    )


def spawn_background_process(command: list[str], *, env: dict[str, str]) -> subprocess.Popen:
    kwargs: dict[str, object] = {"env": env}
    if os.name == "nt":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
