from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import socket
import time
from urllib.parse import urlencode

import httpx


@dataclass(slots=True)
class DesktopLaunchConfig:
    preferred_port: int = 8080
    explicit_port: int | None = None
    allow_lan: bool = False
    admin_secret: str | None = None
    headless: bool = False
    no_browser: bool = False


@dataclass(slots=True)
class DesktopBinding:
    listen_host: str
    browser_host: str


def resolve_launch_binding(config: DesktopLaunchConfig) -> DesktopBinding:
    if config.allow_lan and not config.admin_secret:
        raise ValueError("An admin secret is required when LAN mode is enabled.")
    if config.allow_lan:
        return DesktopBinding(listen_host="0.0.0.0", browser_host="127.0.0.1")
    return DesktopBinding(listen_host="127.0.0.1", browser_host="127.0.0.1")


def select_listen_port(*, preferred_port: int = 8080, explicit_port: int | None = None, host: str = "127.0.0.1") -> int:
    candidate = explicit_port if explicit_port is not None else preferred_port
    if _port_available(host, candidate):
        return candidate
    if explicit_port is not None:
        raise ValueError(f"Port {explicit_port} is already in use.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def build_dashboard_url(host: str, port: int, *, admin_secret: str | None = None) -> str:
    base_url = f"http://{host}:{port}/dashboard"
    if not admin_secret:
        return base_url
    return f"{base_url}?{urlencode({'admin_secret': admin_secret})}"


def wait_for_healthcheck(
    healthcheck_url: str,
    *,
    timeout_seconds: float = 10.0,
    interval_seconds: float = 0.2,
    probe=None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_probe = probe or _default_probe
    while time.monotonic() < deadline:
        if health_probe(healthcheck_url):
            return
        time.sleep(interval_seconds)
    raise TimeoutError(f"Timed out waiting for healthcheck: {healthcheck_url}")


def build_child_command(
    *,
    executable: Path,
    entrypoint_script: Path,
    config: DesktopLaunchConfig,
    frozen: bool,
) -> list[str]:
    command = [str(executable)]
    if not frozen:
        command.append(str(entrypoint_script))
    command.extend(["--headless", "--port", str(config.explicit_port or config.preferred_port)])
    if config.allow_lan:
        command.append("--allow-lan")
    if config.admin_secret:
        command.extend(["--admin-secret", config.admin_secret])
    if config.no_browser:
        command.append("--no-browser")
    return command


def build_settings_env(*, base_env: dict[str, str], config: DesktopLaunchConfig) -> dict[str, str]:
    env = dict(base_env)
    env.setdefault("MANAGED_AGENT_STORAGE_BACKEND", "sqlite")
    if config.allow_lan:
        env["MANAGED_AGENT_ENFORCE_ADMIN_AUTH"] = "true"
    else:
        env.pop("MANAGED_AGENT_ENFORCE_ADMIN_AUTH", None)
    if config.admin_secret:
        env["MANAGED_AGENT_ADMIN_SECRET"] = config.admin_secret
    return env


def launch_background_desktop(
    *,
    config: DesktopLaunchConfig,
    executable: Path,
    entrypoint_script: Path,
    frozen: bool,
    base_env: dict[str, str],
    popen,
    wait_for_server,
    open_browser,
    chosen_port: int | None = None,
) -> str:
    binding = resolve_launch_binding(config)
    port = chosen_port or select_listen_port(
        preferred_port=config.preferred_port,
        explicit_port=config.explicit_port,
        host=binding.listen_host,
    )
    command = build_child_command(
        executable=executable,
        entrypoint_script=entrypoint_script,
        config=DesktopLaunchConfig(
            preferred_port=config.preferred_port,
            explicit_port=port,
            allow_lan=config.allow_lan,
            admin_secret=config.admin_secret,
            headless=True,
            no_browser=True,
        ),
        frozen=frozen,
    )
    popen(command, env=build_settings_env(base_env=base_env, config=config))
    healthcheck_url = f"http://{binding.browser_host}:{port}/healthz"
    wait_for_server(healthcheck_url)
    dashboard_url = build_dashboard_url(binding.browser_host, port, admin_secret=config.admin_secret if config.allow_lan else None)
    if not config.no_browser:
        open_browser(dashboard_url)
    return dashboard_url


def _default_probe(healthcheck_url: str) -> bool:
    try:
        response = httpx.get(healthcheck_url, timeout=1.0, trust_env=False)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True
