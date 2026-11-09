#!/usr/bin/env python3
"""Generate SmartCore_plug.ctcs from SmartCore_plug.xls.

Usage:
    python gen_ctcs.py <input.xls> -o <output.ctcs>

Format (reverse-engineered from DataGenrator.exe output):
    - Data sheet rows in order; for each row with a positive integer size in column B,
      emit the value (column C) as big-endian integer of that many bytes.
    - Skip rows with no size (header, section markers, blank rows).
    - The last two rows are ID_CRC_DATA (0xee8f, 2 bytes) and CRC_DATA (4 bytes, init 0).
    - CRC-32 (poly 0x04C11DB7, init 0, non-reflected, no final xor) is computed over
      all serialized bytes EXCEPT the last 4 bytes (the CRC field), then written into
      those 4 bytes big-endian.
    - Pad with 64 zero bytes at the end.
"""
from __future__ import annotations

import argparse
import struct
import sys


def parse_value(v):
    """Parse a cell value: '0x...' hex string -> int; numeric -> int."""
    s = str(v).strip()
    if s.lower().startswith("0x"):
        hx = s[2:].rstrip("L").rstrip("l")
        return int(hx, 16)
    return int(round(float(v)))


def read_data_sheet(path):
    """Read the Data sheet and return list of (size, value) pairs."""
    import xlrd

    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_name("Data")
    rows = []
    for r in range(sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        size = sh.cell_value(r, 1)
        val = sh.cell_value(r, 2)
        if name == "ID_INFO":
            continue
        if isinstance(size, float) and size == int(size):
            size = int(size)
        if not isinstance(size, int) or size <= 0:
            continue
        rows.append((size, parse_value(val)))
    return rows


def crc32_mpeg2(data):
    """CRC-32/MPEG-2: poly 0x04C11DB7, init 0, non-reflected, no xorout."""
    poly = 0x04C11DB7
    crc = 0
    for b in data:
        crc ^= (b << 24)
        for _ in range(8):
            crc = ((crc << 1) & 0xFFFFFFFF) ^ poly if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc & 0xFFFFFFFF


def generate(rows):
    """Serialize rows into .ctcs bytes."""
    buf = bytearray()
    for size, val in rows:
        buf += val.to_bytes(size, "big")
    # CRC over all bytes except the last 4 (CRC_DATA field)
    crc = crc32_mpeg2(bytes(buf[:-4]))
    buf[-4:] = crc.to_bytes(4, "big")
    # 64-byte zero padding
    buf += b"\x00" * 64
    return bytes(buf), crc


def main():
    ap = argparse.ArgumentParser(description="Generate SmartCore_plug.ctcs from SmartCore_plug.xls")
    ap.add_argument("input", help="Path to SmartCore_plug.xls")
    ap.add_argument("-o", "--output", required=True, help="Output .ctcs path")
    args = ap.parse_args()

    rows = read_data_sheet(args.input)
    out, crc = generate(rows)

    with open(args.output, "wb") as f:
        f.write(out)

    print(f"Input rows: {len(rows)}")
    print(f"Item region: {len(out) - 64} bytes")
    print(f"CRC: 0x{crc:08x}")
    print(f"Output: {args.output} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
