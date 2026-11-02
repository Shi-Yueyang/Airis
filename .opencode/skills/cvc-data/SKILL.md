---
name: cvc-data
description: "Decodes, generates, edits, and verifies CVC application data files (ASW1.bin, Config2.line1, Config1.train) using their ATP and SDMU template XMLs, with field-walk reports and round-trip checks. Use for any inspect, audit, generate, edit, or verify task on these files, and for interpreting decoder warnings such as CRC MISMATCH, OUT-OF-RANGE, or TEMPLATE/DATA MISMATCH."
---

# CVC Data

Decode, generate, and edit CVC application-data binaries with the bundled
scripts.

## How to use this skill

Read the doc that matches the task, then follow it. Each phase doc is
complete on its own for its task:

| Task | Read |
|---|---|
| Inspect/audit a data file, interpret warnings, capture values | `decode.md` |
| Produce data files from templates (values JSON required; `--set` for one-offs) | `generate.md` |
| Change specific values in existing files, preserve everything else | `edit.md` |
| Wire-format questions (framing, magics per DIST class, field order) | `references/protocol.md` |
| Anything chaining the above; verification and reporting | the relevant phase docs + the discipline below |


## Prerequisites

- Python 3 (standard library only). The scripts process local files only:
  no external processes, no network.
- The matching ATP and SDMU template XMLs. Both are always required: the
  reference frame carries both application fields, in canonical ATP→SDMU
  order, regardless of command-line order.
- For decode or round-trip work, the source data files.
- For generation, a values JSON — `--values` is required on every run; bare
  template-default generation is rejected, so no run can silently be a
  defaults run.
- For generation, a writable scratch output directory that does not contain
  source files to preserve — generation overwrites conventional filenames
  (`ASW1.bin`, `Config2.line1`, `Config1.train`) in the target directory,
  and every run writes all three.

## Verification and reporting discipline


- **No reliance before decode output is clean** — every `CRC MISMATCH`,
  `TEMPLATE/DATA MISMATCH`, out-of-range, unknown-field, and
  unaccounted-byte warning is resolved or explained before decoded data is
  used (`decode.md`).
- **No completion claim before verify** — every generated or edited file is
  re-decoded with the same templates; require `crc=OK` and `walk=OK` for
  both fields in every file. Reproduction of a known dataset: byte-for-byte
  equality with the references. Intentional edits: exact requested-key diff
  and unchanged unrelated values (`edit.md`). A successful exit code is not
  proof of correct data.
- **Values must come from the matching template revision** — stale keys and
  out-of-range values are rejected before any file is written.
- **The report is the evidence** — templates and values file used, output
  directory, CRC and field-walk results, byte-comparison or edit-diff
  result, and any warnings or checks not performed.

Chained tasks (reproducing or editing a dataset) just run the phases in
order — decode, generate, verify — each governed by the doc the table
routes it to.

## Standing limitations

- `crc=OK`/`walk=OK` do not validate every consumer-side domain constraint;
  check interdependent values against the consumer's semantics.
- The tools handle per-class files only; the concatenated stream and its
  8-byte version tail belong to the stream assembler.
- Values files must be namespaced and fully consumed; details and failure
  messages live in `generate.md`.
