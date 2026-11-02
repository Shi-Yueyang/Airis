# Generate — Produce CVC Data Files from Templates

Serialize the canonical ATP + SDMU template pair into the three per-class
data files. This is the generator; to build on existing data prefer
`edit.md`, to inspect files prefer `decode.md`.

## Format reference

Wire framing, magics, and the canonical ATP→SDMU field order live in
`references/protocol.md` in this skill's folder.

## Required inputs

- Python 3, standard library only.
- BOTH template XMLs, in any order — the reference frame always carries the
  ATP (`0x66AA5599`) and SDMU (`0xA5A59696`) fields; the generator enforces
  the set and emits fields in canonical protocol order regardless of `-t`
  order. `BSWCfgTemplate.xml` has no `<ASW SYMBOL>` and is skipped with a
  warning; any other application-field symbol is rejected.
- A values JSON (`--values`, **required on every run**) and/or `--set`
  overrides on top of it — bare template-default generation is rejected.
- A writable output directory that does not contain source files to
  preserve — generation overwrites the conventional filenames `ASW1.bin`,
  `Config2.line1`, `Config1.train` in it, and every run writes all three.

## Values format

`--values` accepts ONLY the namespaced form (the exact shape
`dump_cvc_data.py --values-out` emits) — every rule below is enforced by the
generator, no manual pre-checking needed:

```json
{ "TRAIN": { "ATP": { "TRAIN_ALLOW_SPEED": 220 }, "SDMU": { "WS_MIN_DIAMETER_1": 830 } } }
```

- Top-level groups by DIST class (`DP`/`LINE`/`TRAIN`) or by function
  (`ATP`/`SDMU`, applying across classes). Flat and class-shared keys are
  rejected — names collide across templates (`WS_MIN_DIAMETER_1`,
  `G_ACCELERATION`), so every key must state its field.
- Values are ints or `0x` hex strings; a list addresses `([k])` repeated
  entries by position, a scalar fills every entry.
- Precedence per parameter: class-scoped key > function-global key >
  template `DEFAULTVALUE` > `MINVALUE` > 0. Parameters the values file does
  not cover fall through this chain; every run prints a fallback count and
  `-v` lists each parameter's value source.
- Every key must match at least one template parameter. Stale names, wrong
  class, wrong function, or values outside `MINVALUE`/`MAXVALUE` fail
  generation with the output directory untouched — nothing partial or
  misleading is written.

## Generation

The generator is `scripts/gen_cvc_data.py`; `<skill-dir>` below is this
skill's folder. Output paths resolve relative to the current working
directory. `--help` lists all flags; `-v` prints the per-field offset table.

Every run passes a values file; ad-hoc overrides go in without editing it —
`--set` is repeatable, wins over `--values`, and comma-separated values
address `([k])` entries:

```sh
python <skill-dir>/scripts/gen_cvc_data.py \
  -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
  --values values.json \
  --set TRAIN.ATP.TRAIN_ALLOW_SPEED=220 \
  -o scratch/generated
```

The consumer's braking-domain rules are CHECKED on the effective values,
never injected: where present, `N_ITEM_SB7`/`N_ITEM_EB` counts must be at
least 1 and `SB7_Decceleration`/`EB_Decceleration` entries and `Braking
Calculation Parameter` must be non-zero, or generation fails with the
offending key named. A values file destined for the consumer must carry them.

## Verify before reporting success

Generation output is not proof. Decode the generated files with the same two
templates (`decode.md`, or directly):

```sh
python <skill-dir>/scripts/dump_cvc_data.py \
  -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
  scratch/generated/ASW1.bin scratch/generated/Config2.line1 scratch/generated/Config1.train
```

Require `crc=OK` and `walk=OK` on every field. When reproducing a known
dataset, additionally byte-compare against the reference files. Report
warnings and any checks skipped; do not widen template ranges to make a
value pass — fix the value.

## Limitations

- `crc=OK`/`walk=OK` do not validate every consumer-side domain constraint.
  Check the consumer's semantics when changing interdependent values.
- Pinned-array wrappers (`ID_MODE_LIMITED_SPEED`, `ID_SDM_LIMITED_SPEED`)
  force the written count to the template's explicit entry count; counts of
  `([k])` REPEAT groups come from their `N_ITEM` parameter — raising a count
  requires list values for every parameter in the group.
- A `PARAM` wrapper with `SYMBOL` is serialized as a nested TLV
  (`SYMBOL:4 | payload_length:4 | payload`). If the template declares
  `LENGTH`, the serialized payload must match it or generation fails.
- The 8-byte stream version tail is added by the stream assembler, not here.

## Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `the following arguments are required: --values` | Generation invoked without a values file (bare-default runs are not supported). | Always pass `--values`: capture one with `dump_cvc_data.py --values-out`, or write the keys you control. |
| `no template given for ATP/SDMU` | Only one of the pair passed. | Pass both templates. |
| `un-namespaced key … rejected` | Flat or class-shared keys in the values file. | Group as `{class: {function: {NAME: value}}}`, or use `--set`. |
| `values keys matched by no template parameter` | Stale/typo'd name, wrong class or function group. | Re-capture from the matching template revision or fix the key path. |
| `value … below MINVALUE / above MAXVALUE` | Override outside template bounds. | Correct the value; do not edit the template to widen it. |
| `count 0 leaves an empty table` / `effective value 0 breaks the consumer's braking calculation` | Braking divisor/table params left uncovered or zero by the values file. | Add the named `class.ATP.NAME` keys with valid non-zero values; do not rely on fallback. |
| `note: N value(s) not covered by the values file fell back` (informational) | Values file doesn't cover every parameter. | Check sources with `-v`; a high `MINVALUE`/`0` fallback count means the output is not a deliverable config. |
| Output differs from the reference | Values or template revision differ. | Use values captured from the same revision (`edit.md` workflow); `-t` order cannot cause this. |
