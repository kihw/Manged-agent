from __future__ import annotations

import json
import socket

from app.models import CodexInstance, RegisterInstanceRequest
from app.runtime import RuntimePaths
from app.services.platform import PlatformService


class DesktopInstanceManager:
    def __init__(self, *, services: PlatformService, runtime_paths: RuntimePaths) -> None:
        self.services = services
        self.runtime_paths = runtime_paths
        self.config_path = runtime_paths.config_dir / "desktop-instance.json"

    def ensure_local_instance(self) -> CodexInstance:
        self.runtime_paths.config_dir.mkdir(parents=True, exist_ok=True)
        persisted = self._load_persisted_registration()
        if persisted is not None:
            instance = self.services.store.get_instance(persisted["instance_id"])
            if instance is not None:
                return instance

        registration = self.services.register_instance(
            RegisterInstanceRequest(
                client_kind="windows_app",
                workspace_path=str(self.runtime_paths.project_root),
                capabilities=["dashboard", "launch", "approvals"],
                machine_id=f"managed-agent-{socket.gethostname().lower()}",
            )
        )
        self.config_path.write_text(
            json.dumps(registration.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        instance = self.services.store.get_instance(registration.instance_id)
        if instance is None:
            raise RuntimeError("Local desktop instance registration did not persist correctly.")
        return instance

    def _load_persisted_registration(self) -> dict[str, str] | None:
        if not self.config_path.exists():
            return None
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        instance_id = payload.get("instance_id")
        instance_token = payload.get("instance_token")
        if not isinstance(instance_id, str) or not isinstance(instance_token, str):
            return None
        return {"instance_id": instance_id, "instance_token": instance_token}
