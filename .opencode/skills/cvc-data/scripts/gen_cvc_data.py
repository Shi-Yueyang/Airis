#!/usr/bin/env python3
"""Serialize an CVC configuration template into application data files.

Reads the ATP and SDMU template XMLs (each carrying <ASW @SYMBOL> with
<PARAMCLASS @DIST> classes) and writes three files (conventional names; content
is identified by magic, not name):

    PARAMCLASS @DIST -> file
    DP                 ASW1.bin        (magic 0xABABABAB)
    LINE               Config2.line1   (magic 0xACACACAC)
    TRAIN              Config1.train   (magic 0xADADADAD)

Wire format (matches the INIT config-data parser protocol, all big-endian):

    file = magic:4 | file_length:4 | field_1 | field_2 | ... | crc:4
    field_n = symbol:4 (template ASW @SYMBOL) | field_length:4 | body:field_length
    file_length counts all fields + crc (the crc itself included in the length,
    but covered CRC = magic+len+all fields, i.e. whole file minus last 4 bytes)
    crc = CRC-32/ISO-HDLC (zlib.crc32), same as the parser's ComputeCrc()

The reference frame always carries both application fields, ATP then SDMU:

    ATP  0x66AA5599        SDMU 0xA5A59696

Both templates are REQUIRED and are passed in any order (-t ATP.xml -t SDMU.xml
or -t SDMU.xml -t ATP.xml produce byte-identical output): fields are assembled
in the canonical protocol order, and every value rule is keyed by field
function/symbol, never by position. Templates without <ASW SYMBOL> (e.g. BSW)
are skipped with a warning; any other application-field symbol is rejected.

The concatenated stream tail (dp_version + project_version, 8 bytes at stream end)
is NOT generated here — it belongs to whoever assembles the files into the stream.

Field values (highest priority first). --values is REQUIRED: a run without a
values file is rejected; bare template-default generation is not supported.
    1. --values JSON overrides, NAMESPACED by DIST class and field function:
           { "DP": {"ATP": {"NID_ENGINE": 91}, "SDMU": {"WHEEL_DIAMETER_1": 840}},
             "LINE": {...}, "TRAIN": {...} }
       A top-level group keyed by a function name ("ATP", "SDMU") applies to
       that field across all classes. Un-namespaced keys (flat parameters, or
       shared keys directly inside a class group) are REJECTED: names can
       collide across templates (e.g. WS_MIN_DIAMETER_1, G_ACCELERATION), so
       every key must state the field it belongs to.
       For "([k])" repeated fields the value may be a LIST, addressing entries
       by position ("SB7_Speed": [5, 20, 45]); a scalar fills every entry.
       Names match the PARAM NAME or the name with the trailing "(...)" index
       suffix stripped (e.g. "SB7_Decceleration" matches "SB7_Decceleration([k])").
       dump_cvc_data.py --values-out emits this exact namespaced form, giving
       byte-faithful regeneration.
       Every key must match at least one template parameter: a key matched by
       no parameter (stale name, wrong class, wrong function) fails generation.
    2. --set CLASS.FUNCTION.NAME=VALUE (repeatable) — ad-hoc overrides on the
       command line, merged over the values file; also FUNCTION.NAME=VALUE for
       a whole-field override. Comma-separated values address "([k])" entries.
    3. template DEFAULTVALUE
    4. template MINVALUE
    5. 0
Parameters not covered by the values file fall through this chain; every run
prints a fallback summary and -v lists each parameter's value source.

Domain rules are CHECKED, never injected: the INIT parser divides by the ATP
braking parameters, so an N_ITEM_SB7/N_ITEM_EB count below 1, a zero
SB7_Decceleration/EB_Decceleration entry, or a zero "Braking Calculation
Parameter" fails generation before anything is written. Provide them in the
values file.

Usage:
    python <skill-dir>/scripts/gen_cvc_data.py -t ATP.xml -t SDMU.xml -o <out_dir> --values <values.json> [-v]
    python <skill-dir>/scripts/gen_cvc_data.py -t ATP.xml -t SDMU.xml -o <out_dir> --values <values.json> \
        --set TRAIN.ATP.TRAIN_ALLOW_SPEED=220 --set TRAIN.SDMU.WS_MIN_DIAMETER_1=830

    values.json values are decimal ints or 0x-prefixed hex strings; every value
    is validated against the template MINVALUE/MAXVALUE and SIZE.
"""

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

FILE_MAGICS = {"DP": 0xABABABAB, "LINE": 0xACACACAC, "TRAIN": 0xADADADAD}
DIST_FILE_NAMES = {"DP": "ASW1.bin", "LINE": "Config2.line1", "TRAIN": "Config1.train"}

# Canonical application fields of the reference frame and their wire order.
ATP_SYMBOL = 0x66AA5599
SDMU_SYMBOL = 0xA5A59696
FIELD_ORDER = {ATP_SYMBOL: 0, SDMU_SYMBOL: 1}
FIELD_SYMBOL_NAMES = {ATP_SYMBOL: "ATP", SDMU_SYMBOL: "SDMU"}


def ensure_utf8_stdio():
    """Force stdout/stderr to UTF-8.

    Windows defaults to the system code page (cp936/GBK on Chinese installs), where some
    characters used in reports raise UnicodeEncodeError. Skipped when already UTF-8 or
    when the stream has no reconfigure() (replaced by an IDE or test framework).
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        encoding = (getattr(stream, "encoding", "") or "").replace("-", "").lower()
        if encoding == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# Domain rules the consumer's INIT_check_configuration_data enforces (SB7/EB
# decelerations are divisors; the tables must not be empty). The generator
# CHECKS the effective values against these and fails loudly — it never
# injects values of its own.
NONZERO_PARAMS = {"SB7_Decceleration", "EB_Decceleration",
                  "Braking Calculation Parameter"}
MIN_TABLE_COUNTS = {"N_ITEM_SB7": 1, "N_ITEM_EB": 1}


class GenError(Exception):
    pass


def to_int(text):
    """Parse a template numeric attribute (decimal, 0x-prefixed hex, or None/empty)."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    return int(text, 16) if text.lower().startswith("0x") else int(text)


def base_name(name):
    """Strip a trailing (n)/([k]) index suffix: 'MODE_LIMITED_SPEED(7)' -> 'MODE_LIMITED_SPEED'."""
    return re.sub(r"\([^()]*\)$", "", name or "").strip()


def normalize_value(where, value):
    """Validate/coerce one override value: int, 0x-hex string, or list of either."""
    if isinstance(value, bool):
        raise GenError("%s: boolean is not a valid config value" % where)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        parsed = to_int(value)
        if parsed is None:
            raise GenError("%s: cannot parse value %r as an integer" % (where, value))
        return parsed
    if isinstance(value, list):
        if not value:
            raise GenError("%s: empty list value" % where)
        return [normalize_value("%s[%d]" % (where, i), v) for i, v in enumerate(value)]
    raise GenError("%s: value %r is not an integer, hex string, or list of those"
                   % (where, value))


def load_values(data, field_names):
    """Validate a namespaced values JSON -> {function: {"global": {...}, "DP": {...}, ...}}."""
    per_fn = {fn: {} for fn in field_names}

    def put(fn, cls, name, value):
        target = per_fn[fn].setdefault(cls, {})
        if name in target:
            raise GenError("key %r given twice for %s (%s)" % (name, fn, cls))
        target[name] = normalize_value("%s.%s.%s" % (cls, fn, name), value)

    if not isinstance(data, dict):
        raise GenError("values file must be a JSON object grouped by class or function")
    for top, group in data.items():
        if top in FILE_MAGICS:
            if not isinstance(group, dict):
                raise GenError(
                    "class group %r must map function -> {NAME: value}; un-namespaced "
                    "values are not accepted (expected {\"%s\": {\"%s\": {...}}})"
                    % (top, top, field_names[0]))
            for fn, fn_group in group.items():
                if fn not in field_names:
                    raise GenError("unknown or un-namespaced group %r in class %s of values "
                                   "file (expected %s)" % (fn, top, "/".join(field_names)))
                if not isinstance(fn_group, dict):
                    raise GenError("values for %s.%s must be an object of {NAME: value}"
                                   % (top, fn))
                for name, value in fn_group.items():
                    put(fn, top, name, value)
        elif top in field_names:
            if not isinstance(group, dict):
                raise GenError("values for function group %r must be an object of "
                               "{NAME: value}" % top)
            for name, value in group.items():
                put(top, "global", name, value)
        elif isinstance(group, dict):
            raise GenError("unknown group %r in values file (expected %s or %s)"
                           % (top, "/".join(FILE_MAGICS), "/".join(field_names)))
        else:
            raise GenError(
                "un-namespaced key %r: values must be grouped "
                "{class: {function: {NAME: value}}} or {function: {NAME: value}}; "
                "for a one-off override use --set <class>.<function>.<name>=value" % top)
    return per_fn


def apply_set(per_fn, field_names, spec):
    """Merge one --set CLASS.FUNCTION.NAME=VALUE (or FUNCTION.NAME=VALUE) into per-function values."""
    if "=" not in spec:
        raise GenError("--set expects CLASS.FUNCTION.NAME=VALUE or FUNCTION.NAME=VALUE, got %r" % spec)
    path, _, text = spec.partition("=")
    segs = path.split(".", 2)
    if segs[0] in FILE_MAGICS:
        if len(segs) != 3:
            raise GenError("--set %r: expected %s.FUNCTION.NAME=value" % (spec, segs[0]))
        cls, fn, name = segs
    elif segs[0] in field_names:
        if len(segs) != 2:
            raise GenError("--set %r: expected %s.NAME=value" % (spec, segs[0]))
        cls, (fn, name) = "global", segs
    else:
        raise GenError("--set %r: first path segment must be %s or %s"
                       % (spec, "/".join(FILE_MAGICS), "/".join(field_names)))
    if fn not in field_names:
        raise GenError("--set %r: unknown function %r (expected %s)"
                       % (spec, fn, "/".join(field_names)))
    if text.strip() == "":
        raise GenError("--set %r: empty value" % spec)
    parts = [to_int(p.strip()) for p in text.split(",")]
    if any(p is None for p in parts):
        raise GenError("--set %r: value %r is not a comma-separated integer/hex list" % (spec, text))
    value = parts[0] if len(parts) == 1 else parts
    # --set wins outright: drop any shadowed copy of the same name at other
    # nesting levels for this function (a class key would otherwise outrank a
    # --set global key).
    groups = per_fn[fn]
    for other_cls in list(groups):
        if other_cls != cls:
            groups[other_cls].pop(name, None)
    groups.setdefault(cls, {})[name] = value


class BodySerializer:
    """Flattens one PARAMCLASS into the field body byte string for one function."""

    def __init__(self, field_values, warn, field_name):
        # field_values: {"global": {name: value}} plus one dict per DIST class,
        # validated by load_values()/apply_set().
        self.field_name = field_name
        self.warn = warn
        self.global_overrides = dict(field_values.get("global", {}))
        self.pending_global = set(field_values.get("global", {}))
        self.class_overrides = {}
        self.pending_class = {}
        for cls in FILE_MAGICS:
            vals = field_values.get(cls) or {}
            if vals:
                self.class_overrides[cls] = dict(vals)
                self.pending_class[cls] = set(vals)
        self.active_class = None
        self.buf = bytearray()
        self.rows = []            # (offset, size, name, value, source) for -v report
        self.values = {}          # PARAM NAME -> encoded value (for N_ITEM lookups)

    # -- value selection ----------------------------------------------------

    def resolve_value(self, param, forced=None, index=None):
        """Return (value, source) for one leaf parameter. Sources other than
        override[...] mean the values file did not cover this parameter."""
        name = param.get("NAME")
        if forced is not None:
            value, source = forced, "forced-count"
        else:
            # Consumption tracking: a key equal to this parameter's name (or its
            # base name without the (n)/([k]) suffix) is no longer stale, even
            # when a closer-layer key wins for it.
            for key in (name, base_name(name)):
                self.pending_class.get(self.active_class, set()).discard(key)
                self.pending_global.discard(key)
            value = source = None
            layers = []
            if self.active_class is not None:
                layers.append((self.class_overrides.get(self.active_class, {}), self.active_class + "."))
            layers.append((self.global_overrides, ""))
            for table, prefix in layers:
                for key in (name, base_name(name)):
                    if key in table:
                        value, source = table[key], "override[%s%s]" % (prefix, key)
                        break
                if value is not None:
                    break
            # list values address per-index entries of REPEAT groups
            if isinstance(value, list):
                if index is None:
                    raise GenError("%s: list override only valid for '([k])' repeated fields" % name)
                if index >= len(value):
                    raise GenError("%s: list override has %d item(s), index %d requested"
                                   % (name, len(value), index))
                value = value[index]
            if value is None:
                value = to_int(param.get("DEFAULTVALUE"))
                source = "DEFAULTVALUE"
            if value is None:
                value = to_int(param.get("MINVALUE"))
                source = "MINVALUE"
            if value is None:
                value, source = 0, "default-0"

        lo, hi = to_int(param.get("MINVALUE")), to_int(param.get("MAXVALUE"))
        if lo is not None and value < lo:
            raise GenError("%s: value %s below MINVALUE %s (source %s)" % (name, value, lo, source))
        if hi is not None and value > hi:
            raise GenError("%s: value %s above MAXVALUE %s (source %s)" % (name, value, hi, source))
        return int(value), source

    def check_unused(self):
        """Fail on values keys that matched no parameter in any class."""
        stale = ["%s.%s.%s" % (cls, self.field_name, key)
                 for cls in sorted(self.pending_class)
                 for key in sorted(self.pending_class[cls])]
        stale += ["%s.%s" % (self.field_name, key) for key in sorted(self.pending_global)]
        if stale:
            raise GenError("values keys matched by no template parameter "
                           "(stale name, wrong class, or wrong function?): %s"
                           % ", ".join(stale))

    def encode_leaf(self, param, forced=None, index=None):
        size = int(param.get("SIZE"))
        value, source = self.resolve_value(param, forced=forced, index=index)
        if not 0 <= value < (1 << (8 * size)):
            raise GenError("%s: value %s does not fit %d byte(s)" % (param.get("NAME"), value, size))
        self.rows.append((len(self.buf), size, param.get("NAME"), value, source))
        self.buf += value.to_bytes(size, "big")
        self.values[param.get("NAME")] = value

    # -- structure walk -----------------------------------------------------

    def serialize_class(self, paramclass):
        self.active_class = paramclass.get("DIST")
        self.buf = bytearray()
        self.rows = []
        self.values = {}
        for param in paramclass.findall("PARAM"):
            self.serialize_param(param)
        return bytes(self.buf)

    def serialize_param(self, param):
        children = [c for c in param if c.tag in ("PARAM", "REPEAT")]
        if children:
            self.serialize_wrapper(param, children)
        else:
            self.encode_leaf(param)

    def serialize_wrapper(self, wrapper, children):
        symbol_text = wrapper.get("SYMBOL")
        header_offset = len(self.buf)
        if symbol_text:
            self.buf += b"\x00" * 8

        body_offset = len(self.buf)
        self.serialize_wrapper_contents(wrapper, children)

        if symbol_text:
            body_length = len(self.buf) - body_offset
            expected_length = to_int(wrapper.get("LENGTH"))
            if expected_length is not None and body_length != expected_length:
                raise GenError("%s: serialized wrapper length %d does not match template LENGTH %d"
                               % (wrapper.get("NAME"), body_length, expected_length))
            struct.pack_into(">II", self.buf, header_offset,
                             int(symbol_text, 16), body_length)

    def serialize_wrapper_contents(self, wrapper, children):
        repeat = wrapper.find("REPEAT")
        param_children = [c for c in children if c.tag == "PARAM"]

        if repeat is not None:
            # ISREPEAT style: N_ITEM leaf first, then REPEAT block serialized n times.
            for c in children:
                if c.tag == "PARAM":
                    self.serialize_param(c)
                elif c.tag == "REPEAT":
                    count_key = (c.get("ACCORDING") or "").split(":")[-1]
                    if count_key not in self.values:
                        raise GenError("%s: REPEAT ACCORDING references unknown %s"
                                      % (wrapper.get("NAME"), count_key))
                    for k in range(self.values[count_key]):
                        for rp in c.findall("PARAM"):
                            self.encode_leaf(rp, index=k)
            return

        # Pinned-array style: N_ITEM leaf + a fixed number of explicit entries
        # (ID_MODE_LIMITED_SPEED / ID_SDM_LIMITED_SPEED). The written count must
        # equal the number of serialized entries or the parser desynchronizes.
        if len(param_children) > 1 and (param_children[0].get("NAME") or "").startswith("N_ITEM"):
            entry_count = len(param_children) - 1
            first = param_children[0]
            try:
                wanted = self.resolve_value(first)[0]
            except GenError:
                wanted = entry_count
            if wanted != entry_count:
                self.warn("%s: default count %s != %d explicit entries; writing %d"
                          % (wrapper.get("NAME"), wanted, entry_count, entry_count))
            self.encode_leaf(first, forced=entry_count)
            for c in param_children[1:]:
                self.serialize_param(c)
            return

        for c in param_children:
            self.serialize_param(c)


def check_domain(rows, dist, function):
    """Fail when the effective values break the consumer's braking semantic checks."""
    for _off, _size, name, value, _source in rows:
        base = base_name(name)
        if base in NONZERO_PARAMS and value == 0:
            raise GenError(
                "%s.%s.%s: effective value 0 breaks the consumer's braking "
                "calculation (used as a divisor); set a non-zero value under "
                "%s.%s.%s in the values file"
                % (dist, function, name, dist, function, base))
        if base in MIN_TABLE_COUNTS and value < MIN_TABLE_COUNTS[base]:
            raise GenError(
                "%s.%s.%s: count %d leaves an empty table; the consumer's config "
                "check needs at least %d entry; set %s.%s.%s (and non-zero entry "
                "values) in the values file"
                % (dist, function, name, value, MIN_TABLE_COUNTS[base],
                   dist, function, base))


def frame_file(magic, fields):
    """Wrap application fields [(symbol, body), ...] in one file TLV + one CRC."""
    payload = b"".join(struct.pack(">II", sym, len(body)) + body for sym, body in fields)
    file_length = len(payload) + 4            # all fields + trailing CRC
    head = struct.pack(">II", magic, file_length)
    crc = zlib.crc32(head + payload) & 0xFFFFFFFF
    return head + payload + struct.pack(">I", crc)


def load_fields(template_paths, warn):
    """Return the canonical application fields [(function, symbol, {DIST: PARAMCLASS})],
    ordered by protocol (ATP, then SDMU) regardless of command-line order."""
    fields, seen = [], {}
    for path in template_paths:
        asw = ET.parse(path).getroot().find(".//ASW")
        if asw is None or not asw.get("SYMBOL"):
            warn("%s: no <ASW SYMBOL=...> element; skipped (not an application field)" % path)
            continue
        symbol = int(asw.get("SYMBOL"), 16)
        if symbol in seen:
            raise GenError("%s: ASW SYMBOL 0x%08X already used by %s" % (path, symbol, seen[symbol]))
        seen[symbol] = path
        function = asw.get("FUNCTION") or FIELD_SYMBOL_NAMES.get(symbol, "0x%08X" % symbol)
        fields.append((function, symbol, {pc.get("DIST"): pc for pc in asw.iter("PARAMCLASS")}))
    if not fields:
        raise GenError("no template with an <ASW SYMBOL=...> element was given")
    missing = ["%s (0x%08X)" % (FIELD_SYMBOL_NAMES[sym], sym)
               for sym in FIELD_ORDER if sym not in seen]
    if missing:
        raise GenError("the reference frame always carries both application fields; "
                       "no template given for %s" % ", ".join(missing))
    extra = [f for f in fields if f[1] not in FIELD_ORDER]
    if extra:
        raise GenError("unexpected application field(s) %s: the reference frame carries "
                       "only ATP and SDMU"
                       % ", ".join("%s (0x%08X)" % (fn, sym) for fn, sym, _ in extra))
    fields.sort(key=lambda f: FIELD_ORDER[f[1]])
    return fields


def main(argv=None):
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Serialize the CVC ATP + SDMU config template XMLs into ASW1.bin / Config2.line1 / Config1.train",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  python scripts/gen_cvc_data.py -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml -o out_dir --values values.json\n"
               "  python scripts/gen_cvc_data.py -t SDMU.xml -t ATP.xml -o out_dir --values values.json -v    # order does not matter\n"
               "  python scripts/gen_cvc_data.py -t ATP.xml -t SDMU.xml -o out_dir --values values.json \\\n"
               "      --set TRAIN.ATP.TRAIN_ALLOW_SPEED=220\n"
               "the template and output paths are explicit arguments; no directory layout is assumed.")
    ap.add_argument("-t", "--template", required=True, action="append",
                    help="template XML (any name/location). Both the ATP and SDMU "
                         "application-field templates are required; pass them in any "
                         "order — fields are emitted in the canonical protocol order.")
    ap.add_argument("-o", "--out-dir", required=True,
                    help="output directory for the three data files")
    ap.add_argument("--values", required=True,
                    help="JSON file (REQUIRED): namespaced overrides, "
                         "{class: {function: {PARAM name: value}}} or {function: {NAME: value}}; "
                         "bare template-default generation is not supported")
    ap.add_argument("--set", action="append", metavar="PATH=VALUE",
                    help="ad-hoc override CLASS.FUNCTION.NAME=VALUE (or FUNCTION.NAME=VALUE); "
                         "repeatable; comma-separated VALUE addresses '([k])' entries; "
                         "merged over --values")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the per-field offset table")
    args = ap.parse_args(argv)

    def warn(msg):
        print("warning: %s" % msg, file=sys.stderr)

    fields = load_fields(args.template, warn)
    names = [f[0] for f in fields]

    per_fn = {n: {} for n in names}
    if args.values:
        # utf-8-sig: tolerate a BOM (PowerShell's default UTF-8 writer adds one).
        per_fn = load_values(json.loads(Path(args.values).read_text(encoding="utf-8-sig")), names)
    for spec in args.set or []:
        apply_set(per_fn, names, spec)

    serializers = {
        fn: BodySerializer(per_fn[fn], warn, fn)
        for fn, symbol, _ in fields
    }

    dists = [d for d in FILE_MAGICS if any(d in f[2] for f in fields)]
    for dist in {pc for f in fields for pc in f[2]} - set(FILE_MAGICS):
        warn("skipping unknown PARAMCLASS DIST=%s" % dist)
    pending_writes = []
    for dist in dists:
        framed, sizes, rows = [], [], []
        for function, symbol, classes in fields:
            if dist not in classes:
                warn("%s template has no PARAMCLASS DIST=%s; field omitted" % (function, dist))
                continue
            ser = serializers[function]
            body = ser.serialize_class(classes[dist])
            check_domain(ser.rows, dist, function)
            framed.append((symbol, body))
            sizes.append("%s=%d" % (function, len(body)))
            rows.append((function, list(ser.rows)))
        pending_writes.append((dist, "+".join(sizes), rows, frame_file(FILE_MAGICS[dist], framed)))

    # Every class has been walked now: fail before touching the output directory
    # when value keys went stale.
    for ser in serializers.values():
        ser.check_unused()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for dist, sizes, rows, data in pending_writes:
        out_path = out_dir / DIST_FILE_NAMES[dist]
        out_path.write_bytes(data)

        print("%-16s DIST=%-5s body=%s file=%d crc=0x%08X"
              % (out_path.name, dist, sizes, len(data), zlib.crc32(data[:-4]) & 0xFFFFFFFF))
        if args.verbose:
            for function, frows in rows:
                print("  [%s]" % function)
                for off, size, name, value, source in frows:
                    print("    %5d  %dB  %-45s = %-12d [%s]" % (off, size, name, value, source))

    fallbacks = {"DEFAULTVALUE": 0, "MINVALUE": 0, "default-0": 0}
    for _dist, _sizes, frows, _data in pending_writes:
        for _function, rlist in frows:
            for _off, _size, _name, _value, source in rlist:
                if source in fallbacks:
                    fallbacks[source] += 1
    total = sum(fallbacks.values())
    if total:
        print("note: %d value(s) not covered by the values file fell back "
              "(DEFAULTVALUE=%d, MINVALUE=%d, 0=%d); -v lists each parameter's source"
              % (total, fallbacks["DEFAULTVALUE"], fallbacks["MINVALUE"],
                 fallbacks["default-0"]), file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GenError as e:
        print("error: %s" % e, file=sys.stderr)
        sys.exit(1)
