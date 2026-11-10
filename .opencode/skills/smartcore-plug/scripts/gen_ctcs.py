#!/usr/bin/env python3
"""Generate, query, edit SmartCore_plug.ctcs files.

Usage:
    python gen_ctcs.py generate <input.xls> -o <output.ctcs>
    python gen_ctcs.py query <input.ctcs> --field <field_name> [-t <template.xls>]
    python gen_ctcs.py edit <input.ctcs> --field <field_name> --value <new_value> [-t <template.xls>] -o <output.ctcs>

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
import xlrd


def parse_value(v):
    """Parse a cell value: '0x...' hex string -> int; numeric -> int."""
    s = str(v).strip()
    if s.lower().startswith("0x"):
        hx = s[2:].rstrip("L").rstrip("l")
        return int(hx, 16)
    return int(round(float(v)))


def read_data_sheet_with_offsets(path):
    """Read Data sheet, return list of (name, size, value, offset) where offset is cumulative from 0."""
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_name("Data")
    rows = []
    current_offset = 0
    for r in range(sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        size = sh.cell_value(r, 1)
        val = sh.cell_value(r, 2)
        if name == "ID_INFO" or not name:
            continue
        if isinstance(size, float) and size == int(size):
            size = int(size)
        if not isinstance(size, int) or size <= 0:
            continue
        rows.append((name, size, parse_value(val), current_offset))
        current_offset += size
    # Add the last two special fields (ID_CRC_DATA and CRC_DATA)
    # ID_CRC_DATA is 2 bytes, CRC_DATA is 4 bytes
    rows.append(("ID_CRC_DATA", 2, 0xee8f, current_offset))
    current_offset += 2
    rows.append(("CRC_DATA", 4, 0, current_offset))
    return rows, current_offset  # current_offset is total size of data part (before padding)


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
    """Serialize (name, size, value, offset) rows into .ctcs bytes, compute CRC."""
    buf = bytearray()
    # Serialize all fields except CRC_DATA (last one)
    for row in rows[:-1]:  # skip CRC_DATA field in rows list
        size, val = row[1], row[2]
        buf += val.to_bytes(size, "big")
    # The CRC_DATA placeholder is already included (0 in last row)
    # Compute CRC over all bytes except the last 4 (CRC_DATA)
    crc = crc32_mpeg2(bytes(buf[:-4]))
    buf[-4:] = crc.to_bytes(4, "big")
    # 64-byte zero padding
    buf += b"\x00" * 64
    return bytes(buf), crc


def query_field(ctcs_path, field_name, template_xls=None):
    """Query the value of a specific field from .ctcs file."""
    with open(ctcs_path, "rb") as f:
        ctcs_data = f.read()
    if len(ctcs_data) != 2020:
        raise ValueError(f"Invalid .ctcs file size: {len(ctcs_data)} bytes (expected 2020)")
    
    # Read template to find field offset and size
    if not template_xls:
        # If no template, need to parse from xls first
        raise ValueError("Query requires template xls to define field offsets and sizes")
    template_rows, _ = read_data_sheet_with_offsets(template_xls)
    
    # Find the field
    field = None
    for row in template_rows:
        if row[0] == field_name:
            field = row
            break
    if not field:
        raise ValueError(f"Field {field_name} not found in template")
    
    name, size, _, offset = field
    # Read value from ctcs: at offset, size bytes, big-endian
    value = int.from_bytes(ctcs_data[offset:offset+size], "big")
    # If it's hex-like, format as 0x for easier reading
    if value > 0xFF:  # For multi-byte, show as hex
        return f"0x{value:X}"
    return value


def edit_field(ctcs_path, field_name, new_value, template_xls, output_ctcs_path):
    """Edit a specific field's value in .ctcs file, update CRC."""
    # Read template to get field info
    template_rows, _ = read_data_sheet_with_offsets(template_xls)
    
    # Find the field
    field = None
    for row in template_rows:
        if row[0] == field_name:
            field = row
            break
    if not field:
        raise ValueError(f"Field {field_name} not found in template")
    
    name, size, _, offset = field
    new_val_parsed = parse_value(new_value)
    
    # Read original ctcs data
    with open(ctcs_path, "rb") as f:
        ctcs_data = bytearray(f.read())
    if len(ctcs_data) != 2020:
        raise ValueError(f"Invalid .ctcs file size: {len(ctcs_data)} bytes (expected 2020)")
    
    # Write new value at the offset
    ctcs_data[offset:offset+size] = new_val_parsed.to_bytes(size, "big")
    
    # Compute new CRC over all bytes except last 4 (CRC_DATA)
    data_without_crc = bytes(ctcs_data[:-4])
    new_crc = crc32_mpeg2(data_without_crc)
    # Write new CRC
    ctcs_data[-4:] = new_crc.to_bytes(4, "big")
    
    # Save to output
    with open(output_ctcs_path, "wb") as f:
        f.write(ctcs_data)
    
    return new_crc


def main():
    ap = argparse.ArgumentParser(description="SmartCore CTCS tool: generate, query, edit")
    subparsers = ap.add_subparsers(dest="command", required=True)

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate .ctcs file from xls Data sheet")
    gen_parser.add_argument("input", help="Input SmartCore_plug.xls")
    gen_parser.add_argument("-o", "--output", required=True, help="Output .ctcs path")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query a field value from .ctcs file")
    query_parser.add_argument("input_ctcs", help="Input .ctcs file")
    query_parser.add_argument("--field", required=True, help="Field name to query")
    query_parser.add_argument("-t", "--template", required=True, help="Template xls file defining field structure")

    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit a field value in .ctcs file")
    edit_parser.add_argument("input_ctcs", help="Input .ctcs file")
    edit_parser.add_argument("--field", required=True, help="Field name to edit")
    edit_parser.add_argument("--value", required=True, help="New value for the field (number or 0x hex)")
    edit_parser.add_argument("-t", "--template", required=True, help="Template xls file defining field structure and offsets")
    edit_parser.add_argument("-o", "--output", required=True, help="Output modified .ctcs path")

    args = ap.parse_args()

    if args.command == "generate":
        # Read rows with offsets (we need all fields including ID_CRC_DATA)
        rows, _ = read_data_sheet_with_offsets(args.input)
        out, crc = generate(rows)
        with open(args.output, "wb") as f:
            f.write(out)
        print(f"Generate: Input fields {len(rows)}")
        print(f"Output: {args.output} ({len(out)} bytes), CRC: 0x{crc:08x}")
    elif args.command == "query":
        value = query_field(args.input_ctcs, args.field, args.template)
        print(f"Query result: Field {args.field} = {value}")
    elif args.command == "edit":
        new_crc = edit_field(args.input_ctcs, args.field, args.value, args.template, args.output)
        print(f"Edit: Field {args.field} updated to {args.value}")
        print(f"Output: {args.output}, New CRC: 0x{new_crc:08x}")


if __name__ == "__main__":
    main()
