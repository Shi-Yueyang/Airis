#!/usr/bin/env python3
"""Validate an Ark app package root (standalone; no arkbd dependency).

Usage:
  python validate_app_package.py <package_root> [expected_app_id]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Same-directory import for portable skill package layout
sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_lib import validate_package_root  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_app_package.py <package_root> [expected_app_id]", file=sys.stderr)
        return 2
    package_root = Path(sys.argv[1]).resolve()
    expected = sys.argv[2] if len(sys.argv) > 2 else None
    if not package_root.is_dir():
        print(f"Not a directory: {package_root}", file=sys.stderr)
        return 2

    result = validate_package_root(package_root, expected_app_id=expected)
    payload = {
        "valid": result["valid"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "checklist": result.get("checklist"),
        "app_id": (result.get("manifest") or {}).get("app_id"),
        "version": (result.get("manifest") or {}).get("version"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
