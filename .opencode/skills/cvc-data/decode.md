# Decode — Inspect CVC Data Files

Decode CVC application-data binaries into a field-walk report using the ATP
and SDMU template XMLs. Read-only: this workflow never writes to the source
files.

## Format reference

The wire format (TLV framing, magics per DIST class, canonical ATP→SDMU
field order, reference regression sizes) is defined in
`references/protocol.md` in this skill's folder.

## Inputs

- Data files named by convention `ASW1.bin` (DP), `Config2.line1` (LINE),
  `Config1.train` (TRAIN), but identified by magic, not name. Single
  per-class files only; a concatenated stream with the 8-byte version tail
  is not decodable here.
- The ATP and SDMU template XMLs (`ATPCfgTemplate.xml`,
  `SDMUCfgTemplate.xml`) so every field has a template. Templates are
  matched to fields by `<ASW SYMBOL>`, not by argument order.
- Python 3, standard library only.

## Decoding

The decoder is `scripts/dump_cvc_data.py`; `<skill-dir>` below is this
skill's folder. Input and output paths resolve relative to the current
working directory. All files can be decoded in one call:

```sh
python <skill-dir>/scripts/dump_cvc_data.py \
  -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
  ASW1.bin Config2.line1 Config1.train \
  -o decoded_report.md
```

`-o` writes the Markdown report to a file; without it the report goes to
stdout. Add `--values-out values.json` to also capture the fully namespaced
`{class: {function: {NAME: value}}}` JSON that
`scripts/gen_cvc_data.py --values` accepts for regeneration (this is the
capture step of `edit.md`). REPEAT groups are emitted as lists. Fields whose
walk failed are excluded from the capture; `EXTRA-SLOT` rows have no template
name and are skipped with a warning.

## Interpreting the report

- File line: `DIST=… magic=0x… crc=OK|BAD file=…B fields=[0x66AA5599=18B, …]`
  — CRC covers the whole file minus its trailing 4 bytes.
- Field line: `field=… body=…B walk=OK` | `walk=OK+NB-unaccounted` (template
  consumed fewer bytes than the body holds) |
  `walk=INCOMPLETE(template-needs-more)` (body exhausted mid-walk). The last
  two mean template/data version mismatch.
- Table rows: per-parameter offset (relative to the field body), byte size,
  name, hex and decimal value. Flags: `OUT-OF-RANGE [min..max]` (value
  outside template bounds) and `EXTRA-SLOT` (count forces more entries than
  the template pins).
- A `PARAM` wrapper with `SYMBOL` is a nested TLV. For an optional wrapper,
  the decoder checks for its 4-byte symbol at the current offset; if present,
  it reads the 4-byte payload length and walks only that bounded payload.
  Parameter offsets remain relative to the enclosing field body and therefore
  include the 8-byte nested header. A declared/template length mismatch and
  unconsumed wrapper payload are reported as warnings.

## Success criteria

A decode is trustworthy only when every file shows `crc=OK`, every field
shows `walk=OK` with no unaccounted bytes, and no warnings fire
(`CRC MISMATCH`, `TEMPLATE/DATA MISMATCH`, `OUT-OF-RANGE`,
`no template for field`, unaccounted bytes between fields and CRC). Resolve
warnings before relying on any decoded or captured value;
`crc=OK walk=OK` still does not validate consumer-side domain semantics.

## Malformed input

The decoder reports and never guesses: unknown magic, too-short files,
length overruns, and missing fields produce per-file `ERROR` lines while the
batch continues; a field symbol with no supplied template is listed
undecoded. Do not invent values for undecodable regions — say what failed
and why.

## Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| `CRC MISMATCH` | Stored CRC != computed over the covered range. | Treat the file as corrupted/modified; verify against a trusted source. |
| `TEMPLATE/DATA MISMATCH` | Template revision differs from the data's. | Supply the matching template; inspect the binary before trusting values. |
| `no template for field 0x…` | A field symbol has no `-t` template. | Pass both ATP and SDMU templates. |
| `OUT-OF-RANGE` | Stored value outside template `MINVALUE`/`MAXVALUE`. | Report it; check which side (data or template) is wrong. |
| Unknown magic / too short | Not a per-class file, or a truncated/concatenated stream. | Split the stream to per-class files first; these tools do not decode the assembled stream. |
