#!/usr/bin/env python3
"""Self-test for gen_ctcs.py: verifies byte-identical output against reference sample.

Usage:
    python selftest_ctcs.py [reference.xls] [reference.ctcs]

If no arguments, looks for SmartCore_plug.xls and SmartCore_plug.ctcs in the parent
directory (relative to this script's location).
"""
from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) >= 3:
        xls_path = sys.argv[1]
        ctcs_path = sys.argv[2]
    else:
        # Look for sample in /home/yangbin/AI_competition_casco/ (two levels up from skill dir)
        # SCRIPT_DIR = .../AI_competition_casco/Airis/.opencode/skills/smartcore-plug/scripts
        # AI_competition_casco is 5 levels up: dirname x5
        grandparent = SCRIPT_DIR
        for _ in range(5):
            grandparent = os.path.dirname(grandparent)
        xls_path = os.path.join(grandparent, "SmartCore_plug.xls")
        ctcs_path = os.path.join(grandparent, "SmartCore_plug.ctcs")

    if not os.path.exists(xls_path):
        print(f"SKIP: reference xls not found: {xls_path}")
        return 0
    if not os.path.exists(ctcs_path):
        print(f"SKIP: reference ctcs not found: {ctcs_path}")
        return 0

    sys.path.insert(0, SCRIPT_DIR)
    from gen_ctcs import read_data_sheet, generate

    rows = read_data_sheet(xls_path)
    out, crc = generate(rows)

    sample = open(ctcs_path, "rb").read()

    if out == sample:
        print(f"PASS: byte-identical ({len(out)} bytes, CRC 0x{crc:08x})")
        return 0
    else:
        print(f"FAIL: mismatch (sample {len(sample)} bytes vs output {len(out)} bytes)")
        for i in range(min(len(out), len(sample))):
            if out[i] != sample[i]:
                print(f"  first diff at offset {i}: output 0x{out[i]:02x} vs sample 0x{sample[i]:02x}")
                break
        return 1


if __name__ == "__main__":
    sys.exit(main())
