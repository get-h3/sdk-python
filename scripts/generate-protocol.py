#!/usr/bin/env python3
"""Regenerate protocol.py from H3 protocol JSON Schema v1 files.

Reads JSON Schema files from get-h3/protocol/schemas/v1/ and generates
src/h3_harness/protocol.py with Pydantic models.

Usage:
    make generate
    python scripts/generate-protocol.py --schema-dir /path/to/schemas/v1
"""

import argparse
import json
import re
import sys
from pathlib import Path

HEADER = '''"""H3 Protocol Types — Pydantic models matching the v1 JSON Schema.

Generated from get-h3/protocol/schemas/v1/*.json.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

'''

ENUM_HEADER = "# ── Enums ──\n"


def camel_to_snake(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def class_name_from_title(title: str) -> str:
    """'ProcessRequest' or 'ToolCall' already PascalCase."""
    return title


def py_type_from_schema(prop: dict, defs: dict) -> str:
    """Resolve a JSON Schema property to a Python type string."""
    if "$ref" in prop:
        ref = prop["$ref"]
        if "#" in ref:
            _, path = ref.split("#", 1)
            if path.startswith("/definitions/"):
                return path.split("/")[-1]
        fname = ref.replace(".json", "")
        return class_name_from_title(fname.replace("-", " ").title().replace(" ", ""))

    t = prop.get("type", "string")

    if "enum" in prop:
        return "str"

    if t == "string":
        return "str"
    elif t == "integer":
        return "int"
    elif t == "number":
        return "float"
    elif t == "boolean":
        return "bool"
    elif t == "array":
        items = prop.get("items", {})
        return f"list[{py_type_from_schema(items, defs)}]"
    elif t == "object":
        return "dict[str, Any]"
    return "Any"


def generate_class(class_name: str, schema: dict, defs: dict) -> list[str]:
    """Generate lines for one Pydantic model."""
    lines = [f"\nclass {class_name}(BaseModel):"]
    desc = schema.get("description", "")
    if desc and len(desc) > 80:
        # Truncate long docstrings to avoid E501
        desc = desc[:77] + "..."
    if desc:
        lines.append(f'    """{desc}"""')

    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in sorted(props.items(), key=lambda x: (x[0] not in required, x[0])):
        ptype = py_type_from_schema(prop, defs)
        is_req = name in required
        if is_req:
            lines.append(f"    {name}: {ptype}")
        else:
            lines.append(f"    {name}: {ptype} | None = None")

    return lines


def generate_enum(name: str, values: list[str]) -> list[str]:
    """Generate lines for a str Enum."""
    lines = [f"\nclass {name}(str, Enum):"]
    for v in values:
        label = v.upper().replace("-", "_")
        lines.append(f'    {label} = "{v}"')
    return lines


def generate_protocol(schema_dir: str) -> str:
    schema_path = Path(schema_dir)
    schemas: dict[str, dict] = {}

    for f in sorted(schema_path.glob("*.json")):
        with open(f) as fh:
            s = json.load(fh)
        title = s.get("title", f.stem)
        schemas[title] = s

    common = schemas.get("H3 Common Types", {})
    defs = common.get("definitions", {})

    lines = [HEADER, ENUM_HEADER]

    # ── Top-level Enums ──
    if "Decision" in schemas:
        vals = schemas["Decision"]["properties"]["decision"]["enum"]
        lines.extend(generate_enum("DecisionType", vals))

    if "End" in schemas:
        vals = schemas["End"]["properties"]["reason"]["enum"]
        lines.extend(generate_enum("EndReason", vals))

    if "HealthResponse" in schemas:
        hr = schemas["HealthResponse"]
        lines.extend(
            generate_enum("HealthStatus", hr["properties"]["status"]["enum"])
        )
        lines.extend(
            generate_enum(
                "Capability", hr["properties"]["capabilities"]["items"]["enum"]
            )
        )

    if "CancelRequest" in schemas:
        cr = schemas["CancelRequest"]
        if "reason" in cr.get("properties", {}):
            vals = cr["properties"]["reason"].get("enum", [])
            if vals:
                lines.extend(generate_enum("CancelReason", vals))

    if "ResultRequest" in schemas:
        rr = schemas["ResultRequest"]
        # ResultType from nested result.type enum
        result_obj = rr.get("properties", {}).get("result", {})
        result_props = (
            result_obj.get("properties", {})
            if isinstance(result_obj, dict)
            else {}
        )
        type_prop = result_props.get("type", {})
        if "enum" in type_prop:
            vals = type_prop["enum"]
            lines.extend(generate_enum("ResultType", vals))

    if "ErrorResponse" in schemas:
        er = schemas["ErrorResponse"]
        # ErrorCode is nested: properties.error.properties.code.enum
        err_obj = er.get("properties", {}).get("error", {})
        err_props = err_obj.get("properties", {}) if isinstance(err_obj, dict) else {}
        code_prop = err_props.get("code", {})
        if "enum" in code_prop:
            vals = code_prop["enum"]
            lines.extend(generate_enum("ErrorCode", vals))

    if "SessionResponse" in schemas:
        sr = schemas["SessionResponse"]
        if "status" in sr.get("properties", {}):
            vals = sr["properties"]["status"].get("enum", [])
            if vals:
                lines.extend(generate_enum("SessionStatus", vals))

    # ── Common Definitions ──
    lines.append("\n\n# ── Common Types ──\n")
    for name in ["Attachment", "Message", "Identity", "HistoryEntry",
                  "Tool", "Model", "SessionState", "Config", "Context"]:
        if name in defs:
            lines.extend(generate_class(name, defs[name], defs))

    # ── Decision Payloads ──
    lines.append("\n\n# ── Decision Payloads ──\n")
    for key in ["ToolCall", "LLMCall", "TextResponse", "Wait", "Delegate", "End"]:
        if key in schemas:
            lines.extend(generate_class(key, schemas[key], defs))

    # ── LLMMessage (used by LLMCall.messages) ──
    lines.append("\n\nclass LLMMessage(BaseModel):")
    lines.append('    """Single message in an LLM conversation."""')
    lines.append("    role: str")
    lines.append("    content: str")

    # ── ErrorDetail ──
    lines.append("\n\nclass ErrorDetail(BaseModel):")
    lines.append('    """Detailed error information."""')
    lines.append("    field: str | None = None")
    lines.append("    message: str")
    lines.append("    code: str | None = None")

    # ── ResultPayload ──
    lines.append("\n\nclass ResultPayload(BaseModel):")
    lines.append('    """Payload for a result returned to the harness."""')
    lines.append("    type: str")
    lines.append("    success: bool")
    lines.append("    tool_name: str | None = None")
    lines.append("    data: dict[str, Any] | None = None")
    lines.append("    duration_ms: int | None = None")

    # ── Request/Response Models ──
    lines.append("\n\n# ── Request/Response Models ──\n")
    for key in ["ProcessRequest", "ResultRequest", "CancelRequest",
                 "HealthResponse", "ErrorResponse", "SessionResponse", "Decision"]:
        if key in schemas:
            lines.extend(generate_class(key, schemas[key], defs))

    # ── Decision auto-ID ──
    lines.append("""
    def __init__(self, **data):
        if 'decision_id' not in data or data['decision_id'] is None:
            data['decision_id'] = str(uuid4())
        super().__init__(**data)""")

    # Import uuid4 at the end (always needed for Decision auto-ID)
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Regenerate protocol.py")
    parser.add_argument("--schema-dir", default=None, help="Path to schemas/v1")
    args = parser.parse_args()

    if args.schema_dir:
        schema_dir = args.schema_dir
    else:
        repo_root = Path(__file__).resolve().parent.parent
        schema_dir = repo_root / ".." / "protocol" / "schemas" / "v1"
        if not schema_dir.exists():
            schema_dir = Path("protocol-src/schemas/v1")

    schema_dir = Path(schema_dir)
    if not schema_dir.exists():
        print(f"ERROR: Schema directory not found: {schema_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading schemas from: {schema_dir}")
    code = generate_protocol(str(schema_dir))

    out = Path(__file__).resolve().parent.parent / "src" / "h3_harness" / "protocol.py"
    out.write_text(code)
    print(f"Wrote: {out} ({len(code)} chars)")


if __name__ == "__main__":
    main()
