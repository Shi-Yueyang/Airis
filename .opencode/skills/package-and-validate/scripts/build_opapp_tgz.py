#!/usr/bin/env python3
"""Build {app_id}-{version}.opapp.tgz (standalone; no arkbd dependency).

Usage:
  python build_opapp_tgz.py <package_root> [output.tgz]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_lib import build_tgz_from_directory, validate_package_root  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: build_opapp_tgz.py <package_root> [output.tgz]", file=sys.stderr)
        return 2
    package_root = Path(sys.argv[1]).resolve()
    if not package_root.is_dir():
        print(f"Not a directory: {package_root}", file=sys.stderr)
        return 2

    validation = validate_package_root(package_root)
    if not validation["valid"]:
        print(json.dumps({"valid": False, "errors": validation["errors"]}, ensure_ascii=False, indent=2))
        return 1

    manifest = validation["manifest"]
    app_id = str(manifest.get("app_id") or "app").strip()
    version = str(manifest.get("version") or "0.0.0").strip().replace("/", "_")
    default_out = package_root.parent / f"{app_id}-{version}.opapp.tgz"
    output = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else default_out

    build_tgz_from_directory(package_root, output)
    print(
        json.dumps(
            {
                "valid": True,
                "output": str(output),
                "app_id": app_id,
                "version": version,
                "engine": "airis-standalone",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
