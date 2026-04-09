#!/usr/bin/env python3
"""Validate selected OpenAPI examples against JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "openapi.yaml"


EXAMPLE_VALIDATIONS = [
    {
        "name": "AgentDefinition request example",
        "path": [
            "paths",
            "/v1/agents",
            "post",
            "requestBody",
            "content",
            "application/json",
            "examples",
            "create_default_planner",
            "value",
        ],
        "schema": ROOT / "agent.schema.json",
    },
    {
        "name": "McpServer example (local-index)",
        "path": [
            "paths",
            "/v1/agents",
            "post",
            "requestBody",
            "content",
            "application/json",
            "examples",
            "create_default_planner",
            "value",
            "allowed_mcp_servers",
            0,
        ],
        "schema": ROOT / "mcp-server.schema.json",
    },
    {
        "name": "McpServer example (secrets-vault)",
        "path": [
            "paths",
            "/v1/agents",
            "post",
            "requestBody",
            "content",
            "application/json",
            "examples",
            "create_default_planner",
            "value",
            "allowed_mcp_servers",
            1,
        ],
        "schema": ROOT / "mcp-server.schema.json",
    },
]


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_path(document: Any, path_parts: list[Any]) -> Any:
    current = document
    for key in path_parts:
        current = current[key]
    return current


def main() -> int:
    openapi = read_yaml(OPENAPI_PATH)
    errors: list[str] = []

    for item in EXAMPLE_VALIDATIONS:
        example = get_path(openapi, item["path"])
        schema = read_json(item["schema"])
        validator = Draft202012Validator(schema)
        validation_errors = sorted(validator.iter_errors(example), key=lambda e: e.path)

        if validation_errors:
            for err in validation_errors:
                loc = "/".join(str(p) for p in err.path) or "<root>"
                errors.append(f"{item['name']} @ {loc}: {err.message}")

    if errors:
        print("OpenAPI example validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("OpenAPI examples validated successfully against JSON schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
