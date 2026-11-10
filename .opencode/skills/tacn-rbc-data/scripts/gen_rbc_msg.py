#!/usr/bin/env python3
"""按内置的 TACN OBS↔RBC 报文定义生成 hex 报文串。

报文结构来自本技能 references/protocol.md，脚本不含任何外部模板；输入是一份按报文分组的
取值 JSON，输出是可直接粘贴进测试仪器/监视工具的 hex 文本（默认一行大写、无分隔）。

取值 JSON 的形状（键写法与 protocol.md 一致；intent/provenance 是生成门禁，缺一不可）：

    {
      "M3": {
        "intent": {"message": "M3", "target": "both",
                   "packets": ["P15", "P44/CTCS-150"], "confirmed": true},
        "provenance": {"header": "user", "P15": "user", "P44/CTCS-150": "user"},
        "header": {"T_TRAIN": 34655, "NID_LRBG": 16681259},
        "packets": [
          {"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 3000}},
          {"packet": "P44", "user": "CTCS-150", "fields": {"Q_EOATYPE": 0, "NID_ENGINE": 90}}
        ]
      }
    }

  * intent 必须由用户确认后手写：confirmed=true；target 为 hex / sim-xml / both；
    packets 必须与实际包顺序完全一致；声明不符、缺 confirmed 都会直接失败。
  * provenance 给每个报文段标注来源：user（用户给的）、decoded（反解导出）、
    placeholder（占位/示例值）。值可以是段级字符串，也可以是 {字段: 来源} 对象。
    含 placeholder 时必须显式加 --allow-placeholder，否则不生成任何文件。

  * 顶层每个键生成一个 .hex 文件；键名就是报文标签（M3/M24/…），也可以用
    {"ma_523": {"message": "M3", ...}} 让文件名与报文类型分开。
  * packets 是数组，顺序即空口排列顺序（同一报文里可以有多个 P65/P66/P44）。
  * 字段名写法：NAME、NAME(k)（迭代组里的项）、NAME#n（同名字段按声明顺序第 n 个）、
    NID_LRBG / NID_PRVBG（24 bit 复合键，自动拆成 NID_C/NID_BG）。
  * 取值：十进制整数、0x 十六进制串、迭代组的列表（用不到的位置写 null）、
    双 IP 写成 "172.16.27.100.172.16.28.100"、纯文本给字符串、数据块给 hex 串。
  * --set 可临时覆盖：M3.header.NID_BG=523 / M3.P15.L_ENDSECTION=3000 /
    M3.P65[2].NID_TSR=128 / M3.P44.CTCS-150.NID_ENGINE=90。

生成纪律：报文没有 CRC，所以生成结果一律用 dump_rbc_msg.py 反解回来核对（脚本会自己打印
L_MESSAGE/L_PACKET/位遍历闭合与回退统计；selftest_rbc_msg.py 是可执行的协议回归）。

用法：
    python <skill-dir>/scripts/gen_rbc_msg.py --describe M155
    python <skill-dir>/scripts/gen_rbc_msg.py --values values.json -o out/
    python <skill-dir>/scripts/gen_rbc_msg.py --values values.json --message M3 -o out/ -v
    python <skill-dir>/scripts/gen_rbc_msg.py --values values.json \
        --set M3.P15.L_ENDSECTION=3000 --set M24.header.NID_BG=523

--describe 只打印消息结构（方向、定长、帧头、预定义变量、必选/可选信息包、values 骨架），
不生成文件，也不需要 --values。查消息结构优先用它，不要到 rbc_spec.py 里搜 "M155"。
"""

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rbc_spec as S  # noqa: E402


class CliError(Exception):
    pass


def parse_scalar(text):
    """把 --set 的值解析成 int / 列表 / 字符串。"""
    text = text.strip()
    if text == "":
        raise CliError("--set 的取值不能为空")
    if text.lower().startswith("0x") or re.match(r"^-?\d+$", text):
        return S.parse_int("--set", text)
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        out = []
        for part in parts:
            out.append(None if part == "" else S.parse_int("--set", part))
        return out
    return text


def split_path(spec):
    if "=" not in spec:
        raise CliError("--set 需要 <分组>.<位置>.<字段>=<值> 的形式，收到 %r" % spec)
    path, _sep, text = spec.partition("=")
    segs = [s for s in path.split(".") if s]
    if len(segs) < 3:
        raise CliError("--set %r：路径太短，至少是 <分组>.header.<字段> 或 "
                       "<分组>.<信息包>.<字段>" % spec)
    return segs, text.strip()


def locate_packets(body):
    packets = body.setdefault("packets", [])
    if not isinstance(packets, list):
        raise CliError("packets 必须是数组")
    return packets


def apply_set(doc, spec):
    segs, text = split_path(spec)
    group, rest = segs[0], segs[1:]
    if group not in doc:
        doc[group] = {}
    body = doc[group]
    if not isinstance(body, dict):
        raise CliError("分组 %r 必须是对象" % group)
    value = parse_scalar(text)
    if rest[0] == "header":
        if len(rest) != 2:
            raise CliError("--set %r：报文头字段路径应为 <分组>.header.<字段>" % spec)
        body.setdefault("header", {})[rest[1]] = value
        return set_path(group, "header", rest[1])
    match = re.match(r"^(P\d+|CTCS-\d+)(?:\[(\d+)\])?$", rest[0])
    if not match:
        raise CliError("--set %r：%r 不是 P15 / P44 / CTCS-150 这样的包标识"
                       % (spec, rest[0]))
    label = match.group(1)
    index = int(match.group(2)) if match.group(2) else None
    packets = locate_packets(body)
    if label.upper() == "P44" and len(rest) == 3 \
            and str(rest[1]).upper().startswith("CTCS-"):
        # <分组>.P44.CTCS-150.<字段>
        label = str(rest[1]).upper()
        rest = ["P44", label, rest[2]]
    if label.startswith("CTCS-"):
        # <分组>.P44.CTCS-150.<字段>
        if len(rest) != 3:
            raise CliError("--set %r：用户包路径应为 <分组>.P44[.n].CTCS-<号>.<字段>" % spec)
        user = label
        field = rest[2]
        for entry in packets:
            if str(entry.get("packet", "")).upper() == "P44" \
                    and str(entry.get("user", "")).upper() == user:
                entry.setdefault("fields", {})[field] = value
                return set_path(group, "P44/%s" % user, field)
        packets.append({"packet": "P44", "user": user, "fields": {field: value}})
        return set_path(group, "P44/%s" % user, field)
    if len(rest) != 2:
        raise CliError("--set %r：信息包字段路径应为 <分组>.<信息包>.<字段>" % spec)
    field = rest[1]
    seen = 0
    for entry in packets:
        if str(entry.get("packet", "")).upper() == label.upper():
            seen += 1
            if index is None or seen == index:
                entry.setdefault("fields", {})[field] = value
                return set_path(group, "P%d" % int(label[1:]), field)
    if index is not None:
        raise CliError("--set %r：第 %d 个 %s 不存在（报文里只有 %d 个）"
                       % (spec, index, label, seen))
    packets.append({"packet": label, "fields": {field: value}})
    return set_path(group, "P%d" % int(label[1:]), field)


def set_path(group, section, field):
    """--set 覆盖路径的规范形式，用于把被覆盖字段记为 user 来源。"""
    return "%s.%s.%s" % (group, section, re.split(r"[#(]", str(field))[0])


def safe_name(label):
    name = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(label)).strip("_")
    return name or "message"


def read_values(path):
    try:
        text = io.open(path, encoding="utf-8-sig").read()
    except OSError as exc:
        raise CliError("读不了 values 文件 %s：%s" % (path, exc))
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise CliError("values 文件不是合法 JSON（%s）：%s" % (path, exc))
    if not isinstance(doc, dict):
        raise CliError("values 文件的顶层必须是 {报文分组: {...}}")
    for reserved in ("intent", "provenance"):
        if reserved in doc:
            raise CliError("intent/provenance 必须写在报文分组里（例如 doc[\"M3\"][\"intent\"]），"
                           "不能放在顶层；%r 会被当成报文分组" % reserved)
    return doc


# ---------------------------------------------------------------------------
# 生成门禁：intent + provenance
# ---------------------------------------------------------------------------
GATE_HINT = "生成门禁见 references/gate.md；确认单未填完不得生成。"
SOURCE_VALUES = ("user", "decoded", "placeholder")
TARGETS = ("hex", "sim-xml", "both")


def packet_code(spec, user_spec=None):
    """信息包段标识：P15 / P44/CTCS-150。intent.packets 与 provenance 都用它。"""
    if spec.get("nid") == 44:
        return "P44/CTCS-%d" % user_spec["nid"]
    return "P%d" % spec["nid"]


def normalize_message(value):
    text = str(value).strip().upper()
    match = re.match(r"^M(\d+)$", text)
    if match:
        return "M%d" % int(match.group(1))
    match = re.match(r"^(\d+)$", text)
    if match:
        return "M%d" % int(match.group(1))
    return text


def normalize_packet(value):
    text = str(value).strip().upper().replace(" ", "")
    if text.startswith("CTCS-"):
        return "P44/" + text
    if text.startswith("P44/"):
        return text
    match = re.match(r"^P(\d+)$", text)
    if match:
        return "P%d" % int(match.group(1))
    return text


def base_field(name):
    return re.split(r"[#(]", str(name))[0]


def section_rule(prov, section):
    if section in prov:
        return prov[section], section
    if section.startswith("P44/") and "P44" in prov:
        return prov["P44"], "P44"
    if "*" in prov:
        return prov["*"], "*"
    return None, section


def field_source(rule, key, field):
    if isinstance(rule, str):
        return rule, key
    if not isinstance(rule, dict):
        return "<非法来源>", key
    if field in rule:
        return rule[field], key + "." + field
    base = base_field(field)
    if base in rule:
        return rule[base], key + "." + base
    if "*" in rule:
        return rule["*"], key + ".*"
    return None, key


def _overridden(overrides, label, section, field):
    return set_path(label, section, field) in overrides


def check_gate(label, body, msg, entries, target, overrides, allow_placeholder):
    """校验 intent/provenance；不通过就抛错，一个文件都不写。

    返回审计统计：{counts: {user/decoded/placeholder}, placeholders: [(段, 字段)]}。
    """
    problems = []
    intent = body.get("intent")
    if not isinstance(intent, dict):
        problems.append("缺少 intent：先按 references/gate.md 的确认单写 "
                        "intent{message,target,packets,confirmed}")
    else:
        if intent.get("confirmed") is not True:
            problems.append("intent.confirmed 不是 true：需求确认单尚未完成，不得生成")
        declared_target = intent.get("target")
        if declared_target not in TARGETS:
            problems.append("intent.target 必须是 %s，收到 %r"
                            % ("/".join(TARGETS), declared_target))
        elif declared_target != "both" and declared_target != target:
            problems.append("这份取值标的是 %s，不能用来生成 %s；"
                            "要两种产物都生成请写 \"target\": \"both\""
                            % (declared_target, target))
        declared_msg = normalize_message(intent.get("message", ""))
        actual_msg = "M%d" % msg["nid"]
        if declared_msg != actual_msg:
            problems.append("intent.message 声明 %r，实际分组是 %s"
                            % (intent.get("message"), actual_msg))
        declared = intent.get("packets")
        actual = [packet_code(spec, user_spec) for spec, user_spec, _fields in entries]
        if not isinstance(declared, list):
            problems.append("intent.packets 必须是数组（无信息包写 []），收到 %r" % (declared,))
        else:
            got = [normalize_packet(item) for item in declared]
            if got != actual:
                problems.append("intent.packets 声明 %s，实际包顺序是 %s；"
                                "组成不一致不得生成" % (got, actual))

    counts = {"user": 0, "decoded": 0, "placeholder": 0}
    placeholders = []
    prov = body.get("provenance")
    if not isinstance(prov, dict):
        problems.append("缺少 provenance：逐段标注来源 user/decoded/placeholder")
        prov = {}

    merged = []
    index = {}
    if isinstance(body.get("header"), dict) and body["header"]:
        merged.append(["header", list(body["header"].keys())])
        index["header"] = 0
    for spec, user_spec, fields in entries:
        section = packet_code(spec, user_spec)
        if section not in index:
            index[section] = len(merged)
            merged.append([section, []])
        for name in fields:
            if name not in merged[index[section]][1]:
                merged[index[section]][1].append(name)

    known = set(name for name, _fields in merged) | {"*"}
    if any(name.startswith("P44/") for name, _fields in merged):
        known.add("P44")
    for key in sorted(prov):
        if key not in known:
            problems.append("provenance 键 %r 没有对应的报文段（可用：%s）"
                            % (key, "、".join(sorted(known))))

    for section, fields in merged:
        rule, key = section_rule(prov, section)
        if rule is None:
            if fields and all(_overridden(overrides, label, section, f) for f in fields):
                rule, key = "user", "(--set)"
            else:
                problems.append("provenance 缺少 %r 段：写 \"%s\": \"user\"（或 "
                                "\"decoded\"/\"placeholder\"）" % (section, section))
                continue
        if isinstance(rule, str):
            if rule not in SOURCE_VALUES:
                problems.append("provenance.%s 的来源 %r 不合法（只能是 %s）"
                                % (key, rule, "/".join(SOURCE_VALUES)))
                continue
            for name in fields:
                source = "user" if _overridden(overrides, label, section, name) else rule
                counts[source] += 1
                if source == "placeholder":
                    placeholders.append((section, name))
            continue
        if not isinstance(rule, dict):
            problems.append("provenance.%s 必须是来源字符串或 {字段: 来源} 对象" % key)
            continue
        for name in rule:
            if name == "*":
                continue
            if name not in fields and base_field(name) not in [base_field(f) for f in fields]:
                problems.append("provenance.%s 里的字段 %r 不在该段取值里" % (key, name))
        for name in fields:
            source, _where = field_source(rule, key, name)
            if _overridden(overrides, label, section, name):
                source = "user"
            if source is None:
                problems.append("provenance.%s 没有给字段 %r 标注来源" % (key, name))
                continue
            if source not in SOURCE_VALUES:
                problems.append("provenance.%s.%s 的来源 %r 不合法（只能是 %s）"
                                % (key, name, source, "/".join(SOURCE_VALUES)))
                continue
            counts[source] += 1
            if source == "placeholder":
                placeholders.append((section, name))

    if placeholders and not allow_placeholder:
        listed = "、".join("%s.%s" % (section, name) for section, name in placeholders)
        problems.append("有 %d 个占位字段（%s）；确认可用占位值后加 --allow-placeholder，"
                        "否则请补真实取值" % (len(placeholders), listed))
    if problems:
        raise S.SpecError("\n".join(["生成门禁未通过（%s）：" % label]
                                    + ["- %s" % text for text in problems]
                                    + [GATE_HINT]))
    return {"counts": counts, "placeholders": placeholders}


def audit_line(gate, fallbacks):
    counts = gate["counts"]
    text = "审计: 用户 %d / 解码 %d / 占位 %d / 协议默认 %d" % (
        counts["user"], counts["decoded"], counts["placeholder"], fallbacks)
    return text


def hex_text(data, style, per_line):
    raw = data.hex().upper()
    if style == "plain":
        return raw
    if style == "spaced":
        return " ".join(raw[i:i + 2] for i in range(0, len(raw), 2))
    step = per_line * 2
    return "\n".join(raw[i:i + step] for i in range(0, len(raw), step))


_MISSING = object()


def _describe_source(item):
    """字段的取值来源：固定 / 默认 / 默认哨兵 / 需给值。"""
    dflt = item.get("dflt", _MISSING)
    sent = item.get("sent")
    if dflt is not _MISSING:
        text = "默认 %s" % _show(dflt)
        if sent is not None and sent == dflt:
            text = "默认哨兵 %s" % _show(dflt)
        lo, hi = item.get("lo"), item.get("hi")
        if lo is not None and hi is not None and lo == hi == dflt:
            text = "固定 %s" % _show(dflt)
        enum = item.get("enum")
        if enum is not None and dflt in enum:
            text += "（%s）" % enum[dflt]
        return text
    if sent is not None:
        return "需给值（哨兵 %s）" % _show(sent)
    return "需给值"


def _describe_header_rows(msg):
    """把帧头 + 预定义变量展开成 (偏移, 位宽, 字段, 来源)；复合键合并成 NID_LRBG。"""
    items = (S.HEADER_G2T if msg["dir"] == S.G2T else S.HEADER_T2G) + msg["pre"]
    rows = []
    offset = 0
    index = 0
    while index < len(items):
        item = items[index]
        comp = item.get("composite")
        if comp and index + 1 < len(items) and items[index + 1].get("composite") == comp:
            nxt = items[index + 1]
            bits = item.get("bits", 0) + nxt.get("bits", 0)
            source = "默认 NID_C=%s / NID_BG=%s" % (_show(item.get("dflt", 0)),
                                                   _show(nxt.get("dflt", 0)))
            rows.append((offset, bits, comp, source))
            offset += bits
            index += 2
            continue
        role = item.get("role")
        if role == "nid_message":
            source = "固定 %d" % msg["nid"]
        elif role == "l_message":
            if msg["fixed_len"]:
                source = "自动计算（%d 字节）" % msg["fixed_len"]
            else:
                source = "自动计算"
        elif item.get("kind") not in (None, "leaf"):
            source = "%s（见 protocol.md）" % item.get("kind")
        else:
            source = _describe_source(item)
        rows.append((offset, item.get("bits", 0), item.get("name", "?"), source))
        offset += item.get("bits", 0)
        index += 1
    return rows, offset


def _describe_packets(msg):
    rows = []
    for group in msg["req"]:
        rows.append(("必选", " 或 ".join(S.packet_label(n) for n in group)))
    for nid in msg["opt"]:
        rows.append(("可选", S.packet_label(nid)))
    for user in sorted(msg["users"]):
        kind = msg["users"][user]
        qualifier = {"opt": "可选", "cond": "条件可选",
                     "ack": "可选（M_ACK=1）"}.get(kind, kind)
        rows.append((qualifier, "P44/CTCS-%d %s" % (user, S.USER_PACKETS[user]["name"])))
    return rows


def _describe_skeleton(msg):
    """给出 values 的形状；值一律写 <待确认>，直接复制会触发门禁失败。"""
    header = {}
    seen = set()
    items = (S.HEADER_G2T if msg["dir"] == S.G2T else S.HEADER_T2G) + msg["pre"]
    pending = "<待确认>"
    for item in items:
        if item.get("role") in ("nid_message", "l_message"):
            continue
        comp = item.get("composite")
        if comp:
            if comp in seen:
                continue
            seen.add(comp)
            header[comp] = pending
            continue
        name = item.get("name")
        if name in seen:
            suffix = 2
            while "%s#%d" % (name, suffix) in seen:
                suffix += 1
            name = "%s#%d" % (name, suffix)
        seen.add(name)
        header[name] = pending
    body = {
        "intent": {"message": "M%d" % msg["nid"], "target": "both",
                   "packets": [pending], "confirmed": False},
        "provenance": {"header": pending, "*": pending},
        "header": header,
        "packets": [],
    }
    return {"M%d" % msg["nid"]: body}


def describe_message(label, out=None):
    """打印一条消息的结构；不生成文件，也不依赖 values。"""
    out = out or sys.stdout
    msg = S.resolve_message(label)
    is_pure_header = not msg["pre"] and not msg["req"] and not msg["opt"] and not msg["users"]
    direction = S.DIR_NAME[msg["dir"]]
    suffix = "，纯帧头" if is_pure_header else ""
    print("M%d %s（%s%s）" % (msg["nid"], msg["name"], direction, suffix), file=out)
    if msg["fixed_len"]:
        packet_note = "，信息包：无" if is_pure_header else ""
        print("L_MESSAGE = %d（固定）%s" % (msg["fixed_len"], packet_note), file=out)
    else:
        print("L_MESSAGE = 由内容计算（≤ %d 字节）" % S.MAX_MESSAGE_BYTES, file=out)
    if msg.get("note"):
        print("说明：%s" % msg["note"], file=out)

    rows, consumed = _describe_header_rows(msg)
    print("\n帧头 / 预定义变量：", file=out)
    print("  偏移  位宽  字段                  取值", file=out)
    for offset, bits, name, source in rows:
        print("  %4d  %4d  %-20s %s" % (offset, bits, name, source), file=out)
    if msg["fixed_len"]:
        pad = msg["fixed_len"] * 8 - consumed
        if pad > 0:
            print("  %4d  %4d  %-20s %s" % (consumed, pad, "（填充位）", "全 1"), file=out)

    packets = _describe_packets(msg)
    print("\n信息包：", file=out)
    if not packets:
        print("  无", file=out)
    else:
        for qualifier, text in packets:
            print("  - %s：%s" % (qualifier, text), file=out)

    print("\nvalues 骨架（不可直接生成：先把 <待确认> 换成用户确认值，"
          "并填 intent/provenance；见 references/gate.md）：", file=out)
    print(json.dumps(_describe_skeleton(msg), ensure_ascii=False, separators=(",", ":")), file=out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="生成 TACN RBC 报文 hex（报文结构内置，见 references/protocol.md）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例子：\n"
               "  python gen_rbc_msg.py --describe M155\n"
               "  python gen_rbc_msg.py --values values.json -o out/\n"
               "  python gen_rbc_msg.py --values values.json --message M3 -o out/ -v\n"
               "  python gen_rbc_msg.py --values values.json --set M3.P15.L_ENDSECTION=3000\n")
    ap.add_argument("--values", help="取值 JSON（生成时必填；--describe 时不需要）")
    ap.add_argument("--describe", metavar="M155",
                    help="只打印该消息的结构（方向/定长/帧头/必选包/values 骨架），不生成文件")
    ap.add_argument("-o", "--out-dir", default=".", help="hex 输出目录（默认当前目录）")
    ap.add_argument("--message", action="append", metavar="M3",
                    help="只生成指定报文（可重复）；默认生成 values 里的全部分组")
    ap.add_argument("--set", action="append", metavar="PATH=VALUE",
                    help="临时覆盖：M3.header.NID_BG=523 / M3.P15.L_ENDSECTION=3000 / "
                         "M3.P44.CTCS-150.NID_ENGINE=90；逗号分隔表示列表")
    ap.add_argument("--allow-placeholder", action="store_true",
                    help="允许 provenance 标为 placeholder 的占位/示例值；不加则拒绝生成")
    ap.add_argument("--hex-style", choices=("plain", "spaced", "lines"), default="plain",
                    help="hex 排版：plain 一行连续（默认）、spaced 每字节空格、lines 每行若干字节")
    ap.add_argument("--hex-per-line", type=int, default=16, help="--hex-style lines 时每行字节数")
    ap.add_argument("--p72-charset", default="utf-16-be",
                    choices=("utf-16-be", "utf-16-le", "gb18030"),
                    help="P72 纯文本编码（协议标 UTF-16，160K 表为 GB18030，联调需核实）")
    ap.add_argument("--ctcs132-sig-bits", type=int, default=8,
                    help="CTCS-132 里 NID_SIG 的位宽（协议标 n 依编号规则，默认 8）")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个字段的偏移/位宽/取值来源")
    args = ap.parse_args(argv)

    if args.describe:
        try:
            return describe_message(args.describe)
        except (S.SpecError, CliError) as exc:
            print("错误: %s" % exc, file=sys.stderr)
            return 1

    if not args.values:
        ap.error("缺少 --values：生成时必须给取值 JSON（只想看结构请用 --describe M155）")

    options = {"p72_charset": args.p72_charset, "ctcs132_sig_bits": args.ctcs132_sig_bits}
    try:
        doc = read_values(args.values)
        overrides = set()
        for spec in args.set or []:
            overrides.add(apply_set(doc, spec))

        selected = [m.strip().upper() for m in args.message or []]
        groups = []
        for label, body in doc.items():
            if selected and label.strip().upper() not in selected:
                continue
            groups.append((label, body))
        if not groups:
            raise CliError("没有可生成的报文分组（--message 过滤后为空）")

        prepared = []
        for label, body in groups:
            if not isinstance(body, dict):
                raise CliError("分组 %r 必须是对象" % label)
            msg, header, entries = S.values_for_message(body, label)
            gate = check_gate(label, body, msg, entries, "hex",
                              overrides, args.allow_placeholder)
            result = S.encode_message(msg, header, entries, options)
            prepared.append((label, msg, result, gate))
    except S.SpecError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1
    except CliError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1

    out_dir = args.out_dir
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    used = {}
    written = []
    fallback_total = 0
    for label, msg, result, gate in prepared:
        base = safe_name(label)
        count = used.get(base, 0) + 1
        used[base] = count
        name = base if count == 1 else "%s_%d" % (base, count)
        path = os.path.join(out_dir, name + ".hex")
        text = hex_text(result["data"], args.hex_style, args.hex_per_line)
        with io.open(path, "w", encoding="ascii", newline="\n") as handle:
            handle.write(text + "\n")
        written.append(path)
        fallback_total += result["fallbacks"]

        packets = ",".join(S.packet_label(n, u) for n, u in result["metas"]) or "无信息包"
        print("%-28s %-22s %3d 字节  L_MESSAGE=%d  回退 %d 字段  包=[%s]"
              % (os.path.basename(path), "M%d %s" % (msg["nid"], msg["name"]),
                 len(result["data"]), len(result["data"]), result["fallbacks"], packets))
        print("    hex: %s" % result["data"].hex().upper())
        for name, got, verdict in result["checks"]:
            print("    %s: %s（%s）" % (name, got, verdict))
        print("    %s" % audit_line(gate, result["fallbacks"]))
        for section, field in gate["placeholders"]:
            print("    占位: %s.%s" % (section, field))
        for warning in result["warnings"]:
            print("    警告: %s" % warning, file=sys.stderr)
        if args.verbose:
            for row in result["rows"]:
                if row["omitted"]:
                    continue
                print("      %5d %3dbit  %-34s = %-14s [%s]"
                      % (row["offset"], row["bits"], row["name"],
                         _show(row["value"]), row["source"]))

    if fallback_total:
        print("提示: 共 %d 个字段没有在 values 里给值，按协议默认值回落（-v 可逐个查看来源）；"
              "交付前请确认这些默认值符合本轮测试意图" % fallback_total, file=sys.stderr)
    print("已写出 %d 个文件到 %s" % (len(written), os.path.abspath(out_dir)))
    return 0


def _show(value):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
