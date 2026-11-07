#!/usr/bin/env python3
"""把 TACN OBS↔RBC 报文（hex 文本或原始二进制）反解成 Markdown 字段报告。

报文结构来自本技能 references/protocol.md 的内置定义，不需要任何模板文件。

输入：
  * hex 文本：一行或若干行，允许空格/逗号/冒号/0x 前缀（监视工具、串口日志直接粘贴即可）
  * 原始二进制文件（--format bin 可强制；默认按"首字节是不是已知 NID_MESSAGE"自动判别）
  * --hex "03 01 ..." 直接给串
  * --split：一条文件里有多条报文时，按 L_MESSAGE 逐条解析

输出（Markdown，默认 stdout）：
  每条报文一段：帧头表 + 每个信息包一张表（起始位/位宽/字段/取值/说明），
  以及 L_MESSAGE、L_PACKET、位遍历闭合、填充位、组成规则的自洽检查表和告警清单。

纪律：报文没有 CRC，报告里的"自洽通过"只证明长度/位遍历/组成自洽，不证明 RBC 侧业务语义。
未知 NID_MESSAGE / 未收录信息包 / 位流越界一律报出来并停止该条报文的遍历，不猜字段。

用法：
    python <skill-dir>/scripts/dump_rbc_msg.py m3.hex
    python <skill-dir>/scripts/dump_rbc_msg.py --hex "0300000B083FFFFFE87D0F" -o report.md
    python <skill-dir>/scripts/dump_rbc_msg.py captures.txt --split --values-out captured.json
"""

import argparse
import binascii
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rbc_spec as S  # noqa: E402


class CliError(Exception):
    pass


HEX_CHARS = set("0123456789abcdefABCDEF")


def looks_like_hex(text):
    cleaned = re.sub(r"0[xX]", "", text)
    cleaned = re.sub(r"[\s,;:._-]", "", cleaned)
    if not cleaned:
        return False
    if any(ch not in HEX_CHARS for ch in cleaned):
        return False
    return len(cleaned) % 2 == 0


def hex_to_bytes(text):
    cleaned = re.sub(r"0[xX]", "", text)
    cleaned = re.sub(r"[\s,;:._-]", "", cleaned)
    if len(cleaned) % 2:
        raise CliError("hex 串长度是奇数（%d 位），无法按字节解析" % len(cleaned))
    try:
        return binascii.unhexlify(cleaned)
    except (binascii.Error, ValueError) as exc:
        raise CliError("hex 串解析失败：%s" % exc)


def load_input(path, forced_format):
    try:
        raw = io.open(path, "rb").read()
    except OSError as exc:
        raise CliError("读不了 %s：%s" % (path, exc))
    if forced_format == "bin":
        return raw, "原始二进制"
    if forced_format == "hex":
        return hex_to_bytes(raw.decode("latin-1")), "hex 文本"
    text = raw.decode("latin-1")
    if looks_like_hex(text):
        data = hex_to_bytes(text)
        if data and data[0] in S.MESSAGES:
            return data, "hex 文本"
        if raw and raw[0] in S.MESSAGES:
            return raw, "原始二进制（内容同时像 hex，按首字节判别）"
        return data, "hex 文本"
    return raw, "原始二进制"


def render_value(row):
    value = row["value"]
    if isinstance(value, int):
        return "%d（0x%X）" % (value, value)
    if value is None:
        return "—"
    return str(value)


def frame_rows(rows, fid):
    return [r for r in rows if r["fid"] == fid]


def render_message(result, source_note, out):
    rows = result["rows"]
    if result.get("msg") is None:
        out.write("## %s\n\n" % source_note)
        out.write("**无法反解**：%s\n\n" % "；".join(result["errors"]))
        return
    msg = result["msg"]
    out.write("## %s\n\n" % source_note)
    out.write("- 报文：**M%d %s**（%s），%d 字节，%d 个信息包\n"
              % (msg["nid"], msg["name"], result["dir"], result["size"],
                 result.get("packets", 0)))
    if result["errors"]:
        out.write("- 结论：**不可依赖** —— %s\n" % "；".join(result["errors"]))
    elif result["warnings"]:
        out.write("- 结论：**自洽但有待核实** —— %d 条告警见下\n" % len(result["warnings"]))
    else:
        out.write("- 结论：**自洽通过**（长度一致、包内 L_PACKET 一致、位遍历闭合、组成合法）\n")
    out.write("\n### 自洽检查\n\n| 检查 | 结果 | 详情 |\n|---|---|---|\n")
    for name, got, verdict in result.get("checks", []):
        out.write("| %s | %s | %s |\n" % (name, verdict, got))
    out.write("\n")

    # 帧分组：0 = 报文头，其后每个信息包一个 fid
    fids = []
    for row in rows:
        if row["fid"] not in fids:
            fids.append(row["fid"])
    for fid in fids:
        group = frame_rows(rows, fid)
        if not group:
            continue
        label = group[0]["frame"]
        if fid == 0:
            out.write("### 报文头\n\n")
        else:
            start = group[0]["offset"]
            end = max(r["offset"] + r["bits"] for r in group)
            nid_xuser = next((r for r in group if r["base"] == "NID_XUSER"), None)
            lp_rows = [r for r in group if r["base"] == "L_PACKET"]
            out.write("### %s\n\n" % label)
            out.write("起始位 %d，包内共 %d bit" % (start, end - start))
            for row in lp_rows:
                declared = row["value"] if row["value"] is not None else 0
                frame_start = start if row["occ"] == 1 else (
                    nid_xuser["offset"] if nid_xuser else start)
                computed = end - frame_start
                verdict = "OK" if declared == computed else "MISMATCH"
                out.write("；L_PACKET 声明 %d bit / 计算 %d bit（%s）"
                          % (declared, computed, verdict))
            out.write("\n\n")
        out.write("| 起始位 | 位宽 | 字段 | 取值 | 说明 |\n|---:|---:|:---|---:|:---|\n")
        for row in group:
            name = row["name"]
            if row["omitted"]:
                name = "%s（不进报文）" % name
            desc = row["desc"] or ""
            if row["depth"]:
                name = "　" * (row["depth"] - 1) + name
            out.write("| %d | %d | %s | %s | %s |\n"
                      % (row["offset"], row["bits"], name, render_value(row), desc))
        out.write("\n")

    if result["warnings"] or result["errors"]:
        out.write("### 需要处理\n\n")
        for text in result["errors"]:
            out.write("- **错误**：%s\n" % text)
        for text in result["warnings"]:
            out.write("- 告警：%s\n" % text)
        out.write("\n")


def decode_all(data, labels, options, split_mode):
    results = []
    offset = 0
    total = len(data) * 8
    while offset < total:
        result = S.decode_message(data, offset, options)
        results.append(result)
        if not split_mode:
            break
        nxt = result.get("next_pos")
        if not nxt or nxt <= offset or (result.get("msg") is None):
            break
        offset = nxt
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="反解 TACN RBC 报文并输出 Markdown 字段报告（结构内置，见 references/protocol.md）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例子：\n"
               "  python dump_rbc_msg.py m3.hex\n"
               "  python dump_rbc_msg.py --hex \"0300000B083FFFFFE87D0F\" -o report.md\n"
               "  python dump_rbc_msg.py capture.dat --format bin --split --values-out captured.json\n")
    ap.add_argument("files", nargs="*", help="hex 文本或二进制报文文件（可多个）")
    ap.add_argument("--hex", action="append", metavar="HEX", help="直接给 hex 串（可重复）")
    ap.add_argument("-o", "--out", help="报告写到该文件（默认 stdout）")
    ap.add_argument("--format", choices=("auto", "hex", "bin"), default="auto",
                    help="输入格式（默认 auto：按首字节是否已知消息号判别）")
    ap.add_argument("--split", action="store_true",
                    help="一条输入里有多条报文时，按 L_MESSAGE 逐条解析")
    ap.add_argument("--values-out", metavar="PATH",
                    help="同时把反解结果写成取值 JSON（gen_rbc_msg.py --values 可直接回喂，"
                         "用于定点修改后重新生成）")
    ap.add_argument("--p72-charset", default="utf-16-be",
                    choices=("utf-16-be", "utf-16-le", "gb18030"),
                    help="P72 纯文本编码（协议标 UTF-16，160K 表为 GB18030，联调需核实）")
    ap.add_argument("--ctcs132-sig-bits", type=int, default=8,
                    help="CTCS-132 里 NID_SIG 的位宽（协议标 n 依编号规则，默认 8）")
    args = ap.parse_args(argv)

    if not args.files and not args.hex:
        ap.print_help()
        print("\n错误: 至少给一个报文文件或 --hex 串", file=sys.stderr)
        return 1

    options = {"p72_charset": args.p72_charset, "ctcs132_sig_bits": args.ctcs132_sig_bits,
               "split": args.split}
    inputs = []
    try:
        for path in args.files:
            data, note = load_input(path, args.format)
            inputs.append((path, data, note))
        for index, text in enumerate(args.hex or [], 1):
            inputs.append(("--hex #%d" % index, hex_to_bytes(text), "hex 文本"))
    except CliError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1

    report = io.StringIO()
    report.write("# TACN RBC 报文反解报告\n\n")
    report.write("> 报文无 CRC；下表证明长度、包长、位遍历与报文组成自洽，"
                 "不证明 RBC 侧业务语义。结构来源：references/protocol.md。\n\n")

    captured = {}
    captured_names = {}
    had_error = False
    for path, data, note in inputs:
        results = decode_all(data, path, options, args.split)
        for index, result in enumerate(results, 1):
            label = path if len(results) == 1 else "%s（第 %d 条）" % (path, index)
            note_line = "%s · %s · %d 字节" % (label, note, len(data))
            render_message(result, note_line, report)
            if result.get("msg") is not None:
                msg = result["msg"]
                key = "M%d" % msg["nid"]
                captured_names[key] = captured_names.get(key, 0) + 1
                if captured_names[key] > 1:
                    key = "%s_%d" % (key, captured_names[key])
                captured[key] = S.capture_message(result)
            if result["errors"]:
                had_error = True
            for text in result["errors"]:
                print("错误: %s: %s" % (path, text), file=sys.stderr)
            for text in result["warnings"]:
                print("警告: %s: %s" % (path, text), file=sys.stderr)

    text = report.getvalue()
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("报告已写入 %s" % args.out)
    else:
        print(text)

    if args.values_out:
        if not captured:
            print("错误: 没有可导出的报文，未写 values 文件", file=sys.stderr)
            return 1
        with io.open(args.values_out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(captured, ensure_ascii=False, indent=2) + "\n")
        print("取值已写入 %s（%s）"
              % (args.values_out, "、".join(sorted(captured))))
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
