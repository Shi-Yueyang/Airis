# CVC application-data protocol

This reference describes the binary framing used by the cvc-data scripts
(`scripts/` in this skill folder). It is the single canonical format
document for this skill — see [SKILL.md](../SKILL.md) for routing and the
phase docs (`decode.md`, `generate.md`, `edit.md`) for commands and
workflows.

## File framing

All integers are big-endian:

```text
file = magic:4 | file_length:4 | field_1 | field_2 | ... | crc:4
field = symbol:4 | field_length:4 | body:field_length
```

- `file_length` counts all application fields plus the trailing CRC, but not
  the first 8 bytes (`magic | file_length`).
- The CRC is CRC-32/ISO-HDLC (`zlib.crc32`) over the entire file except the
  final 4 CRC bytes.
- Fields are adjacent; there is no separator or padding.
- A template `PARAM` wrapper with `SYMBOL` frames its nested payload inside a
  field body as `symbol:4 | body_length:4 | body`. The optional ATP wrappers
  use this framing; their 8-byte nested headers count toward the enclosing
  field-body offsets and length. `LENGTH` in the template describes the
  nested body, excluding the header.
- The outer magic identifies the distribution class, not the filename:

  | Class (`DIST`) | Magic | Conventional file |
  |---|---:|---|
  | DP | `0xABABABAB` | `ASW1.bin` |
  | LINE | `0xACACACAC` | `Config2.line1` |
  | TRAIN | `0xADADADAD` | `Config1.train` |

## Application fields

Each field is shaped by the template whose `<ASW SYMBOL>` matches the field
symbol. In the reference files, fields are ordered ATP first, then SDMU:

| Function | Template | Symbol |
|---|---|---:|
| ATP | `ATPCfgTemplate.xml` | `0x66AA5599` |
| SDMU | `SDMUCfgTemplate.xml` | `0xA5A59696` |

For each file, the binary body for a field is selected from the template's
`<PARAMCLASS DIST="DP|LINE|TRAIN">`. The generator requires both ATP and SDMU
templates and always emits the fields in the canonical order above, whatever
the command-line order of `-t` arguments.

`BSWCfgTemplate.xml` is not an application-field template for these files: it
has no `<ASW SYMBOL>`, `<PARAM>` byte sizes, or field symbol, and is skipped by
the tools with a warning.

## Stream framing outside these files

The complete concatenated application stream may have an 8-byte version tail
(`dp_version` followed by `project_version`, big-endian). These per-class files
do not include that tail; its production belongs to the stream assembler.

## Reference regression sizes

A known-good reference dataset has the following field-body lengths:

| File | ATP body | SDMU body | Total file |
|---|---:|---:|---:|
| `ASW1.bin` | 18 bytes | 14 bytes | 60 bytes |
| `Config2.line1` | 247 bytes | 35 bytes | 310 bytes |
| `Config1.train` | 110 bytes | 44 bytes | 182 bytes |

The files have one outer frame and one CRC each. These sizes are useful
regression checks, but byte-for-byte round-trip comparison is stronger.
