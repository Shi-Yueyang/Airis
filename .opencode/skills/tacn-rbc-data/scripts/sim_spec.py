#!/usr/bin/env python3
"""把 rbc_spec 的编码结果渲染成 RBC 模拟器 DataTable XML 行，供 gen_rbc_sim_xml.py 使用。

RBC 模拟器的 XML 是“按线序排列的定宽字段表”，格式见
references/rbc-simulator-input-xml.md。模拟器只支持 RBC→车 消息，且信息包/用户包
受它自己的 C# 分派表限制；本模块在 rbc_spec 的协议结果之上做三件事：

  * 按模拟器模板改字段名（P15_L_PACKET、X_TEXT(L_TEXT)、GROUP_NID_ENGINE(0)、
    Q_EOATYPE 两行等）；
  * 补模拟器模板有、协议实现没有的占位行（P68 的 D_TRACKINIT）；
  * 去掉模拟器不打包的行（CTCS-132 的信号状态迭代组）。

字段位宽、取值和长度仍以 rbc_spec 的编码结果为准；本模块不重新计算报文内容。

只依赖标准库，兼容 Python 3.8（不写类型注解，不用 match）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rbc_spec as S  # noqa: E402

PLACEHOLDER = "自动计算不填"

# 模拟器 §6.1 的 RBC→车消息表；车→地消息不是模拟器输入。
SIM_MESSAGES = {
    2: "目视授权",
    3: "行车许可 MA",
    6: "确认退出冒进防护模式",
    8: "列车数据确认",
    15: "有条件紧急停车",
    16: "无条件紧急停车",
    18: "取消紧急停车",
    24: "通常消息",
    32: "系统版本",
    34: "确认前方轨道空闲 TAF 请求",
    39: "会话结束确认",
    41: "接受列车",
    45: "分配坐标系",
}

# 模拟器 C# 分派表支持的信息包（§6.2）。M3/M24 的具体组成仍由 protocol.md 约束。
SIM_PACKETS = {3, 5, 15, 21, 27, 41, 42, 44, 57, 58, 63, 65, 66, 68, 72, 80, 131}

# 模拟器 §6.3 支持的 P44 内层用户包。CTCS-51 只有模板、没有分派分支。
SIM_USERS = {80, 81, 82, 83, 131, 132, 150, 152}

# 模拟器模板里的字段说明。只用于 XML 的 description 属性，模拟器不解析。
FIELD_DESC = {
    "NID_MESSAGE": "消息标识号",
    "L_MESSAGE": "消息长度(字节)",
    "T_TRAIN": "车载设备时钟",
    "M_ACK": "确认标识位",
    "NID_C": "地区编号",
    "NID_BG": "应答器标识号",
    "NID_ENGINE": "列车标识号",
    "NID_OPERATIONAL": "车次号",
    "V_TRAIN": "列车速度",
    "NID_PACKET": "信息包标识号",
    "Q_DIR": "验证方向",
    "L_PACKET": "信息包位数",
    "NID_XUSER": "CTCS信息包标识码",
    "Q_SCALE": "距离/长度分辨率",
    "D_SR": "至目视授权终点距离",
    "D_LINK": "至下一链接应答器的距离",
    "Q_NEWCOUNTRY": "是否新国家/地区",
    "Q_LINKORIENTATION": "链接方向",
    "Q_LINKREACTION": "链接反应",
    "Q_LOCACC": "链接允许安装偏差",
    "V_LOA": "允许速度",
    "T_LOA": "允许速度有效时间",
    "L_SECTION": "区段长度",
    "Q_SECTIONTIMER": "区段定时器标识",
    "T_SECTIONTIMER": "区段定时器时间",
    "D_SECTIONTIMERSTOPLOC": "区段定时器停车位置",
    "L_ENDSECTION": "MA 末区段长度",
    "Q_ENDTIMER": "末区段定时器标识",
    "T_ENDTIMER": "末区段定时器时间",
    "D_ENDTIMERSTARTLOC": "末区段定时器起点",
    "Q_DANGERPOINT": "危险点标识",
    "D_DP": "危险点距离",
    "V_RELEASEDP": "危险点开口速度",
    "Q_OVERLAP": "保护区段标识",
    "D_STARTOL": "保护区段起点距离",
    "T_OL": "保护区段时间",
    "D_OL": "保护区段长度",
    "V_RELEASEOL": "保护区段开口速度",
    "D_GRADIENT": "坡度变化点距离",
    "Q_GDIR": "坡度方向",
    "G_A": "安全坡度",
    "D_STATIC": "静态速度变化点距离",
    "V_STATIC": "静态速度",
    "Q_FRONT": "前端/尾端有效",
    "NC_DIFF": "列车类型",
    "V_DIFF": "速度差",
    "D_LEVELTR": "等级转换点距离",
    "M_LEVELTR": "转换目标等级",
    "NID_STM": "STM 标识",
    "L_ACKLEVELTR": "等级转换确认距离",
    "T_MAR": "MA 请求时间",
    "T_TIMEOUTRQST": "MA 请求超时",
    "T_CYCRQST": "循环请求间隔",
    "T_CYCLOC": "位置报告时间间隔",
    "D_CYCLOC": "位置报告距离间隔",
    "M_LOC": "位置报告特殊地点",
    "NID_TSR": "临时限速编号",
    "D_TSR": "至临时限速起点距离",
    "L_TSR": "临时限速长度",
    "V_TSR": "临时限速速度",
    "Q_TRACKINIT": "初始化线路条件标识",
    "D_TRACKINIT": "初始化线路条件距离",
    "D_TRACKCOND": "线路条件距离",
    "L_TRACKCOND": "线路条件长度",
    "M_TRACKCOND": "线路条件类型",
    "Q_TEXTCLASS": "文本类别",
    "Q_TEXTDISPLAY": "文本显示条件",
    "D_TEXTDISPLAY": "文本显示距离",
    "M_MODETEXTDISPLAY": "文本显示模式",
    "M_LEVELTEXTDISPLAY": "文本显示等级",
    "M_MODETEXTDISPLAY_END": "文本结束显示模式",
    "M_LEVELTEXTDISPLAY_END": "文本结束显示等级",
    "L_TEXTDISPLAY": "文本显示长度",
    "T_TEXTDISPLAY": "文本显示时间",
    "Q_TEXTCONFIRM": "文本确认要求",
    "L_TEXT": "文本长度",
    "X_TEXT(L_TEXT)": "文本内容",
    "D_MAMODE": "调车/引导模式距离",
    "M_MAMODE": "调车/引导模式",
    "V_MAMODE": "调车/引导模式速度",
    "L_MAMODE": "调车/引导模式长度",
    "L_ACKMAMODE": "调车/引导模式确认长度",
    "Q_RBC": "RBC 会话命令",
    "NID_RBC": "RBC 标识",
    "NID_RADIO": "无线地址",
    "Q_SLEEPSESSION": "休眠会话标识",
    "D_RBCTR": "至 RBC 移交点距离",
    "D_VALIDNV": "国家参数有效期",
    "V_NVSHUNT": "调车允许速度",
    "V_NVSTFF": "值守允许速度",
    "V_NVONSIGHT": "目视允许速度",
    "V_NVUNFIT": "不可用允许速度",
    "V_NVREL": "释放允许速度",
    "D_NVROLL": "溜逸距离",
    "Q_NVSRBKTRG": "制动目标标识",
    "Q_NVEMRRLS": "紧急释放标识",
    "V_NVALLOWOVTRP": "允许越站速度",
    "V_NVSUPOVTRP": "监督越站速度",
    "D_NVOVTRP": "越站距离",
    "T_NVOVTRP": "越站时间",
    "D_NVPOTRP": "越站后距离",
    "M_NVCONTACT": "接触网状态",
    "T_NVCONTACT": "接触网监控时间",
    "M_NVDERUN": "派生运行标识",
    "D_NVSTFF": "值守距离",
    "Q_NVDRIVER_ADHES": "司机黏着标识",
    "GROUP_ID": "编组 ID",
    "N_TRAINNUM": "编组列车数量",
    "GROUP_NID_ENGINE": "编组中列车 NID_ENGINE",
    "NID_ENGINE_PRE": "前车 NID_ENGINE",
    "M_IP_PRE": "前车 IP 地址",
    "Q_CMDTYPE": "命令类型",
    "Q_EOATYPE": "EOA 点类型",
    "Q_DIR_HANDLE": "手柄方向",
    "Q_TRACTION_HANDLE": "牵引/制动手柄",
    "M_HEAD_PRESSURE": "列车管头部压力",
    "M_TAIL_PRESSURE": "列车管尾部压力",
    "KILOMETER_POST": "公里标",
    "RESERVED1": "预留",
    "RESERVED2": "预留",
    "N_STACNT": "车站数量",
    "NID_STA": "车站编号",
    "N_TO": "道岔数量",
    "NID_TO": "道岔编号",
    "Q_TOSTATUS": "道岔定反位状态",
    "N_SIGSTACNT": "信号状态车站数量",
    "NID_SIG": "信号机编号",
    "Q_SIGSTATUS": "信号机状态",
    "N_ITER": "迭代数量",
}


class SimError(Exception):
    pass


def check_supported(msg, entries):
    """在编码前拦掉模拟器没有分派的报文/信息包/用户包。"""
    if msg["nid"] not in SIM_MESSAGES:
        raise SimError(
            "RBC 模拟器只支持 RBC→车消息：%s；M%d 不是模拟器输入"
            % ("、".join("M%d" % nid for nid in sorted(SIM_MESSAGES)), msg["nid"]))
    for spec, user_spec, _fields in entries:
        nid = spec["nid"]
        if nid == 44:
            if user_spec is not None and user_spec["nid"] not in SIM_USERS:
                raise SimError(
                    "RBC 模拟器不支持 P44/CTCS-%d（分派表只有 %s）；"
                    "XML 不能定义新的用户包"
                    % (user_spec["nid"],
                       "、".join("CTCS-%d" % u for u in sorted(SIM_USERS))))
            continue
        if nid not in SIM_PACKETS:
            raise SimError(
                "RBC 模拟器不支持 P%d（分派表只有 %s）"
                % (nid, "、".join("P%d" % p for p in sorted(SIM_PACKETS))))


def check_encoded(result):
    """编码后再查模拟器特有的结构限制。"""
    for row in result["rows"]:
        if row["frame"].startswith("P44/CTCS-132") and row["base"] == "N_SIGSTACNT" \
                and row["value"] not in (0, None):
            raise SimError(
                "RBC 模拟器不打包 CTCS-132 的信号状态迭代组；"
                "N_SIGSTACNT 必须为 0（当前 %s）" % row["value"])
    for row in result["rows"]:
        if row["frame"].startswith("P68") and row["base"] == "Q_TRACKINIT" \
                and row["value"] == 1:
            raise SimError("RBC 模拟器要求 P68 Q_TRACKINIT=0；=1 时后续行会被误读")


def _var_name(row, nid):
    base = row["base"]
    idx = row["idx"]
    occ = row["occ"]

    if base == "Q_EOALOC" and nid == 150:
        base = "Q_EOATYPE"
    elif base == "M_MODETEXTDISPLAY" and nid == 72 and occ >= 2:
        base = "M_MODETEXTDISPLAY_END"
    elif base == "M_LEVELTEXTDISPLAY" and nid == 72 and occ >= 2:
        base = "M_LEVELTEXTDISPLAY_END"
    elif base == "Group_NID_ENGINE":
        base = "GROUP_NID_ENGINE"
    elif base == "X_TEXT":
        base = "X_TEXT(L_TEXT)"
    elif base == "N_ITER":
        if nid == 27:
            if not idx and occ >= 2:
                base = "P27_N_ITER"
        elif nid in (3, 5, 15, 21, 41, 58, 63, 68, 80):
            base = "P%d_N_ITER" % nid

    if idx:
        return "%s(%s)" % (base, ",".join(str(i) for i in idx))
    return base


def _description(row, variable):
    if variable == "X_TEXT(L_TEXT)":
        return "文本内容（GB18030 或 UTF-16BE）"
    if variable == "D_TRACKINIT":
        return "初始化线路条件距离（Q_TRACKINIT=0 时不打包）"
    if row["base"] == "Q_EOALOC":
        return "EOA 位置（区间/站内）"
    if row["base"] == "Group_NID_ENGINE":
        return FIELD_DESC["GROUP_NID_ENGINE"]
    if variable == "M_MODETEXTDISPLAY_END":
        return FIELD_DESC["M_MODETEXTDISPLAY_END"]
    if variable == "M_LEVELTEXTDISPLAY_END":
        return FIELD_DESC["M_LEVELTEXTDISPLAY_END"]
    return FIELD_DESC.get(row["base"], row["base"])


def _value_text(row, kind):
    value = row["value"]
    if kind == "placeholder":
        return PLACEHOLDER
    if value is None:
        return "0"
    return str(value)


def build_plan(msg, result, auto_length=False):
    """把 encode_message 的结果渲染成模拟器行，并按模拟器的打包口径重算长度。

    注意：协议实现（rbc_spec）把 P15 的 T_ENDTIMER、D_DP、保护区段等字段当成
    恒存在，而模拟器模板把它们当成条件字段（限定词=0 时保留行但不打包）。
    L_PACKET / L_MESSAGE 必须按模拟器的口径计算，不能直接沿用 result["size"]。
    """
    meta_by_fid = {}
    for index, meta in enumerate(result["metas"], 1):
        meta_by_fid[index] = meta

    out = []
    slots = []
    frame_bits = {}
    frame_label = {}
    lp_count = {}
    p15_state = {}
    skip_fid = None

    for row in result["rows"]:
        fid = row["fid"]
        base = row["base"]
        frame = row["frame"]
        meta = meta_by_fid.get(fid)
        sid = None
        if meta is not None:
            sid = meta[1] if meta[1] is not None else meta[0]
        packed = not row["omitted"]
        frame_label[fid] = frame

        # CTCS-132：模拟器只打包 N_SIGSTACNT 这个字节，后面的信号状态行不写。
        if meta is not None and meta[1] == 132 and base == "N_SIGSTACNT":
            variable = _var_name(row, sid)
            out.append(_make_row(row, meta[0], variable, row["bits"],
                                 _value_text(row, "int"), "int"))
            if packed:
                frame_bits[fid] = frame_bits.get(fid, 0) + row["bits"]
            skip_fid = fid
            continue
        if skip_fid == fid:
            continue

        # P15：模拟器把 Q_ENDTIMER / Q_DANGERPOINT / Q_OVERLAP 后的字段当条件字段。
        if meta is not None and meta[0] == 15:
            if base == "Q_ENDTIMER":
                p15_state["Q_ENDTIMER"] = row["value"]
            elif base in ("T_ENDTIMER", "D_ENDTIMERSTARTLOC"):
                packed = p15_state.get("Q_ENDTIMER") == 1
            elif base == "Q_DANGERPOINT":
                p15_state["Q_DANGERPOINT"] = row["value"]
            elif base in ("D_DP", "V_RELEASEDP"):
                packed = p15_state.get("Q_DANGERPOINT") == 1
            elif base == "Q_OVERLAP":
                p15_state["Q_OVERLAP"] = row["value"]
            elif base in ("D_STARTOL", "T_OL", "D_OL", "V_RELEASEOL"):
                packed = p15_state.get("Q_OVERLAP") == 1
            elif base == "Q_SECTIONTIMER" and not row["idx"]:
                p15_state["Q_SECTIONTIMER"] = row["value"]
            elif base in ("T_SECTIONTIMER", "D_SECTIONTIMERSTOPLOC") and not row["idx"]:
                packed = p15_state.get("Q_SECTIONTIMER") == 1

        if base == "L_MESSAGE":
            out.append(_make_row(row, 0, "L_MESSAGE", row["bits"],
                                 _value_text(row, "int"), "int"))
            slots.append((len(out) - 1, fid, base, None))
            frame_bits[fid] = frame_bits.get(fid, 0) + row["bits"]
            continue

        if base == "L_PACKET":
            index = lp_count.get(fid, 0)
            lp_count[fid] = index + 1
            nid = meta[0] if meta else 0
            if nid == 44:
                variable = "P44_L_PACKET" if index == 0 else "L_PACKET"
            else:
                variable = "P%d_L_PACKET" % nid
            out.append(_make_row(row, nid, variable, row["bits"],
                                 _value_text(row, "int"), "int"))
            slots.append((len(out) - 1, fid, base, index))
            frame_bits[fid] = frame_bits.get(fid, 0) + row["bits"]
            continue

        variable = _var_name(row, sid)
        bits = row["bits"]
        if variable == "X_TEXT(L_TEXT)":
            bits = 8  # 模拟器忽略该行的 bits，按 L_TEXT 计算实际长度
            kind = "text"
        elif base in ("M_IP_PRE", "NID_RADIO"):
            kind = "ip"
        else:
            kind = "int"
        out.append(_make_row(row, meta[0] if meta else None, variable, bits,
                             _value_text(row, kind), kind))
        if packed:
            frame_bits[fid] = frame_bits.get(fid, 0) + row["bits"]

        # 模拟器 P68 模板在 Q_TRACKINIT 后固定有一行 D_TRACKINIT；=0 时不打包。
        if meta is not None and meta[0] == 68 and base == "Q_TRACKINIT":
            out.append(("D_TRACKINIT", 15,
                        "初始化线路条件距离（Q_TRACKINIT=0 时不打包）", "0", "int"))

    total_bits = sum(frame_bits.values())
    size = (total_bits + 7) // 8
    pad = size * 8 - total_bits

    for index, fid, base, lp_index in slots:
        variable, bits, description, _value, kind = out[index]
        if base == "L_MESSAGE":
            value = PLACEHOLDER if auto_length and msg["nid"] in (3, 24) else str(size)
        elif auto_length:
            value = PLACEHOLDER
        else:
            meta = meta_by_fid.get(fid)
            if meta is not None and meta[0] == 44 and lp_index == 1:
                value = str(frame_bits.get(fid, 0) - 23)
            else:
                value = str(frame_bits.get(fid, 0))
        out[index] = (variable, bits, description, value, kind)

    lengths = []
    for index, meta in enumerate(result["metas"], 1):
        bits = frame_bits.get(index, 0)
        if meta[0] == 44:
            lengths.append((frame_label.get(index, "P44") + " 外层", bits))
            lengths.append((frame_label.get(index, "P44") + " 内层", bits - 23))
        else:
            lengths.append((frame_label.get(index, "P%d" % meta[0]), bits))

    checks = [
        ("L_MESSAGE", "%d 字节" % size,
         "协议固定 %d 字节" % msg["fixed_len"] if msg["fixed_len"] else "自动回填"),
        ("位遍历闭合", "%d bit = %d 字节 + %d bit 补 1"
         % (total_bits, size, pad), "OK"),
        ("报文上限", "%d / %d 字节" % (size, S.MAX_MESSAGE_BYTES), "OK"),
        ("必选与组成",
         "、".join(S.packet_label(n, u) for n, u in result["metas"]) or "无信息包", "OK"),
    ]
    return {"rows": out, "bits": total_bits, "size": size, "pad": pad,
            "packet_lengths": lengths, "checks": checks}


def _make_row(row, nid, variable, bits, value, kind):
    return (variable, bits, _description(row, variable), value, kind)


def xml_text(rows):
    from xml.sax.saxutils import quoteattr

    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<DataTable>"]
    for variable, bits, description, value, _kind in rows:
        lines.append("  <data variable=%s bits=\"%d\" description=%s value=%s />"
                     % (quoteattr(variable), bits, quoteattr(description),
                        quoteattr(value)))
    lines.append("</DataTable>")
    return "\n".join(lines) + "\n"


def verify_rows(rows, msg):
    """写文件前的结构自检：行 0、四位宽、取值位宽。"""
    if not rows:
        raise SimError("没有可写出的 XML 行")
    variable, bits, _description, value, _kind = rows[0]
    if variable != "NID_MESSAGE" or value != str(msg["nid"]):
        raise SimError("第 1 行必须是 NID_MESSAGE=%d，实际 %s=%s"
                       % (msg["nid"], variable, value))
    for index, (variable, bits, description, value, kind) in enumerate(rows, 1):
        if not isinstance(bits, int) or not 1 <= bits <= 64:
            raise SimError("第 %d 行 %s 的 bits=%r 不在 1..64" % (index, variable, bits))
        if description is None or value is None:
            raise SimError("第 %d 行 %s 缺少 description/value" % (index, variable))
        if value == "":
            raise SimError("第 %d 行 %s 的 value 不能为空" % (index, variable))
        if kind in ("text", "ip") or value == PLACEHOLDER:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise SimError("第 %d 行 %s 的取值不是十进制整数：%r"
                           % (index, variable, value))
        if number < 0 or number >= (1 << bits):
            raise SimError("第 %d 行 %s=%s 超出 %d bit 范围"
                           % (index, variable, number, bits))


def verify_xml(path, rows, msg):
    """读回刚写出的 XML，确认结构、属性和取值位宽。"""
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise SimError("XML 读回失败（%s）：%s" % (path, exc))
    if root.tag != "DataTable":
        raise SimError("根元素必须是 DataTable，实际 %r" % root.tag)
    data = list(root)
    if len(data) != len(rows):
        raise SimError("XML 行数 %d 与期望 %d 不符" % (len(data), len(rows)))
    for index, (elem, wanted) in enumerate(zip(data, rows), 1):
        if elem.tag != "data":
            raise SimError("第 %d 个子元素不是 <data>" % index)
        for attr in ("variable", "bits", "description", "value"):
            if attr not in elem.attrib:
                raise SimError("第 %d 行缺少 %s 属性" % (index, attr))
        try:
            bits = int(elem.attrib["bits"])
        except ValueError:
            raise SimError("第 %d 行 bits 不是整数：%r"
                           % (index, elem.attrib["bits"]))
        if not 1 <= bits <= 64:
            raise SimError("第 %d 行 bits=%d 不在 1..64" % (index, bits))
        if elem.attrib["variable"] != wanted[0]:
            raise SimError("第 %d 行 variable=%r，期望 %r"
                           % (index, elem.attrib["variable"], wanted[0]))
        if elem.attrib["description"] != wanted[2]:
            raise SimError("第 %d 行 description=%r，期望 %r"
                           % (index, elem.attrib["description"], wanted[2]))
        if elem.attrib["value"] != wanted[3]:
            raise SimError("第 %d 行 value=%r，期望 %r"
                           % (index, elem.attrib["value"], wanted[3]))
    first = data[0].attrib
    if first["variable"] != "NID_MESSAGE" or first["value"] != str(msg["nid"]):
        raise SimError("第 1 行必须是 NID_MESSAGE=%d" % msg["nid"])


def output_name(body, msg, used):
    """默认 dataTableM<n>.xml；可用分组里的 file/filename 覆盖。"""
    custom = body.get("file") or body.get("filename")
    if custom:
        name = os.path.basename(str(custom)).strip()
        if not name:
            raise SimError("分组的 file/filename 不能为空")
        if not name.lower().endswith(".xml"):
            name += ".xml"
        if name in used:
            raise SimError("输出文件名重复：%s（请用不同的 file/filename）" % name)
    else:
        name = "dataTableM%d.xml" % msg["nid"]
        base, ext = os.path.splitext(name)
        count = 2
        while name in used:
            name = "%s_%d%s" % (base, count, ext)
            count += 1
    used[name] = used.get(name, 0) + 1
    return name


def describe_supported():
    """--list 的文字说明。"""
    lines = ["RBC 模拟器（RBC→车）支持的报文："]
    for nid in sorted(SIM_MESSAGES):
        msg = S.MESSAGES.get(nid)
        if msg is None:
            lines.append("  M%d %s（协议定义缺失）" % (nid, SIM_MESSAGES[nid]))
            continue
        ids = []
        for alt in msg["req"]:
            ids.extend(alt)
        ids.extend(msg["opt"])
        packets = ["P%d" % n for n in sorted(set(ids)) if n in SIM_PACKETS]
        users = ["CTCS-%d" % u for u in sorted(msg["users"]) if u in SIM_USERS]
        parts = []
        if packets:
            parts.append("信息包 " + "、".join(packets))
        if users:
            parts.append("用户包 " + "、".join(users))
        if not parts:
            parts.append("纯帧头/预定义变量")
        lines.append("  M%d %s：%s" % (nid, msg["name"], "；".join(parts)))
    lines.append("")
    lines.append("说明：")
    lines.append("  * 模拟器只支持 RBC→车消息；M129/M132/M136 等车→地消息不是它的输入。")
    lines.append("  * M27/M28/M33 与 CTCS-64 不在本仓库的协议定义里，暂不支持。")
    lines.append("  * CTCS-51 在模拟器里没有发送分支；CTCS-132 的 N_SIGSTACNT 必须为 0。")
    return "\n".join(lines)
