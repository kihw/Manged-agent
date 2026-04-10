from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test a packaged Managed Agent Windows executable.")
    parser.add_argument("--exe", required=True, help="Path to Managed Agent.exe")
    parser.add_argument("--timeout", type=float, default=20.0, help="Maximum startup time in seconds")
    return parser.parse_args()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_healthcheck(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/healthz", timeout=1.0, trust_env=False)
        except httpx.HTTPError:
            time.sleep(0.25)
            continue
        if response.status_code == 200:
            return
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {base_url}/healthz")


def main() -> int:
    args = parse_args()
    exe_path = Path(args.exe).resolve()
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    temp_root = Path(tempfile.mkdtemp(prefix="managed-agent-release-"))
    local_app_data = temp_root / "LocalAppData"
    local_app_data.mkdir(parents=True, exist_ok=True)
    port = find_free_port()
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(local_app_data)

    process = subprocess.Popen(
        [str(exe_path), "--headless", "--no-browser", "--port", str(port)],
        env=env,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        wait_for_healthcheck(base_url, args.timeout)
        dashboard = httpx.get(f"{base_url}/dashboard", timeout=2.0, trust_env=False)
        dashboard.raise_for_status()
        db_path = local_app_data / "Managed Agent" / "data" / "managed-agent-v1.db"
        if not db_path.exists():
            raise FileNotFoundError(f"SQLite database was not created: {db_path}")
        print(f"Smoke test passed for {exe_path}")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
