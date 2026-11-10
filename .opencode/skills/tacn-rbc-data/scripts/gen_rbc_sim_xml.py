#!/usr/bin/env python3
"""按取值 JSON 生成 RBC 模拟器的 DataTable XML 输入文件（RBC→车）。

文件格式见 references/rbc-simulator-input-xml.md：根元素 <DataTable>，每行一个
<data variable bits description value />，行序就是线序。模拟器只支持 RBC→车消息，
信息包/用户包受它自己的 C# 分派表限制（见 sim_spec.py）。

取值 JSON 与 gen_rbc_msg.py 完全相同（header + packets，字段名写法一致），
因此同一份取值可以同时产出 hex 报文和模拟器 XML。默认输出 dataTableM<n>.xml
（模拟器消息编辑器按这个名字自动加载），可用分组里的 "file"/"filename" 改名。

用法：
    python <skill-dir>/scripts/gen_rbc_sim_xml.py --list
    python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json -o out/
    python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json \
        --message M24 -o out/ -v
    python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json \
        --set m24_c80.P44.CTCS-80.N_TRAINNUM=2 --auto-length

--auto-length 只把 M3/M24 的 L_MESSAGE 和所有 *L_PACKET 写成“自动计算不填”；
简单消息的 L_MESSAGE 仍写数字（模拟器会按整数解析它）。

只依赖标准库，兼容 Python 3.8（不写类型注解，不用 match）。
"""

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_rbc_msg as G  # noqa: E402
import rbc_spec as S  # noqa: E402
import sim_spec as X  # noqa: E402


def _select_groups(doc, selected):
    groups = []
    for label, body in doc.items():
        if selected and label.strip().upper() not in selected:
            continue
        groups.append((label, body))
    if not groups:
        raise G.CliError("没有可生成的报文分组（--message 过滤后为空）")
    return groups


def _rewrite_text_length(rows):
    """UTF-16BE 时模拟器的 L_TEXT 是字节数，而协议实现按字符数计。"""
    text = None
    for variable, _bits, _desc, value, kind in rows:
        if variable == "X_TEXT(L_TEXT)" and kind == "text":
            text = value
    if text is None:
        return rows
    length = len(text.encode("utf-16-be"))
    if length > 255:
        raise X.SimError("P72 文本编码后 %d 字节，超过模拟器 L_TEXT 上限 255" % length)
    out = []
    for row in rows:
        if row[0] == "L_TEXT":
            row = (row[0], row[1], row[2], str(length), row[4])
        out.append(row)
    return out


def _prepare(doc, selected, options, charset, overrides, allow_placeholder):
    prepared = []
    for label, body in _select_groups(doc, selected):
        if not isinstance(body, dict):
            raise G.CliError("分组 %r 必须是对象" % label)
        msg, header, entries = S.values_for_message(body, label)
        gate = G.check_gate(label, body, msg, entries, "sim-xml",
                            overrides, allow_placeholder)
        X.check_supported(msg, entries)
        result = S.encode_message(msg, header, entries, options)
        X.check_encoded(result)
        plan = X.build_plan(msg, result, options.get("auto_length", False))
        if charset == "utf-16-be":
            plan["rows"] = _rewrite_text_length(plan["rows"])
        X.verify_rows(plan["rows"], msg)
        prepared.append((label, body, msg, result, gate, plan))
    return prepared


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="生成 RBC 模拟器 DataTable XML 输入文件（报文结构内置）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例子：\n"
               "  python gen_rbc_sim_xml.py --list\n"
               "  python gen_rbc_sim_xml.py --values values.json -o out/\n"
               "  python gen_rbc_sim_xml.py --values values.json --message m24_c80 -v\n")
    ap.add_argument("--values", help="取值 JSON（生成时必填；--list 时不需要）")
    ap.add_argument("--list", action="store_true",
                    help="列出模拟器支持的报文/信息包/用户包，不生成文件")
    ap.add_argument("-o", "--out-dir", default=".", help="XML 输出目录（默认当前目录）")
    ap.add_argument("--message", action="append", metavar="GROUP",
                    help="只生成指定分组（可重复；按顶层键匹配，不是消息号）")
    ap.add_argument("--set", action="append", metavar="PATH=VALUE",
                    help="临时覆盖，写法与 gen_rbc_msg.py 相同")
    ap.add_argument("--allow-placeholder", action="store_true",
                    help="允许 provenance 标为 placeholder 的占位/示例值；不加则拒绝生成")
    ap.add_argument("--auto-length", action="store_true",
                    help="M3/M24 的 L_MESSAGE 与所有 *L_PACKET 写“自动计算不填”")
    ap.add_argument("--p72-charset", default="gb18030",
                    choices=("gb18030", "utf-16-be"),
                    help="P72 文本编码（模拟器默认 GB18030，UTF-16BE 为另一设置）")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="打印每一行 XML 的变量/位宽/取值")
    args = ap.parse_args(argv)

    if args.list:
        print(X.describe_supported())
        return 0

    if not args.values:
        ap.error("缺少 --values：生成时必须给取值 JSON（只想看支持范围请用 --list）")

    options = {"p72_charset": args.p72_charset, "auto_length": args.auto_length}
    try:
        doc = G.read_values(args.values)
        overrides = set()
        for spec in args.set or []:
            overrides.add(G.apply_set(doc, spec))
        selected = [m.strip().upper() for m in args.message or []]
        prepared = _prepare(doc, selected, options, args.p72_charset,
                            overrides, args.allow_placeholder)
    except S.SpecError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1
    except X.SimError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1
    except G.CliError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1

    out_dir = args.out_dir
    try:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
    except OSError as exc:
        print("错误: 无法创建输出目录 %s：%s" % (out_dir, exc), file=sys.stderr)
        return 1

    used = {}
    written = []
    fallback_total = 0
    for label, body, msg, result, gate, plan in prepared:
        name = X.output_name(body, msg, used)
        path = os.path.join(out_dir, name)
        text = X.xml_text(plan["rows"])
        try:
            with io.open(path, "w", encoding="utf-8-sig", newline="\n") as handle:
                handle.write(text)
            X.verify_xml(path, plan["rows"], msg)
        except (OSError, X.SimError) as exc:
            print("错误: 写出/读回 %s 失败：%s" % (path, exc), file=sys.stderr)
            return 1
        written.append(path)
        fallback_total += result["fallbacks"]

        packets = ",".join(S.packet_label(n, u) for n, u in result["metas"]) or "无信息包"
        print("%-24s %-22s %3d 字节  L_MESSAGE=%d  XML 行 %d  回退 %d 字段  包=[%s]"
              % (name, "M%d %s" % (msg["nid"], msg["name"]), plan["size"],
                 plan["size"], len(plan["rows"]), result["fallbacks"], packets))
        for frame, bits in plan["packet_lengths"]:
            print("    %-16s %d bit" % (frame, bits))
        for name_, got, verdict in plan["checks"]:
            print("    %s: %s（%s）" % (name_, got, verdict))
        print("    %s" % G.audit_line(gate, result["fallbacks"]))
        for section, field in gate["placeholders"]:
            print("    占位: %s.%s" % (section, field))
        for warning in result["warnings"]:
            print("    警告: %s" % warning, file=sys.stderr)
        if args.verbose:
            for index, (variable, bits, desc, value, kind) in enumerate(plan["rows"], 1):
                print("      %3d  %3dbit  %-30s = %-18s %s"
                      % (index, bits, variable, value, desc))

    if fallback_total:
        print("提示: 共 %d 个字段没有在 values 里给值，按协议默认值回落"
              "（-v 可逐个查看）；交付前请确认这些默认值符合本轮测试意图"
              % fallback_total, file=sys.stderr)
    print("已写出 %d 个文件到 %s" % (len(written), os.path.abspath(out_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
