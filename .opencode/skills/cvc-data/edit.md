# Edit — Change Values, Preserve Everything Else

Safely modify values in existing CVC data. The existing files are the source
of truth: everything except the requested change must survive the round
trip, verified — never assumed. No new editing script is needed; this
composes the decoder (`decode.md`) and the serializer (`generate.md`).

## Rules

1. Never edit or overwrite the source files. Work in a scratch output
   directory and keep the originals untouched.
2. Decode the FULL file set (`ASW1.bin`, `Config2.line1`, `Config1.train`)
   in one dump call. Generation always rewrites all three files from
   templates + values; a class you did not decode cannot be preserved and
   would be regenerated from template defaults.
3. Change only the requested keys in the captured values JSON, keeping the
   namespaced shape intact.
4. Verify after regeneration; report the resulting diff explicitly.
5. Do not touch template files to make an edit succeed, and never widen
   `MINVALUE`/`MAXVALUE` to force a value through.

## Workflow

Script paths are relative to this skill's folder (see `SKILL.md`); command
details and all flags live in `decode.md` and `generate.md`.

1. **Decode and capture** — dump all three source files with the matching
   ATP and SDMU templates, `--values-out scratch/values.json`. Require
   `crc=OK` and `walk=OK` on every field before editing anything; a
   mismatching source is stopped on, not "fixed" by editing.
2. **Edit values** — in `values.json`, change only the requested keys under
   their correct `class → function` group. Interdependent-value rules from
   the generator apply: values outside template ranges fail; raising an
   `N_ITEM_*` count requires list values covering every `([k])` parameter of
   that group; pinned-array counts are forced to the template's entry count
   and cannot be edited this way.
3. **Regenerate** — `gen_cvc_data.py --values scratch/values.json -o
   scratch/generated` with the same template pair.
4. **Verify** —
   - Decode the generated files: `crc=OK`, `walk=OK`, no warnings.
   - **No-op case** (regenerating without edits, e.g. as a sanity check or
     to re-frame the same data): outputs must be byte-for-byte identical to
     the sources.
   - **Intentional edit**: capture values from the regenerated files with a
     second `--values-out` and diff against the edited values JSON. The set
     of differing keys must equal exactly the requested change — no
     collateral fields, no drift from interdependent defaults. Protocol
     invariants (CRC, walk, ranges) must hold for all data, changed or not.
5. **Report** — state source files, templates, which keys changed to what,
   the verification results (byte equality or the exact value diff), and any
   check not performed.

## Failure handling

- Source decode warns (`CRC MISMATCH`, `TEMPLATE/DATA MISMATCH`,
  out-of-range): stop; the source is corrupt or the templates are the wrong
  revision. Do not regenerate over data you cannot fully explain.
- Generation fails (un-namespaced key, stale key, out-of-range value): fix
  the values file; the generator writes nothing on these errors, so no
  partial output can mislead.
- Verification diff shows unexpected fields changed: treat as failure — the
  edit touched interdependent values (counts, divisor defaults) or used a
  values file from a different template revision. Re-capture and retry.

## Limits

Shared with the generator: consumer-side domain semantics are not validated
by the tools, and the concatenated-stream version tail is out of scope — see
`references/protocol.md` and `generate.md`.
