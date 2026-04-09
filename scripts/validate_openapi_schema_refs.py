#!/usr/bin/env python3
"""Validate OpenAPI local schema references and coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "openapi.yaml"

# Only schemas intended to be exposed through OpenAPI components.
REQUIRED_OPENAPI_SCHEMAS = {
    "agent.schema.json",
    "task-step.schema.json",
    "tool-execution.schema.json",
    "approval-request.schema.json",
    "artifact.schema.json",
    "mcp-server.schema.json",
}


def walk(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def main() -> int:
    with OPENAPI_PATH.open("r", encoding="utf-8") as f:
        openapi_doc = yaml.safe_load(f)

    all_local_refs: set[str] = set()
    errors: list[str] = []

    for key, value in walk(openapi_doc):
        if key != "$ref" or not isinstance(value, str):
            continue
        if not value.endswith(".schema.json"):
            continue

        ref_path = value.split("#", 1)[0]
        ref_name = Path(ref_path).name
        all_local_refs.add(ref_name)

        target = (OPENAPI_PATH.parent / ref_path).resolve()
        if not target.exists():
            errors.append(
                f"Broken local schema reference in openapi.yaml: {value} (file not found)"
            )

    missing_refs = sorted(REQUIRED_OPENAPI_SCHEMAS - all_local_refs)
    extra_refs = sorted(all_local_refs - REQUIRED_OPENAPI_SCHEMAS)

    if missing_refs:
        errors.append(
            "Unreferenced required schema file(s): " + ", ".join(missing_refs)
        )

    if extra_refs:
        errors.append(
            "Unexpected local schema reference(s) not in required allowlist: "
            + ", ".join(extra_refs)
        )

    if errors:
        print("OpenAPI schema reference validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("OpenAPI schema references are complete and valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
