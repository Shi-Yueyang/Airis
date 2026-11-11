#!/usr/bin/env python3
"""TACN 车地无线（OBS ↔ RBC）报文定义与位打包引擎，供 gen_rbc_msg.py / dump_rbc_msg.py 共用。

内容全部取自本技能 references/protocol.md（RA20016_C4D-IND-ATP_CASCO_2003 的 TACN 变体）。

约定（protocol.md 未明说，由固定 L_PACKET 反推验证，见 references/protocol.md 附录 C）：
  * 比特流 MSB 先行紧密排列，末尾不足整字节补 1；
  * L_PACKET 计入本包自己的头（NID_PACKET [+Q_DIR] L_PACKET ... 至包体结束）；
  * 用户包的 L_PACKET 从 NID_XUSER 起算，P44 外层 L_PACKET 含整个内层用户包；
  * 报文没有 CRC，自洽校验靠 L_MESSAGE / L_PACKET / 位遍历闭合 / 组成规则。

只依赖标准库，兼容 Python 3.8（不写类型注解，不用 match）。
"""

import re
import sys


# ---------------------------------------------------------------------------
# 终端编码
# ---------------------------------------------------------------------------
def ensure_utf8_stdio():
    """把 stdout/stderr 固定为 UTF-8。

    Windows 默认按系统代码页输出（中文环境 cp936/GBK），报告里的“↔”“−”不在 GBK 码表内，
    会直接 UnicodeEncodeError。已经是 UTF-8，或流不支持 reconfigure（IDE、测试框架替换过
    的流）时跳过。
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


# ---------------------------------------------------------------------------
# 方向
# ---------------------------------------------------------------------------
G2T = "R"  # 地 -> 车
T2G = "T"  # 车 -> 地
DIR_NAME = {G2T: "地→车", T2G: "车→地"}

KMH = "km/h"
M = "m"
S = "s"

# ---------------------------------------------------------------------------
# 定义辅助：字段项
#   f   定宽字段            cf  条件字段（限定词为真才存在）
#   arr 按计数字段重复的数组  grp N_ITER 迭代组
#   txt 变长文本            blob 字节对齐数据块
# 组体字段的重复下标由引擎按迭代追加，定义里一律写协议基名（不带 (k)）。
# ---------------------------------------------------------------------------


def f(name, bits, **opts):
    item = dict(kind="leaf", name=name, bits=bits)
    item.update(opts)
    return item


def cf(name, bits, when, **opts):
    item = dict(kind="cond", name=name, bits=bits, when=when)
    item.update(opts)
    return item


def arr(name, bits, by, **opts):
    item = dict(kind="array", name=name, bits=bits, by=by)
    item.update(opts)
    return item


def grp(count, items):
    return dict(kind="group", name=count, count=count, items=items)


def txt(name, by, **opts):
    item = dict(kind="text", name=name, bits=0, by=by)
    item.update(opts)
    return item


def blob(name, **opts):
    item = dict(kind="blob", name=name, bits=0)
    item.update(opts)
    return item


def d_(name, bits, **opts):
    """距离/长度类字段（按作用域内 Q_SCALE 换算，15 bit 未知哨兵 32767）。"""
    opts.setdefault("scale", True)
    opts.setdefault("sent", 32767)
    return f(name, bits, **opts)


def v_(name, bits, step=5, **opts):
    """速度类字段（默认 5 km/h 分辨率）。"""
    opts.setdefault("unit", (step, KMH))
    return f(name, bits, **opts)


def t_(name, bits, **opts):
    """时间类字段（秒）。"""
    opts.setdefault("unit", (1, S))
    return f(name, bits, **opts)


# ---------------------------------------------------------------------------
# 公共枚举/量纲
# ---------------------------------------------------------------------------
Q_SCALE = {0: "10 cm", 1: "1 m", 2: "10 m", 3: "备用"}
ENUM_DIR = {0: "反向", 1: "正向", 2: "双向", 3: "备用"}
ENUM_DIR2 = {0: "反向", 1: "正向", 2: "未知", 3: "备用"}
ENUM_M_ACK = {0: "无需确认", 1: "必须确认"}
ENUM_M_MODE = {0: "FS", 1: "CO", 2: "OS", 3: "SH", 5: "SL", 6: "SB", 7: "TR",
               8: "PT", 10: "IS", 12: "VC", 13: "SN", 14: "预留", 15: "BS"}
ENUM_M_LEVEL = {1: "C2 或 C0", 3: "C3", 4: "CN"}
ENUM_NID_STM = {1: "C0", 3: "C2"}
ENUM_M_ERROR = {0: "BG 一致性-链接位置/编号错误", 1: "BG 一致性-链接 BG 报文错误",
                2: "BG 一致性-未链接 BG 报文错误", 3: "无线一致性-消息错误",
                4: "无线一致性-时序错误", 5: "无线一致性-超时",
                6: "非致命错误", 7: "致命错误"}
ENUM_M_TRACKCOND = {0: "禁停隧道", 1: "禁停桥梁", 2: "禁停其他", 3: "无电区降弓(预留)",
                    4: "无线盲区(预留)", 9: "无电区关主断", 10: "防汛区段"}
ENUM_M_LEVELTR = {1: "C0/C2", 3: "C3", 4: "CN"}
ENUM_Q_LINKREACTION = {1: "常用制动", 2: "无反应"}
ENUM_Q_FRONT = {0: "尾有效/升速", 1: "头有效/降速"}
ENUM_NC_DIFF = {0: "主动摆式", 1: "被动摆式", 2: "跨风敏区", 3: "机牵客", 4: "机牵货"}
ENUM_Q_DIR_HANDLE = {0: "故障", 1: "向前", 2: "向后", 3: "中立"}
ENUM_Q_TRACTION_HANDLE = {0: "故障", 1: "牵引", 2: "制动", 3: "零位"}
ENUM_Q_EOATYPE = {0: "前车后端", 1: "进站信号机", 2: "阻挡信号机", 3: "最大长度", 4: "其他"}
ENUM_Q_EOALOC = {1: "区间", 2: "站内"}
ENUM_Q_TOSTATUS = {0: "未知", 1: "定位", 2: "反位", 3: "备用"}
ENUM_Q_SIGSTATUS = {0: "关闭", 1: "开放", 2: "引导", 3: "备用"}
ENUM_Q_EMERGENCYSTOP = {0: "接受有条件紧急停车", 1: "忽略有条件紧急停车",
                        2: "接受无条件紧急停车", 3: "备用"}
ENUM_Q_STATUS = {0: "位置无效", 1: "位置有效", 2: "位置未知", 3: "备用"}
ENUM_Q_LENGTH = {0: "无完整性信息", 1: "完整性装置确认", 2: "司机确认", 3: "丢失"}
ENUM_M_NVCONTACT = {0: "紧急停车", 1: "常用制动 SB"}
ENUM_Q_TEXTCLASS = {0: "辅助信息", 1: "重要信息"}
ENUM_Q_TEXTCONFIRM = {0: "无需确认", 1: "显示直到确认", 2: "结束未确认则常用制动"}
ENUM_MODE_UNLIMITED = {15: "不受限"}
ENUM_Q_ORIENTATION = {0: "反向通过应答器组", 1: "正向通过应答器组"}

SENT_15 = 32767
SENT_16 = 0xFFFF
SENT_24 = 0xFFFFFF
SENT_32 = 0xFFFFFFFF
SENT_LRBG = 16777215

# ---------------------------------------------------------------------------
# 第 2 层：信息包
# ---------------------------------------------------------------------------
PACKETS = {}


def packet(nid, name, direction, items, fixed_lp=None, note=""):
    PACKETS[nid] = dict(nid=nid, name=name, dir=direction, items=items,
                        fixed_lp=fixed_lp, note=note)


packet(3, "配置参数", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_VALIDNV", 15, dflt=0),
    f("N_ITER", 5, dflt=1, role="count", note="NID_C 数量；L_PACKET 固定 186 要求 N_ITER=1"),
    arr("NID_C", 10, by="N_ITER", note="高 7 位大区号 + 低 3 位分区号"),
    v_("V_NVSHUNT", 7, dflt=8),
    v_("V_NVSTFF", 7, dflt=4),
    v_("V_NVONSIGHT", 7, dflt=4),
    v_("V_NVUNFIT", 7, dflt=16, note="车载未使用"),
    v_("V_NVREL", 7, dflt=0, note="车载未使用"),
    d_("D_NVROLL", 15, dflt=5),
    f("Q_NVSRBKTRG", 1, dflt=1, note="车载未使用"),
    f("Q_NVEMRRLS", 1, dflt=0, note="车载未使用"),
    v_("V_NVALLOWOVTRP", 7, dflt=0, note="车载未使用"),
    v_("V_NVSUPOVTRP", 7, dflt=8, note="车载未使用"),
    d_("D_NVOVTRP", 15, dflt=SENT_15, note="车载未使用"),
    t_("T_NVOVTRP", 8, dflt=60, note="车载未使用"),
    d_("D_NVPOTRP", 15, dflt=0),
    f("M_NVCONTACT", 2, dflt=1, enum=ENUM_M_NVCONTACT),
    t_("T_NVCONTACT", 8, dflt=20, note="255=不监控"),
    f("M_NVDERUN", 1, dflt=0, note="车载未使用"),
    d_("D_NVSTFF", 15, dflt=SENT_15, note="车载未使用"),
    f("Q_NVDRIVER_ADHES", 1, dflt=0, note="车载未使用"),
], fixed_lp=186)

packet(5, "链接信息", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_LINK", 15, note="至下一链接 BG 的距离增量；组内多应答器以第一个为准"),
    f("Q_NEWCOUNTRY", 1, dflt=0, note="=1 时携带 NID_C"),
    cf("NID_C", 10, lambda s: s.get("Q_NEWCOUNTRY") == 1, note="Q_NEWCOUNTRY=1 时存在"),
    f("NID_BG", 14, note="应答器组编号"),
    f("Q_LINKORIENTATION", 1, dflt=1, note="0 反向通过 / 1 正向通过"),
    f("Q_LINKREACTION", 2, dflt=2, enum=ENUM_Q_LINKREACTION),
    f("Q_LOCACC", 6, dflt=5, note="链接应答器允许的安装偏差"),
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        d_("D_LINK", 15),
        f("Q_NEWCOUNTRY", 1, dflt=0),
        cf("NID_C", 10, lambda s: s.get("Q_NEWCOUNTRY") == 1),
        f("NID_BG", 14),
        f("Q_LINKORIENTATION", 1, dflt=1),
        f("Q_LINKREACTION", 2, dflt=2, enum=ENUM_Q_LINKREACTION),
        f("Q_LOCACC", 6, dflt=5),
    ]),
])

packet(15, "行车许可 MA", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    v_("V_LOA", 7, dflt=0, note="车载未使用"),
    t_("T_LOA", 10, dflt=1023, note="1023=无超时定时"),
    f("N_ITER", 5, dflt=0, role="count", note="中间区段数，MA 仅一个区段时=0"),
    grp("N_ITER", [
        d_("L_SECTION", 15),
        f("Q_SECTIONTIMER", 1, dflt=0, note="车载未使用"),
        cf("T_SECTIONTIMER", 10, lambda s: s.get("Q_SECTIONTIMER") == 1, note="车载未使用"),
        cf("D_SECTIONTIMERSTOPLOC", 15, lambda s: s.get("Q_SECTIONTIMER") == 1,
           sent=None, note="车载未使用"),
    ]),
    d_("L_ENDSECTION", 15, sent=None, note="MA 末区段长度"),
    f("Q_SECTIONTIMER", 1, dflt=0, note="车载未使用；按源文档 M3 样例恒定写出"),
    t_("T_SECTIONTIMER", 10, dflt=0, note="车载未使用"),
    d_("D_SECTIONTIMERSTOPLOC", 15, dflt=0, sent=None, note="车载未使用"),
    f("Q_ENDTIMER", 1, dflt=0, note="车载未使用"),
    t_("T_ENDTIMER", 10, dflt=0, note="车载未使用"),
    d_("D_ENDTIMERSTARTLOC", 15, dflt=0, sent=None, note="车载未使用"),
    f("Q_DANGERPOINT", 1, dflt=0, note="0 无 / 1 后随危险点信息"),
    d_("D_DP", 15, dflt=0, sent=None, note="车载未使用"),
    v_("V_RELEASEDP", 7, dflt=127, note="危险点开口速度"),
    f("Q_OVERLAP", 1, dflt=0, note="车载未使用"),
    d_("D_STARTOL", 15, dflt=0, sent=None, note="车载未使用"),
    t_("T_OL", 10, dflt=1023, note="1023 表示无穷大"),
    d_("D_OL", 15, dflt=0, sent=None, note="车载未使用"),
    v_("V_RELEASEOL", 7, dflt=0, note="保护区段开口速度"),
], note="M3 必选包，MA 本体")

packet(21, "坡度曲线", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_GRADIENT", 15, dflt=0, sent=None),
    f("Q_GDIR", 1, dflt=1, note="0 下坡/平坡，1 上坡"),
    f("G_A", 8, dflt=255, note="安全坡度；末项=255 表示描述结束"),
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        d_("D_GRADIENT", 15, sent=None),
        f("Q_GDIR", 1, dflt=1),
        f("G_A", 8, dflt=255),
    ]),
])

packet(27, "静态速度曲线 SSP", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_STATIC", 15, dflt=0, sent=None),
    v_("V_STATIC", 7),
    f("Q_FRONT", 1, dflt=0, enum=ENUM_Q_FRONT),
    f("N_ITER", 5, dflt=0, role="count", note="列车类型数量"),
    grp("N_ITER", [
        f("NC_DIFF", 4, enum=ENUM_NC_DIFF),
        v_("V_DIFF", 7, note="末项=127 表示描述结束"),
    ]),
    f("N_ITER", 5, dflt=0, role="count", note="速度变化点数量"),
    grp("N_ITER", [
        d_("D_STATIC", 15, sent=None),
        v_("V_STATIC", 7),
        f("Q_FRONT", 1, dflt=0, enum=ENUM_Q_FRONT),
        f("N_ITER", 5, dflt=0, role="count", note="该变化点处列车类型数量"),
        grp("N_ITER", [
            f("NC_DIFF", 4, enum=ENUM_NC_DIFF),
            v_("V_DIFF", 7),
        ]),
    ]),
])

packet(41, "等级切换", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_LEVELTR", 15, note="32767=立即转换"),
    f("M_LEVELTR", 3, enum=ENUM_M_LEVELTR, note="无效值=取消等级转换"),
    cf("NID_STM", 8, lambda s: s.get("M_LEVELTR") == 1, enum=ENUM_NID_STM,
       note="仅 M_LEVELTR=1 时存在"),
    d_("L_ACKLEVELTR", 15, dflt=450, sent=None),
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        f("M_LEVELTR", 3, enum=ENUM_M_LEVELTR),
        cf("NID_STM", 8, lambda s: s.get("M_LEVELTR") == 1, enum=ENUM_NID_STM),
        d_("L_ACKLEVELTR", 15, dflt=450, sent=None),
    ]),
])

packet(57, "MA 请求参数", G2T, [
    t_("T_MAR", 8, dflt=60),
    t_("T_TIMEOUTRQST", 10, dflt=1023),
    t_("T_CYCRQST", 8, dflt=60, note="两次 MA 循环请求间隔"),
], fixed_lp=49)

packet(58, "位置报告参数", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    t_("T_CYCLOC", 8, dflt=6, note="255=无效"),
    d_("D_CYCLOC", 15, dflt=SENT_15, note="32767=不按距离"),
    f("M_LOC", 3, dflt=1, note="001=每个应答器点"),
    f("N_ITER", 5, dflt=0, role="count", note="L_PACKET 固定 56 要求 N_ITER=0"),
    grp("N_ITER", [
        d_("D_LOC", 15, sent=None),
        f("Q_LGTLOC", 1, dflt=1, note="1=最大安全前端越过，0=最小安全尾端越过"),
    ]),
], fixed_lp=56)

packet(63, "目视授权范围内应答器列表", G2T, [
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        f("Q_NEWCOUNTRY", 1, dflt=0),
        cf("NID_C", 10, lambda s: s.get("Q_NEWCOUNTRY") == 1),
        f("NID_BG", 14),
    ]),
])

packet(65, "设置临时限速", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("NID_TSR", 8, note="0~126 应答器方式；127~254 RBC 自定；255=不可撤销"),
    d_("D_TSR", 15),
    d_("L_TSR", 15, sent=None),
    f("Q_FRONT", 1, dflt=1, enum=ENUM_Q_FRONT),
    v_("V_TSR", 7),
], fixed_lp=71, note="同报文内可多个，NID_TSR 须互异（255 除外）")

packet(66, "取消临时限速", G2T, [
    f("NID_TSR", 8, note="127~254"),
], fixed_lp=31, note="同报文内可多个，NID_TSR 须互异（255 除外）")

packet(68, "线路条件", G2T, [
    f("Q_TRACKINIT", 1, dflt=0, note="=1 国内不适用，ATP 不接受"),
    d_("D_TRACKCOND", 15),
    d_("L_TRACKCOND", 15, sent=None),
    f("M_TRACKCOND", 4, enum=ENUM_M_TRACKCOND),
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        d_("D_TRACKCOND", 15),
        d_("L_TRACKCOND", 15, sent=None),
        f("M_TRACKCOND", 4, enum=ENUM_M_TRACKCOND),
    ]),
], note="包内无 Q_SCALE，距离量纲按报文级 Q_SCALE 或默认 1 m 标注")

packet(72, "纯文本消息 DMS", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("Q_TEXTCLASS", 2, dflt=0, enum=ENUM_Q_TEXTCLASS),
    f("Q_TEXTDISPLAY", 1, dflt=0, note="0 条件之一满足即显示，1 组合满足"),
    d_("D_TEXTDISPLAY", 15, dflt=SENT_15),
    f("M_MODETEXTDISPLAY", 4, dflt=15, enum=ENUM_MODE_UNLIMITED),
    f("M_LEVELTEXTDISPLAY", 3, dflt=5, note="1=C0/C2 3=C3 4=CN 5=不受限"),
    cf("NID_STM", 8, lambda s: s.get("M_LEVELTEXTDISPLAY") == 1, enum=ENUM_NID_STM),
    d_("L_TEXTDISPLAY", 15, dflt=SENT_15),
    t_("T_TEXTDISPLAY", 10, dflt=1023),
    f("M_MODETEXTDISPLAY", 4, dflt=15, enum=ENUM_MODE_UNLIMITED, note="显示结束条件"),
    f("M_LEVELTEXTDISPLAY", 3, dflt=5, note="显示结束条件"),
    cf("NID_STM", 8, lambda s: s.get("M_LEVELTEXTDISPLAY") == 1, enum=ENUM_NID_STM,
       note="结束条件 M_LEVELTEXTDISPLAY=1 时存在"),
    f("Q_TEXTCONFIRM", 2, dflt=0, enum=ENUM_Q_TEXTCONFIRM),
    f("L_TEXT", 8, note="文本长度：UTF-16 为字符数，GB18030 为字节数"),
    txt("X_TEXT", by="L_TEXT", note="默认 UTF-16BE，可用 --p72-charset 切换"),
], note="文本编码源文档为 UTF-16（160K 表为 GB18030），联调需核实")

packet(80, "引导/调车区段设置", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_MAMODE", 15),
    f("M_MAMODE", 2, dflt=0, note="0=引导 CO"),
    v_("V_MAMODE", 7, dflt=4, note="0~120 有效，127=取本国值 V_NVONSIGHT"),
    d_("L_MAMODE", 15, sent=None),
    d_("L_ACKMAMODE", 15, dflt=400, sent=None),
    f("N_ITER", 5, dflt=0, role="count"),
    grp("N_ITER", [
        d_("D_MAMODE", 15),
        f("M_MAMODE", 2, dflt=0),
        v_("V_MAMODE", 7, dflt=4),
        d_("L_MAMODE", 15, sent=None),
        d_("L_ACKMAMODE", 15, dflt=400, sent=None),
    ]),
], note="与 CTCS-80 编组命令同号不同层")

PACKET_0_ITEMS = [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("NID_C", 10, composite="NID_LRBG", note="NID_LRBG 高 7 位大区号 + 低 3 位分区号"),
    f("NID_BG", 14, composite="NID_LRBG"),
    d_("D_LRBG", 15, note="LRBG 至列车估计前端距离；32767=未知"),
    f("Q_DIRLRBG", 2, enum=ENUM_DIR2),
    f("Q_DLRBG", 2, enum=ENUM_DIR2),
    d_("L_DOUBTOVER", 15, note="|置信下限−D_LRBG|"),
    d_("L_DOUBTUNDER", 15, note="|置信上限−D_LRBG|"),
    f("Q_LENGTH", 2, enum=ENUM_Q_LENGTH),
    cf("L_TRAININT", 15, lambda s: s.get("Q_LENGTH") in (1, 2), sent=None,
       note="仅 Q_LENGTH=1/2 时存在，安全车长"),
    v_("V_TRAIN", 7, step=1, note="TACN 分辨率 1 km/h"),
    f("Q_DIRTRAIN", 2, enum=ENUM_DIR2),
    f("M_MODE", 4, enum=ENUM_M_MODE),
    f("M_LEVEL", 3, enum=ENUM_M_LEVEL),
    cf("NID_STM", 8, lambda s: s.get("M_LEVEL") == 1, enum=ENUM_NID_STM,
       note="仅 M_LEVEL=1 时存在"),
]

packet(0, "位置报告（方向已知）", T2G, PACKET_0_ITEMS, note="与 P1 按列车方向是否已知二选一")

packet(1, "位置报告（方向未知）", T2G,
       PACKET_0_ITEMS[:3]
       + [f("NID_C", 10, composite="NID_PRVBG", note="前一应答器组大区号"),
          f("NID_BG", 14, composite="NID_PRVBG"),
          d_("D_LRBG", 15, note="LRBG 至列车估计前端距离；32767=未知"),
          f("Q_DIRLRBG", 2, enum=ENUM_DIR2),
          f("Q_DLRBG", 2, enum=ENUM_DIR2),
          d_("L_DOUBTOVER", 15, note="|置信下限−D_LRBG|"),
          d_("L_DOUBTUNDER", 15, note="|置信上限−D_LRBG|"),
          f("Q_LENGTH", 2, enum=ENUM_Q_LENGTH),
          cf("L_TRAININT", 15, lambda s: s.get("Q_LENGTH") in (1, 2), sent=None,
             note="仅 Q_LENGTH=1/2 时存在，安全车长"),
          v_("V_TRAIN", 7, step=1, note="TACN 分辨率 1 km/h"),
          f("Q_DIRTRAIN", 2, enum=ENUM_DIR2),
          f("M_MODE", 4, enum=ENUM_M_MODE),
          f("M_LEVEL", 3, enum=ENUM_M_LEVEL),
          cf("NID_STM", 8, lambda s: s.get("M_LEVEL") == 1, enum=ENUM_NID_STM,
             note="仅 M_LEVEL=1 时存在")],
       note="同 P0，在 NID_LRBG 之后插入 NID_PRVBG")

packet(4, "错误报告", T2G, [
    f("M_ERROR", 8, enum=ENUM_M_ERROR),
], fixed_lp=29)

packet(11, "列车数据", T2G, [
    f("NID_OPERATIONAL", 32, dflt=SENT_32, sent=SENT_32, note="车次号；全 F=未知"),
    f("NC_TRAIN", 15, note="SSP 类型位掩码：0 基本/1 主动摆式/2 被动摆式/4 跨风敏区/8 机牵客/16 机牵货"),
    d_("L_TRAIN", 12, sent=None, note="列车长度"),
    v_("V_MAXTRAIN", 7),
    f("M_LOADINGGAUGE", 8, dflt=0),
    f("M_AXLELOAD", 7, note="轴重/0.5 t（≤40 t）；>40 t 填 126"),
    f("M_AIRTIGHT", 2, dflt=0, note="0=未装"),
    f("N_ITER", 5, dflt=0, role="count", note="牵引类型数量，协议为 0"),
    grp("N_ITER", []),
    f("N_ITER", 5, dflt=0, role="count", note="STM 类型数量"),
    grp("N_ITER", [
        f("NID_STM", 8, enum=ENUM_NID_STM),
    ]),
], note="L_PACKET 取决于内容")

# P44 是容器：包体由内层 CTCS 用户包决定，dir 由所在报文方向决定。
PACKETS[44] = dict(nid=44, name="CTCS 用户包容器", dir=None, items=[], fixed_lp=None,
                   note="同报文内可多个，内嵌用户包不得重复（规则 1-9）")

# ---------------------------------------------------------------------------
# 第 3 层：P44 内用户包（qdir=None 表示内层头没有 Q_DIR）
# ---------------------------------------------------------------------------
USER_PACKETS = {}


def user_packet(nid, name, direction, items, qdir=2, fixed_lp=None, note=""):
    USER_PACKETS[nid] = dict(nid=nid, name=name, dir=direction, items=items,
                             qdir=qdir, fixed_lp=fixed_lp, note=note)


def _reserved2():
    return [f("RESERVED1", 32, dflt=SENT_32, sent=SENT_32),
            f("RESERVED2", 32, dflt=SENT_32, sent=SENT_32)]


def _pressures():
    return [f("M_HEAD_PRESSURE", 16, dflt=SENT_16, sent=SENT_16, unit=(1, "kPa"), note="0~999 kPa"),
            f("M_TAIL_PRESSURE", 16, dflt=SENT_16, sent=SENT_16, unit=(1, "kPa"), note="0~999 kPa")]


user_packet(51, "TSRS 电子地图版本", G2T, [
    f("N_PKTNUM", 6, lo=1, hi=63, note="拆分总包数 N：1~63"),
    f("Q_PKTSEQ", 6, note="本包序号 0~(N-1)"),
    blob("MAPINDEX_FILE", note="电子地图索引文件内容，8 bit 整数倍，写成 hex 字符串"),
])

user_packet(80, "编组命令", G2T, [
    f("GROUP_ID", 32, sent=SENT_32, note="0xFFFFFFFF=未编组"),
    f("N_TRAINNUM", 4, lo=1, hi=15, note="编组列车数 1~15"),
    arr("Group_NID_ENGINE", 24, by="N_TRAINNUM", note="按编组顺序的列车 NID_ENGINE"),
    f("NID_ENGINE_PRE", 24, dflt=SENT_24, sent=SENT_24, note="前车 NID_ENGINE"),
    f("M_IP_PRE", 64, kind="ip", pairs=2, note="前车双网 IP，写作 A.B.C.D.E.F.G.H"),
], note="载于 M24 时 M_ACK 必须=1")

user_packet(81, "编组状态", G2T, [
    f("GROUP_ID", 32, sent=SENT_32, note="0xFFFFFFFF=未编组"),
], note="载于 M24 时 M_ACK 必须=1")

user_packet(82, "解编预告", G2T, [
    f("GROUP_ID", 32, sent=SENT_32),
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_DECOUPLEPOS", 15, dflt=0, sent=None, note="至解编点距离"),
], note="载于 M24 时 M_ACK 必须=1")

user_packet(83, "解编命令", G2T, [
    f("GROUP_ID", 32, sent=SENT_32),
], note="与 CTCS-81 结构完全相同；载于 M24 时 M_ACK 必须=1")

user_packet(131, "IP 化车地通信会话管理", G2T, [
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("Q_CMDTYPE", 1, note="0=会话管理，1=RBC 移交"),
    cf("Q_RBC", 1, lambda s: s.get("Q_CMDTYPE") == 0, note="0 终止 / 1 建立"),
    cf("D_RBCTR", 15, lambda s: s.get("Q_CMDTYPE") == 1, note="至移交执行点距离"),
    f("NID_C", 10, note="目标 RBC 大区号"),
    f("NID_RBC", 14, note="目标 RBC 标识"),
    f("NID_RADIO", 64, kind="ip", pairs=2, note="双 IP，写作 A.B.C.D.E.F.G.H"),
    f("Q_SLEEPSESSION", 1, dflt=1, note="固定填 1"),
], qdir=2, note="协议未给内层 Q_DIR 默认值，本实现按其它用户包惯例默认 2（双向）")

user_packet(132, "道岔定反位/信号状态", G2T, [
    f("N_STACNT", 8, dflt=0, role="count", note="车站数"),
    grp("N_STACNT", [
        f("NID_STA", 16, note="车站编号"),
        f("N_TO", 5, dflt=0, role="count", note="车站内道岔数量"),
        grp("N_TO", [
            f("NID_TO", 8, note="道岔编号"),
            f("Q_TOSTATUS", 2, enum=ENUM_Q_TOSTATUS),
        ]),
    ]),
    f("N_SIGSTACNT", 8, dflt=0, role="count", note="信号状态车站数"),
    grp("N_SIGSTACNT", [
        f("NID_STA", 16, note="信号状态车站编号"),
        f("N_SIG", 5, dflt=0, role="count", note="信号机数量"),
        grp("N_SIG", [
            f("NID_SIG", 8, note="信号机编号；协议标 n 依编号规则，默认按 8 bit"),
            f("Q_SIGSTATUS", 2, enum=ENUM_Q_SIGSTATUS),
        ]),
    ]),
], note="NID_SIG 位宽协议未定，可用 --ctcs132-sig-bits 调整")

user_packet(150, "EOA 点类型信息", G2T, [
    f("Q_EOALOC", 8, dflt=1, enum=ENUM_Q_EOALOC, note="其他值无效"),
    f("Q_EOATYPE", 8, dflt=1, enum=ENUM_Q_EOATYPE, note="=0 时前车字段填真实值，否则填全 F"),
    f("NID_ENGINE", 24, dflt=SENT_24, sent=SENT_24, eoa=True,
      note="Q_EOATYPE=0 时为前车 NID_ENGINE（不可全 F）"),
    f("NID_OPERATIONAL", 32, dflt=SENT_32, sent=SENT_32, eoa=True,
      note="Q_EOATYPE=0 时为前车车次（不可全 F）"),
    f("V_TRAIN", 16, dflt=SENT_16, sent=SENT_16, unit=(1, KMH), eoa=True,
      note="Q_EOATYPE=0 时为前车速度"),
    f("Q_DIR_HANDLE", 8, dflt=255, sent=255, enum=ENUM_Q_DIR_HANDLE, note="0xFF=未知"),
    f("Q_TRACTION_HANDLE", 8, dflt=255, sent=255, enum=ENUM_Q_TRACTION_HANDLE, note="0xFF=未知"),
] + _pressures() + [
    f("KILOMETER_POST", 32, dflt=SENT_32, sent=SENT_32, note="公里标"),
] + _reserved2())

user_packet(152, "后车信息", G2T, [
    f("NID_ENGINE", 24, sent=SENT_24, note="后车 NID_ENGINE，不可 0xFFFFFF"),
    f("NID_OPERATIONAL", 32, sent=SENT_32, note="后车车次，不可全 F"),
    f("V_TRAIN", 16, sent=SENT_16, unit=(1, KMH), note="后车速度，不可 0xFFFF"),
    f("Q_DIR_HANDLE", 8, dflt=255, sent=255, enum=ENUM_Q_DIR_HANDLE),
    f("Q_TRACTION_HANDLE", 8, dflt=255, sent=255, enum=ENUM_Q_TRACTION_HANDLE),
] + _pressures() + [
    f("KILOMETER_POST", 32, dflt=SENT_32, sent=SENT_32, note="公里标"),
] + _reserved2(),
    fixed_lp=240)

user_packet(54, "车载电子地图版本", T2G, [
    f("N_PKTNUM", 6, lo=1, hi=63, note="拆分总包数 N：1~63"),
    f("Q_PKTSEQ", 6, note="本包序号 0~(N-1)"),
    f("N_MAPCNT", 6, dflt=0, role="count", note="地图块数量 1~63"),
    grp("N_MAPCNT", [
        f("M_MAPID", 16, dflt=0, note="地图块编号（车站号），无则 0"),
        f("M_GEODATAVERSION", 16, dflt=0),
        f("M_GEODATACRC", 32, dflt=0),
        f("M_FIXDATAVERSION", 16, dflt=0),
        f("M_FIXDATACRC", 32, dflt=0),
        f("N_TSRCNT", 8, dflt=0, note="块内临时限速命令总数"),
        f("M_TSRDATACRC", 32, dflt=0),
    ]),
], qdir=None)

user_packet(84, "编组列车运行状态", T2G, [
    f("GROUP_ID", 32, sent=SENT_32, note="0xFFFFFFFF=未编组"),
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_DIFF", 15, note="ATP 与 RBC 计算 EOA 终点距离之差"),
])

user_packet(136, "发车信息", T2G, [
    f("NID_C", 10),
    f("NID_BG", 14, note="出站应答器组编号"),
], qdir=None, fixed_lp=46, note="与 M136 消息同号不同层")

user_packet(151, "列车工况状态", T2G, [
    f("Q_DIR_HANDLE", 8, enum=ENUM_Q_DIR_HANDLE, note="0 故障/1 向前/2 向后/3 中立"),
    f("Q_TRACTION_HANDLE", 8, enum=ENUM_Q_TRACTION_HANDLE, note="0 故障/1 牵引/2 制动/3 零位"),
] + _pressures() + [
    f("KILOMETER_POST", 32, dflt=SENT_32, sent=SENT_32, note="公里标"),
] + _reserved2(), qdir=None)


# ---------------------------------------------------------------------------
# 帧头
# ---------------------------------------------------------------------------
HEADER_G2T = [
    f("NID_MESSAGE", 8, role="nid_message"),
    f("L_MESSAGE", 10, role="l_message"),
    f("T_TRAIN", 32, dflt=0, sent=None, note="RBC 发送时间戳（对车载时间的安全估计）"),
    f("M_ACK", 1, dflt=1, enum=ENUM_M_ACK),
    f("NID_C", 10, composite="NID_LRBG", dflt=1023,
      note="NID_LRBG 高 7 位大区号 + 低 3 位分区号"),
    f("NID_BG", 14, composite="NID_LRBG", dflt=16383),
]

HEADER_T2G = [
    f("NID_MESSAGE", 8, role="nid_message"),
    f("L_MESSAGE", 10, role="l_message"),
    f("T_TRAIN", 32, dflt=0, sent=None, note="车载时间戳"),
    f("NID_ENGINE", 24, dflt=SENT_24, sent=SENT_24, note="列车标识号"),
]

# ---------------------------------------------------------------------------
# 第 1 层：消息
# ---------------------------------------------------------------------------
MESSAGES = {}


def message(nid, name, direction, pre=(), req=(), opt=(), users=(), fixed_len=None, note=""):
    MESSAGES[nid] = dict(nid=nid, name=name, dir=direction, pre=list(pre),
                         req=[list(x) for x in req], opt=list(opt),
                         users=dict(users), fixed_len=fixed_len, note=note)


message(2, "目视授权", G2T, pre=[
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    d_("D_SR", 15, note="至目视授权终点距离"),
], opt=[63], note="M_ACK 固定=1")

message(3, "行车许可 MA", G2T, req=[[15]], opt=[3, 5, 21, 27, 65, 66, 68, 80],
        users={132: "cond", 150: "opt"}, note="NID_LRBG 取最新位置报告值；P15 必选")

message(6, "确认退出冒进防护模式", G2T, fixed_len=10, note="纯帧头")

message(8, "列车数据确认", G2T, pre=[
    f("T_TRAIN", 32, sent=None, note="被确认 M129 的时间戳回显"),
], fixed_len=14)

message(15, "有条件紧急停车", G2T, pre=[
    f("NID_EM", 4, lo=1, hi=15, note="1~15，对每个 ATP 从 1 独立计数"),
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("Q_DIR", 2, dflt=1, enum=ENUM_DIR, note="固定 1（正向有效）"),
    d_("D_EMERGENCYSTOP", 15, note="LRBG 至紧急停车点距离"),
], fixed_len=13)

message(16, "无条件紧急停车", G2T, pre=[
    f("NID_EM", 4, dflt=0, hi=0, note="固定 0（协议 §3.6）"),
], fixed_len=10, note="帧头 75 bit + NID_EM 4 bit = 79 bit，正好 10 字节")

message(18, "取消紧急停车", G2T, pre=[
    f("NID_EM", 4, dflt=0, hi=15, note="0~15，指定被取消的紧急消息"),
], fixed_len=10, note="帧头 75 bit + NID_EM 4 bit = 79 bit，正好 10 字节")

message(24, "通常消息", G2T, opt=[3, 57, 58, 65, 66, 72, 41],
        users={51: "opt", 131: "opt", 80: "ack", 81: "ack", 82: "ack", 83: "ack", 152: "opt"},
        note="全部信息包可选；含 CTCS-80/81/82/83 时 M_ACK 必须=1")

message(32, "系统版本", G2T, pre=[
    f("M_VERSION", 7, dflt=16, hi=127, note="固定 16"),
], fixed_len=11)

message(34, "确认前方轨道空闲 TAF 请求", G2T, pre=[
    f("Q_SCALE", 2, dflt=1, role="scale", note="协议无默认值；缺省按 1 m（计入回退）"),
    f("Q_DIR", 2, dflt=2, enum=ENUM_DIR),
    d_("D_TAFDISPLAY", 15, note="LRBG 至 TAF 窗口起点距离"),
    d_("L_TAFDISPLAY", 15, dflt=200, sent=None, note="窗口长度，默认 200 m"),
], fixed_len=14)

message(39, "会话结束确认", G2T, fixed_len=10, note="纯帧头")
message(41, "接受列车", G2T, fixed_len=10, note="纯帧头")
message(45, "分配坐标系", G2T, pre=[
    f("Q_ORIENTATION", 1, enum=ENUM_Q_ORIENTATION),
])

message(129, "经过确认的列车数据", T2G, req=[[0, 1], [11]])
message(132, "请求 MA", T2G, pre=[
    f("Q_TRACKDEL", 1, dflt=0, note="1=请求重发以 LRBG 起点的全部线路描述"),
], req=[[0, 1]], users={136: "opt"})
message(136, "列车位置报告", T2G, req=[[0, 1]], opt=[4],
        users={151: "opt", 54: "cond", 84: "cond"})
message(146, "确认", T2G, pre=[
    f("T_TRAIN", 32, sent=None, note="被确认消息的时间戳回显"),
], fixed_len=14)
message(147, "紧急停车确认", T2G, pre=[
    f("NID_EM", 4, dflt=0, hi=15, note="被确认紧急消息标识 0~15"),
    f("Q_EMERGENCYSTOP", 2, enum=ENUM_Q_EMERGENCYSTOP),
], req=[[0, 1]])
message(149, "前方轨道空闲确认", T2G, req=[[0, 1]])
message(150, "任务结束", T2G, req=[[0, 1]])
message(154, "版本不兼容", T2G, fixed_len=10, note="纯帧头")
message(155, "会话开始", T2G, fixed_len=10, note="纯帧头")
message(156, "会话结束", T2G, fixed_len=10, note="纯帧头")
message(157, "SoM 位置报告", T2G, pre=[
    f("Q_STATUS", 2, dflt=1, enum=ENUM_Q_STATUS),
], req=[[0, 1]], opt=[4])
message(159, "会话已建立", T2G, fixed_len=10, note="纯帧头")

MULTI_OK = {65, 66, 44}  # 规则 1-9：同类型包可多个的例外
MAX_MESSAGE_BYTES = 500

MSG_BY_NAME = dict((("M%d" % nid), nid) for nid in MESSAGES)
PACKET_BY_NAME = dict((("P%d" % nid), nid) for nid in PACKETS)
USER_BY_NAME = dict((("CTCS-%d" % nid), nid) for nid in USER_PACKETS)
ACK_USERS = {80, 81, 82, 83}
# ---------------------------------------------------------------------------
# 异常与工具
# ---------------------------------------------------------------------------
class SpecError(Exception):
    pass


def split_name(name):
    """'M_LEVELTEXTDISPLAY#2' -> ('M_LEVELTEXTDISPLAY', 2)。"""
    match = re.match(r"^(.*?)#(\d+)$", name)
    if match:
        return match.group(1), int(match.group(2))
    return name, 1


def item_bits(item, opts=None):
    if item["name"] == "NID_SIG" and opts and opts.get("ctcs132_sig_bits"):
        return opts["ctcs132_sig_bits"]
    return item["bits"]


def char_bits_for(item, opts):
    charset = (opts or {}).get("p72_charset") or item.get("charset") or "utf-16-be"
    return 8 if charset in ("gb18030", "gbk", "utf-8", "latin-1", "ascii") else 16


L_PACKET_BITS = 13


def packet_frame(dir_):
    """信息包头：NID_PACKET [Q_DIR（仅地→车）] L_PACKET。"""
    items = [f("NID_PACKET", 8, role="nid_packet")]
    if dir_ == G2T:
        items.append(f("Q_DIR", 2, dflt=2, enum=ENUM_DIR))
    items.append(f("L_PACKET", L_PACKET_BITS, role="l_packet"))
    return items


def user_frame(user_spec):
    """用户包头：NID_XUSER [Q_DIR] L_PACKET；Q_DIR 是否出现由各用户包定义决定。"""
    items = [f("NID_XUSER", 9, role="nid_xuser")]
    qdir = user_spec.get("qdir")
    if qdir:
        head = f("Q_DIR", 2, enum=ENUM_DIR)
        if isinstance(qdir, int):
            head["dflt"] = qdir
        items.append(head)
    items.append(f("L_PACKET", L_PACKET_BITS, role="l_packet"))
    return items


def entry_items(spec, user_spec=None, dir_=None):
    """一个信息包条目的完整声明序列（包头 + 可选用户包头 + 包体）。"""
    pdir = spec["dir"] or dir_
    items = list(packet_frame(pdir))
    if user_spec is not None:
        items += user_frame(user_spec) + list(user_spec["items"])
    else:
        items += list(spec["items"])
    return items


def frame_dir_for(spec, msg):
    return spec["dir"] or msg["dir"]


def occ_map(items):
    """按声明顺序给同名字段编号：{id(item): n}。迭代组体只按声明走一遍。"""
    counts = {}
    result = {}

    def walk(lst):
        for item in lst:
            if item["kind"] == "group":
                walk(item["items"])
                continue
            base, _ = split_name(item["name"])
            counts[base] = counts.get(base, 0) + 1
            result[id(item)] = counts[base]

    walk(items)
    return result


def occ_totals(items):
    """{基名: 该帧声明中出现次数}（迭代组体的出现次数累加，不可覆盖）。"""
    totals = {}
    for item in items:
        if item["kind"] == "group":
            for base, count in occ_totals(item["items"]).items():
                totals[base] = totals.get(base, 0) + count
            continue
        base, _ = split_name(item["name"])
        totals[base] = totals.get(base, 0) + 1
    return totals


def expand_composites(mapping, items):
    """把 NID_LRBG / NID_PRVBG（24 bit 整数）展开成对应的 NID_C / NID_BG。"""
    out = dict(mapping or {})
    occ = occ_map(items)
    groups = {}
    for item in items:
        tag = item.get("composite")
        if tag:
            groups.setdefault(tag, []).append((item["name"], occ.get(id(item), 1)))
    for tag in sorted(groups):
        if tag not in out:
            continue
        number = parse_int(tag, out.pop(tag))
        for name, n in groups[tag]:
            part = (number >> 14) if name == "NID_C" else (number & 0x3FFF)
            key = name if n == 1 else "%s#%d" % (name, n)
            if key in out:
                raise SpecError("%s 与 %s 同时给出：请只用其中一种写法" % (tag, key))
            out[key] = part
    return out


def parse_int(name, value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError:
            raise SpecError("%s: 无法把 %r 解析成整数" % (name, value))
    raise SpecError("%s: 取值 %r 不是整数或 0x 十六进制字符串" % (name, value))


# ---------------------------------------------------------------------------
# 位流
# ---------------------------------------------------------------------------
class BitWriter(object):
    def __init__(self):
        self.buf = bytearray()
        self.acc = 0
        self.n = 0

    def bitpos(self):
        return len(self.buf) * 8 + self.n

    def write(self, value, bits):
        if bits <= 0:
            return
        if not 0 <= value < (1 << bits):
            raise SpecError("值 %d 放不进 %d bit" % (value, bits))
        self.acc = (self.acc << bits) | value
        self.n += bits
        while self.n >= 8:
            self.n -= 8
            self.buf.append((self.acc >> self.n) & 0xFF)
            self.acc &= (1 << self.n) - 1

    def reserve(self, bits):
        pos = self.bitpos()
        self.write(0, bits)
        return pos

    def patch(self, pos, bits, value):
        if not 0 <= value < (1 << bits):
            raise SpecError("长度 %d 放不进 %d bit（上限 %d）" % (value, bits, (1 << bits) - 1))
        for i in range(bits):
            bit = (value >> (bits - 1 - i)) & 1
            bp = pos + i
            shift = 7 - bp % 8
            self.buf[bp // 8] = (self.buf[bp // 8] & ~(1 << shift)) | (bit << shift)

    def finish(self):
        """末尾不足整字节补 1，返回 (bytes, 补位数)。"""
        pad = 8 - self.n if self.n else 0
        if pad:
            self.write((1 << pad) - 1, pad)
        return bytes(self.buf), pad


class BitReader(object):
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.total = len(data) * 8
        self.limit = self.total

    def read(self, bits):
        if bits <= 0:
            return 0
        if self.pos + bits > self.limit:
            raise SpecError("位流在第 %d 位耗尽（本帧上限 %d 位，还需 %d bit）"
                            % (self.pos, self.limit, bits))
        value = 0
        for i in range(bits):
            bp = self.pos + i
            value = (value << 1) | ((self.data[bp // 8] >> (7 - bp % 8)) & 1)
        self.pos += bits
        return value


# ---------------------------------------------------------------------------
# 作用域：限定词与计数器取值栈
# ---------------------------------------------------------------------------
class Scope(object):
    def __init__(self):
        self.frames = [{}]

    def push(self):
        self.frames.append({})

    def pop(self):
        self.frames.pop()

    def set(self, name, value):
        self.frames[-1].setdefault(name, []).append(value)

    def get(self, name, default=None):
        for frame in reversed(self.frames):
            values = frame.get(name)
            if values:
                return values[-1]
        return default


# ---------------------------------------------------------------------------
# 显式取值容器
#   键写法与 protocol.md 一致：
#     NAME              基名；该帧只出现一次时直接命中，出现多次时给全部出现处同一值
#     NAME(k)           迭代组里的那个同名项（括号下标个数 = 迭代层数，(k,m)/(i)(j) 均可）
#     NAME#n            按声明顺序的第 n 个出现处（用于 M8 的 T_TRAIN、P44 的内层 Q_DIR 等）
#     NID_LRBG / NID_PRVBG  24 bit 复合键，自动拆成对应 NID_C / NID_BG
# ---------------------------------------------------------------------------
KEY_RE = re.compile(r"^(.*?)(?:\(([^()]*)\))?(?:#(\d+))?$")


def key_parts(key):
    """'NC_DIFF(k,m)' -> ('NC_DIFF', 2, None)；'T_TRAIN#2' -> ('T_TRAIN', 0, 2)。"""
    match = KEY_RE.match(str(key).strip())
    base = match.group(1)
    slots = 0
    if match.group(2) is not None:
        slots = match.group(2).count(",") + 1
    occ = int(match.group(3)) if match.group(3) else None
    return base, slots, occ


def declaration_table(items):
    """{基名: [(出现序号, 迭代层数, 展示名), ...]}，按声明顺序。"""
    table = {}

    def walk(lst, depth):
        for item in lst:
            if item["kind"] == "group":
                walk(item["items"], depth + 1)
                continue
            base, _ = split_name(item["name"])
            entries = table.setdefault(base, [])
            entries.append((len(entries) + 1, depth))

    walk(items, 0)
    return table


class Values(object):
    def __init__(self, where, mapping, items=None):
        self.where = where
        self.raw = dict(mapping or {})
        self.used = set()
        self.multi = {}
        self.bound = {}
        table = declaration_table(items or [])
        explicit = []
        bare = []
        for key, value in self.raw.items():
            base, slots, occ = key_parts(key)
            if base not in table:
                continue
            if occ is not None or slots:
                explicit.append((key, base, slots, occ, value))
            else:
                bare.append((key, base, value))
        for key, base, slots, occ, value in explicit:
            candidates = table[base]
            if occ is not None:
                chosen = [(n, depth) for n, depth in candidates if n == occ]
                if not chosen:
                    raise SpecError("%s.%s: %s 没有第 %d 个出现处（本帧共 %d 个）"
                                    % (where, base, key, occ, len(candidates)))
            else:
                chosen = [(n, depth) for n, depth in candidates if depth == slots]
                if not chosen:
                    raise SpecError("%s.%s: %s 不是迭代字段（协议里 %s 的迭代层数为 %s）"
                                    % (where, base, key, base,
                                       "/".join(str(d) for _n, d in candidates)))
            self._bind(base, chosen, key, value)
        for key, base, value in bare:
            candidates = [(n, depth) for n, depth in table[base] if (base, n) not in self.bound]
            if not candidates:
                continue
            self._bind(base, candidates, key, value)
            if len(candidates) > 1:
                self.multi[base] = len(candidates)

    def _bind(self, base, chosen, key, value):
        for n, _depth in chosen:
            if (base, n) in self.bound:
                raise SpecError("%s.%s: %s 与 %s 都指向第 %d 个 %s；只想给其中一处赋值时，"
                                "请把裸名改成带序号的写法（例如 %s#1）"
                                % (self.where, base, key, self.bound[(base, n)][1], n, base, base))
            self.bound[(base, n)] = (value, key)

    def provided(self, name, occ):
        """该出现处是否被显式给值，以及原始值（不按下标取项）。"""
        base, _ = split_name(name)
        entry = self.bound.get((base, occ))
        return entry[0] if entry else None

    def mark_used(self, name, occ):
        base, _ = split_name(name)
        entry = self.bound.get((base, occ))
        if entry:
            self.used.add(entry[1])

    def take(self, name, occ, idx_path, total=1):
        base, _ = split_name(name)
        entry = self.bound.get((base, occ))
        if entry is None:
            return None, None
        value, source = entry
        self.used.add(source)
        return self._index(value, idx_path, source), source

    def _index(self, value, idx_path, source):
        for depth, i in enumerate(idx_path):
            if isinstance(value, list):
                if i >= len(value):
                    raise SpecError("%s.%s: 列表只有 %d 项，取第 [%d] 轮时越界；这一轮需要该字段，"
                                    "请补齐列表（用不到的位置写 null）"
                                    % (self.where, source, len(value), i))
                value = value[i]
            else:
                break
        if isinstance(value, bool):
            raise SpecError("%s.%s: 布尔不是合法取值" % (self.where, source))
        if value is None:
            raise SpecError("%s.%s: 第 [%s] 轮取值是 null，但这一轮确实需要该字段"
                            % (self.where, source, ",".join(str(i) for i in idx_path)))
        return value

    def leftovers(self):
        return sorted(set(self.raw) - set(self.used))


# ---------------------------------------------------------------------------
# 取值合法性与可读说明
# ---------------------------------------------------------------------------
def check_value(item, width, value, where=""):
    name = "%s%s" % (where + "." if where else "", item["name"])
    if not isinstance(value, int):
        raise SpecError("%s: 取值 %r 不是整数" % (name, value))
    if value < 0:
        raise SpecError("%s: 取值 %d 为负" % (name, value))
    if value >= (1 << width):
        raise SpecError("%s: 取值 %d 超过 %d bit 上限 %d" % (name, value, width, (1 << width) - 1))
    lo, hi = item.get("lo"), item.get("hi")
    if lo is not None and value < lo:
        raise SpecError("%s: 取值 %d 低于协议下限 %d" % (name, value, lo))
    if hi is not None and value > hi:
        raise SpecError("%s: 取值 %d 高于协议上限 %d" % (name, value, hi))


def parse_ip(value, name, bits, pairs):
    if isinstance(value, int):
        number = value
    else:
        if isinstance(value, (list, tuple)):
            octets = list(value)
        else:
            octets = [p for p in re.split(r"[.:]", str(value)) if p != ""]
        if len(octets) != 4 * pairs:
            raise SpecError("%s: IP 需要 %d 段（%d 个 IPv4），得到 %r" % (name, 4 * pairs, pairs, value))
        number = 0
        for part in octets:
            octet = int(part)
            if not 0 <= octet <= 255:
                raise SpecError("%s: IP 段 %r 不在 0~255" % (name, part))
            number = (number << 8) | octet
    if bits and number >= (1 << bits):
        raise SpecError("%s: IP 值放不进 %d bit" % (name, bits))
    return number


def fmt_ip(value, bits, pairs):
    return ".".join(str((value >> (bits - 8 * (i + 1))) & 0xFF) for i in range(4 * pairs))


def encode_text(item, value, opts):
    charset = (opts or {}).get("p72_charset") or item.get("charset") or "utf-16-be"
    if isinstance(value, (bytes, bytearray)):
        return bytes(value), charset
    if not isinstance(value, str):
        raise SpecError("%s: 文本取值必须是字符串，得到 %r" % (item["name"], value))
    try:
        return value.encode(charset), charset
    except (UnicodeEncodeError, LookupError) as exc:
        raise SpecError("%s: 文本无法按 %s 编码（%s）" % (item["name"], charset, exc))


def decode_text(item, data, opts):
    charset = (opts or {}).get("p72_charset") or item.get("charset") or "utf-16-be"
    try:
        return data.decode(charset)
    except (UnicodeDecodeError, LookupError):
        return None


def describe(item, value, scope, opts=None):
    parts = []
    enum = item.get("enum")
    if enum and value in enum:
        parts.append(enum[value])
    if item.get("role") == "scale":
        parts.append(Q_SCALE.get(value, "备用"))
    if item.get("scale"):
        step = {0: 0.1, 1: 1.0, 2: 10.0}.get(scope.get("Q_SCALE", 1), 1.0)
        parts.append("%g %s" % (value * step, M))
    elif item.get("unit"):
        factor, unit = item["unit"]
        if unit == KMH and value == (1 << item["bits"]) - 1:
            parts.append("%g %s（该字段上限，常表示无限制）" % (value * factor, unit))
        else:
            parts.append("%g %s" % (value * factor, unit))
    sent = item.get("sent")
    if sent is not None and value == sent:
        parts.append("未知(哨兵)")
    note = item.get("note")
    if note:
        parts.append(note)
    return "；".join(parts)


def display_name(item, idx=(), occ=1, total=1):
    name = item["name"]
    if idx:
        return "%s(%s)" % (name, ",".join(str(i) for i in idx))
    if total > 1 and occ > 1:
        return "%s#%d" % (name, occ)
    return name


# ---------------------------------------------------------------------------
# 遍历上下文
# ---------------------------------------------------------------------------
class Ctx(object):
    def __init__(self, opts=None):
        self.opts = dict(opts or {})
        self.rows = []
        self.warnings = []
        self.errors = []
        self.fallbacks = 0

    def warn(self, text):
        self.warnings.append(text)

    def row(self, fid, frame, item, occ, total, idx, pos, bits, value, source, desc=""):
        self.rows.append({
            "fid": fid,
            "frame": frame,
            "offset": pos,
            "bits": bits,
            "base": split_name(item["name"])[0],
            "occ": occ,
            "total": total,
            "name": display_name(item, idx, occ, total),
            "depth": len(idx),
            "value": value,
            "source": source,
            "desc": desc,
            "omitted": source == "按限定词省略",
            "idx": tuple(idx),
        })


def body_bits(items):
    """迭代组体至少消耗多少位（用于识别错位的超大计数）。"""
    total = 0
    for item in items:
        if item["kind"] == "group":
            continue
        if item["kind"] in ("text", "blob") or item.get("kind") == "ip":
            total += item_bits(item) if item.get("kind") == "ip" else 8
        elif item["kind"] == "cond":
            total += 0
        elif item["kind"] == "array":
            total += item_bits(item)
        else:
            total += item_bits(item)
    return total


# ---------------------------------------------------------------------------
# 编码
# ---------------------------------------------------------------------------
def _resolve(item, occ, total, values, idx, frame, ctx):
    name = display_name(item, idx, occ, total)
    where = "%s.%s" % (frame, name)
    value, source = values.take(item["name"], occ, idx, total)
    if value is None:
        dflt = item.get("dflt")
        if dflt is None:
            raise SpecError("%s: 未给取值，协议也没有默认值（%s）"
                            % (where, item.get("note") or "见 references/protocol.md"))
        ctx.fallbacks += 1
        return dflt, "协议默认"
    if isinstance(value, str) and item["kind"] in ("leaf", "cond", "array"):
        value = parse_int(where, value)
    return value, source


def enc_items(items, values, occ, totals, scope, writer, ctx, fid, frame, idx, forced, state):
    for item in items:
        kind = item["kind"]
        base, _ = split_name(item["name"])
        occ_no = occ.get(id(item), 1)
        total = totals.get(base, 1)
        role = item.get("role")

        if kind == "group":
            count = scope.get(item["count"])
            if count is None:
                raise SpecError("%s.%s: 找不到迭代计数 %s" % (frame, item["name"], item["count"]))
            for i in range(count):
                scope.push()
                enc_items(item["items"], values, occ, totals, scope, writer, ctx, fid, frame,
                          idx + (i,), forced, state)
                scope.pop()
            continue

        if role in ("nid_message", "nid_packet", "nid_xuser"):
            given, _ = values.take(item["name"], occ_no, idx, total)
            if given is not None:
                raise SpecError("%s.%s: 由条目类型决定，不能在 values 里赋值" % (frame, base))
            pos = writer.bitpos()
            value = forced[base]
            if role == "nid_xuser":
                state["starts"].append(pos)
            writer.write(value, item["bits"])
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], value, "固定")
            scope.set(base, value)
            continue

        if role == "l_message":
            pos = writer.reserve(item["bits"])
            state["lm"] = pos
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], None, "自动计算",
                    "整条消息字节数，生成后回填")
            continue

        if role == "l_packet":
            start = state["starts"][len(state["lp"])]
            pos = writer.reserve(item["bits"])
            state["lp"].append((pos, start))
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], None, "自动计算",
                    "本包位数（含本包头），生成后回填")
            continue

        name = display_name(item, idx, occ_no, total)
        where = "%s.%s" % (frame, name)
        if kind == "cond" and not item["when"](scope):
            given = values.provided(item["name"], occ_no)
            if given is not None and not isinstance(given, list):
                raise SpecError("%s: 当前限定词下该字段不进报文（%s），但 values 给了值 %r；"
                                "迭代组里的字段请给列表，缺失的那一轮可以少写"
                                % (where, item.get("note") or "见协议", given))
            if given is not None:
                values.mark_used(item["name"], occ_no)
            ctx.row(fid, frame, item, occ_no, total, idx, writer.bitpos(), item["bits"], None,
                    "按限定词省略", item.get("note") or "")
            continue

        bits = item_bits(item, ctx.opts)

        if kind == "array":
            count = scope.get(item["by"])
            if count is None:
                raise SpecError("%s: 找不到重复计数 %s" % (where, item["by"]))
            for i in range(count):
                value, source = _resolve(item, occ_no, total, values, idx + (i,), frame, ctx)
                check_value(item, bits, value, frame)
                pos = writer.bitpos()
                writer.write(value, bits)
                ctx.row(fid, frame, item, occ_no, total, idx + (i,), pos, bits, value, source,
                        describe(item, value, scope, ctx.opts))
            continue

        if kind == "text":
            length = scope.get(item["by"], 0) or 0
            step = char_bits_for(item, ctx.opts)
            value, source = values.take(item["name"], occ_no, idx, total)
            if value is None:
                raise SpecError("%s: 必须给文本内容" % where)
            data, charset = encode_text(item, value, ctx.opts)
            if len(data) * 8 != length * step:
                raise SpecError("%s: 文本按 %s 编码得 %d 字节，与 %s=%d 不符"
                                "（UTF-16 时 %s 是字符数，GB18030 时是字节数）"
                                % (where, charset, len(data), item["by"], length,
                                   item["by"]))
            pos = writer.bitpos()
            writer.write(int.from_bytes(data, "big"), len(data) * 8)
            text = value if isinstance(value, str) else decode_text(item, data, ctx.opts)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, len(data) * 8, text, source,
                    "%s，%s=%d（UTF-16 为字符数，GB18030 为字节数）"
                    % (charset, item["by"], length))
            continue

        if kind == "blob":
            value, source = values.take(item["name"], occ_no, idx, total)
            if value is None:
                raise SpecError("%s: 必须给数据块内容（hex 字符串）" % where)
            if isinstance(value, (bytes, bytearray)):
                data = bytes(value)
            else:
                text = re.sub(r"[^0-9A-Fa-f]", "", str(value))
                if not text or len(text) % 2:
                    raise SpecError("%s: 数据块需要偶数位 hex 字符串，得到 %r" % (where, value))
                data = bytes.fromhex(text)
            pos = writer.bitpos()
            for byte in data:
                writer.write(byte, 8)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, len(data) * 8,
                    data.hex().upper(), source, "%d 字节" % len(data))
            continue

        value, source = _resolve(item, occ_no, total, values, idx, frame, ctx)
        if item.get("kind") == "ip":
            pairs = item.get("pairs", 2)
            number = parse_ip(value, where, bits, pairs)
            pos = writer.bitpos()
            writer.write(number, bits)
            scope.set(base, number)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, bits, fmt_ip(number, bits, pairs),
                    source, "双 IP（%d bit）" % bits)
            continue
        check_value(item, bits, value, frame)
        pos = writer.bitpos()
        writer.write(value, bits)
        scope.set(base, value)
        ctx.row(fid, frame, item, occ_no, total, idx, pos, bits, value, source,
                describe(item, value, scope, ctx.opts))


def enc_entry(msg, spec, user_spec, raw_values, scope, writer, ctx, fid):
    dir_ = frame_dir_for(spec, msg)
    items = entry_items(spec, user_spec, dir_)
    occ = occ_map(items)
    totals = occ_totals(items)
    frame = packet_label(spec["nid"], user_spec["nid"] if user_spec else None)
    values = Values(frame, expand_composites(raw_values, items), items)
    forced = {"NID_PACKET": spec["nid"]}
    if user_spec is not None:
        forced["NID_XUSER"] = user_spec["nid"]
    state = {"starts": [writer.bitpos()], "lp": []}
    scope.push()
    enc_items(items, values, occ, totals, scope, writer, ctx, fid, frame, (), forced, state)
    end = writer.bitpos()
    scope.pop()
    for index, (pos, start) in enumerate(state["lp"]):
        computed = end - start
        if computed > (1 << L_PACKET_BITS) - 1:
            raise SpecError("%s: 包长 %d bit 超过 L_PACKET %d bit 上限"
                            % (frame, computed, L_PACKET_BITS))
        writer.patch(pos, L_PACKET_BITS, computed)
        for row in ctx.rows:
            if row["fid"] == fid and row["base"] == "L_PACKET" and row["offset"] == pos:
                row["value"] = computed
        owner = user_spec if index == len(state["lp"]) - 1 and user_spec is not None else spec
        fixed = owner.get("fixed_lp") if owner else None
        if fixed is not None and computed != fixed:
            raise SpecError(
                "%s: 计算得 L_PACKET=%d bit，协议固定 %d bit —— 迭代计数或条件字段与协议不符"
                "（协议定长包：P3=186 P57=49 P58=56 P65=71 P66=31 P4=29 CTCS-136=46 CTCS-152=240）"
                % (frame, computed, fixed))
    stale = values.leftovers()
    if stale:
        raise SpecError("%s: values 里的键没有被任何字段消费（名字写错、出现序号写错，"
                        "或该报文不收这个字段）：%s" % (frame, ", ".join(stale)))
    for base, total in sorted(values.multi.items()):
        ctx.warn("%s.%s 在该帧声明了 %d 次，裸名会给全部出现处同一值；需要不同值请用 %s#1 / %s#2"
                 % (frame, base, total, base, base))
    return (spec["nid"], user_spec["nid"] if user_spec else None), values


def compact_label(meta):
    nid, user = meta
    return "P44/CTCS-%d" % user if user is not None else "P%d" % nid


def encode_message(msg, header_values, entries, opts=None):
    """entries: [(packet_spec, user_spec|None, fields_dict)]，顺序即空口排列顺序。"""
    ctx = Ctx(opts)
    writer = BitWriter()
    scope = Scope()
    scope.push()
    header_items = (HEADER_G2T if msg["dir"] == G2T else HEADER_T2G) + msg["pre"]
    occ = occ_map(header_items)
    totals = occ_totals(header_items)
    hvalues = Values("报文头", expand_composites(header_values, header_items), header_items)
    hstate = {"starts": [0], "lp": []}
    enc_items(header_items, hvalues, occ, totals, scope, writer, ctx, 0, "报文头", (),
              {"NID_MESSAGE": msg["nid"]}, hstate)
    stale = hvalues.leftovers()
    if stale:
        raise SpecError("报文头: values 里的键没有被任何字段消费：%s" % ", ".join(stale))
    for base, total in sorted(hvalues.multi.items()):
        ctx.warn("报文头.%s 声明了 %d 次，裸名会给全部出现处同一值；需要不同值请用 %s#1 / %s#2"
                 % (base, total, base, base))

    metas = []
    per_entry = []
    frames_values = [(0, "报文头", frame_values(ctx, 0))]
    fid = 0
    for spec, user_spec, raw in entries:
        fid += 1
        meta, _values = enc_entry(msg, spec, user_spec, raw, scope, writer, ctx, fid)
        metas.append(meta)
        values = frame_values(ctx, fid)
        per_entry.append(values)
        frames_values.append((fid, compact_label(meta), values))

    if msg["dir"] == G2T and msg.get("ack_fixed") and scope.get("M_ACK") != 1:
        raise SpecError("M%d 的 M_ACK 固定=1（协议 §3.1），当前为 %r"
                        % (msg["nid"], scope.get("M_ACK")))
    if msg["dir"] == G2T and any(u for _n, u in metas if u in ACK_USERS) \
            and scope.get("M_ACK") != 1:
        raise SpecError("含 CTCS-80/81/82/83 编组类用户包时 M_ACK 必须=1（协议 §3.8）")

    total_bits = writer.bitpos()
    total_bytes = (total_bits + 7) // 8
    if "lm" not in hstate:
        raise SpecError("帧头缺少 L_MESSAGE 字段")
    writer.patch(hstate["lm"], 10, total_bytes)
    for row in ctx.rows:
        if row["fid"] == 0 and row["base"] == "L_MESSAGE":
            row["value"] = total_bytes
    data, pad = writer.finish()

    if total_bytes > MAX_MESSAGE_BYTES:
        raise SpecError("报文 %d 字节超过协议上限 %d 字节" % (total_bytes, MAX_MESSAGE_BYTES))
    if msg["fixed_len"] is not None and total_bytes != msg["fixed_len"]:
        raise SpecError("M%d 协议固定 L_MESSAGE=%d 字节，实际 %d 字节 —— 预定义变量或信息包与协议不符"
                        % (msg["nid"], msg["fixed_len"], total_bytes))

    errors, warnings = composition_problems(msg, metas, per_entry, frame_values(ctx, 0))
    sem_errors, sem_warnings = semantic_problems(msg, frames_values, hard=True)
    for text in errors + sem_errors:
        raise SpecError(text)
    for text in warnings + sem_warnings:
        ctx.warn(text)

    checks = [("L_MESSAGE", "%d 字节" % total_bytes,
               "协议固定 %d 字节" % msg["fixed_len"] if msg["fixed_len"] else "自动回填"),
              ("位遍历闭合", "%d bit = %d 字节 + %d bit 补 1"
               % (total_bits, total_bytes, pad), "OK"),
              ("报文上限", "%d / %d 字节" % (total_bytes, MAX_MESSAGE_BYTES), "OK"),
              ("必选与组成", "%s" % ("、".join(packet_label(n, u) for n, u in metas) or "无信息包"),
               "OK")]
    return dict(data=data, rows=ctx.rows, warnings=ctx.warnings, checks=checks,
                fallbacks=ctx.fallbacks, msg=msg, size=total_bytes, pad=pad, metas=metas)


def frame_values(ctx, fid):
    """某一帧内解析到的整数值：{基名: [值, ...]}，按声明/迭代顺序。"""
    out = {}
    for row in ctx.rows:
        if row["fid"] != fid or row["value"] is None or not isinstance(row["value"], int):
            continue
        out.setdefault(row["base"], []).append(row["value"])
    return out


# ---------------------------------------------------------------------------
# 组成与语义规则
# ---------------------------------------------------------------------------
def packet_label(nid, user=None):
    if nid == 44:
        if user in USER_PACKETS:
            return "P44/CTCS-%d %s" % (user, USER_PACKETS[user]["name"])
        return "P44/CTCS-%s" % user
    spec = PACKETS.get(nid)
    return "P%d %s" % (nid, spec["name"] if spec else "未收录信息包")


def composition_problems(msg, entries, values_by_entry, header_values=None):
    """entries: [(packet_id, user_id|None)]；返回 (errors, warnings)。"""
    errors, warnings = [], []
    ids = [e[0] for e in entries]
    counts = {}
    for key in entries:
        counts[key] = counts.get(key, 0) + 1
    for (nid, user), count in sorted(counts.items()):
        if count > 1 and nid not in MULTI_OK:
            errors.append("%s 在一条报文中出现 %d 次（规则 1-9 不允许）"
                          % (packet_label(nid, user), count))
        if nid == 44 and user is not None and count > 1:
            errors.append("同一用户包 %s 重复 %d 次（规则 1-9：内嵌用户包不得重复）"
                          % (packet_label(44, user), count))
    for alt in msg["req"]:
        if not any(nid in alt for nid in ids):
            errors.append("缺少必选信息包：%s" % " 或 ".join(packet_label(nid) for nid in alt))
    allowed = set(msg["opt"])
    for alt in msg["req"]:
        allowed.update(alt)
    for nid, user in entries:
        spec = PACKETS.get(nid)
        if spec and spec["dir"] and spec["dir"] != msg["dir"]:
            errors.append("%s 是%s信息包，不能放进%s的 M%d"
                          % (packet_label(nid), DIR_NAME[spec["dir"]], DIR_NAME[msg["dir"]],
                             msg["nid"]))
            continue
        if nid == 44:
            if user is None:
                errors.append("P44 条目必须声明 user（CTCS 用户包号）")
            elif user not in msg["users"]:
                errors.append("M%d 不承载 P44/CTCS-%d（协议 §%d 的组成表未列入）"
                              % (msg["nid"], user, 8 if msg["dir"] == G2T else 9))
        elif nid not in allowed:
            errors.append("%s 不在 M%d（%s）的信息包组成里"
                          % (packet_label(nid, user), msg["nid"], msg["name"]))
        if user is not None and USER_PACKETS.get(user) \
                and USER_PACKETS[user]["dir"] != msg["dir"]:
            errors.append("CTCS-%d 是%s用户包，不能放进%s的 M%d"
                          % (user, DIR_NAME[USER_PACKETS[user]["dir"]],
                             DIR_NAME[msg["dir"]], msg["nid"]))
    tsrs = []
    for index, (nid, _user) in enumerate(entries):
        if nid in (65, 66):
            got = values_by_entry[index].get("NID_TSR")
            if got:
                tsrs.append((nid, got[0]))
    for i in range(len(tsrs)):
        for j in range(i + 1, len(tsrs)):
            if tsrs[i][1] != tsrs[j][1] or tsrs[i][1] == 255:
                continue
            if tsrs[i][0] == tsrs[j][0]:
                errors.append("两处 P%d 的 NID_TSR=%d 重复；规则 1-9 要求同报文内临时限速编号互异"
                              "（255 除外）" % (tsrs[i][0], tsrs[i][1]))
            # P65 与 P66 用同一编号是正常的"设置/取消"配对，不报
    return errors, warnings


def semantic_problems(msg, frames_values, hard=False):
    """frames_values: [(fid, frame_label, {基名: [值]})]；返回 (errors, warnings)。"""
    errors, warnings = [], []
    for _fid, frame, values in frames_values:
        first = lambda key: ((values.get(key) or [None])[0])

        def flag(text):
            (errors if hard else warnings).append(text)

        if frame == "P68" and first("Q_TRACKINIT") == 1:
            flag("P68 Q_TRACKINIT=1：国内不适用，ATP 不接受该包")
        if frame == "P3" and first("N_ITER") not in (None, 1):
            flag("P3 N_ITER=%s，但协议固定 L_PACKET=186 只容得下 1 个 NID_C" % first("N_ITER"))
        if frame == "P65" and first("NID_TSR") == 255:
            warnings.append("P65 NID_TSR=255 表示不可撤销，取消时需另发 P66")
        if frame == "P66":
            value = first("NID_TSR")
            if value is not None and not 127 <= value <= 254:
                warnings.append("P66 NID_TSR=%d 不在 127~254（取消限速的编号应由 RBC 自定）" % value)
        if frame == "报文头" and msg["dir"] == G2T and msg["nid"] == 3:
            # 协议 §3.2：M3 的 NID_LRBG 必须取最新位置报告值，未知哨兵通常意味着漏填
            value = first("NID_C")
            bg = first("NID_BG")
            if value is not None and bg is not None and ((value << 14) | bg) == SENT_LRBG:
                warnings.append("M3 帧头 NID_LRBG=16777215（未知）：协议要求取最新位置报告的 LRBG")
        if frame.startswith("P44/CTCS-150"):
            eoa = values.get("Q_EOATYPE")
            if eoa:
                if eoa[0] != 0:
                    for key, sentinel in (("NID_ENGINE", SENT_24), ("NID_OPERATIONAL", SENT_32),
                                          ("V_TRAIN", SENT_16)):
                        got = values.get(key)
                        if got and got[0] != sentinel:
                            warnings.append("CTCS-150：Q_EOATYPE=%d≠0 时 %s 应填全 F 哨兵，实为 %s"
                                            % (eoa[0], key, got[0]))
                else:
                    for key, sentinel, label in (("NID_ENGINE", SENT_24, "前车标识"),
                                                 ("NID_OPERATIONAL", SENT_32, "前车车次"),
                                                 ("V_TRAIN", SENT_16, "前车速度")):
                        got = values.get(key)
                        if got and got[0] == sentinel:
                            warnings.append("CTCS-150：Q_EOATYPE=0 时 %s 不可为全 F 哨兵" % label)
        if frame.startswith("P44/CTCS-152"):
            for key, sentinel, label in (("NID_ENGINE", SENT_24, "后车标识"),
                                         ("NID_OPERATIONAL", SENT_32, "后车车次"),
                                         ("V_TRAIN", SENT_16, "后车速度")):
                got = values.get(key)
                if got and got[0] == sentinel:
                    warnings.append("CTCS-152：后车信息 %s 不可为全 F 哨兵（%s）" % (label, key))
        if frame == "P15":
            if first("Q_SECTIONTIMER") and (first("T_SECTIONTIMER") in (None, 0)
                                            or first("D_SECTIONTIMERSTOPLOC") in (None, 0)):
                warnings.append("P15 Q_SECTIONTIMER=1 但末区段定时取值仍为 0，请核对")
    return errors, warnings


# ---------------------------------------------------------------------------
# 解码
# ---------------------------------------------------------------------------
def dec_items(items, reader, occ, totals, scope, ctx, fid, frame, idx, expect, state):
    for item in items:
        kind = item["kind"]
        base, _ = split_name(item["name"])
        occ_no = occ.get(id(item), 1)
        total = totals.get(base, 1)
        role = item.get("role")

        if kind == "group":
            count = scope.get(item["count"])
            if count is None:
                raise SpecError("%s.%s: 找不到迭代计数 %s" % (frame, item["name"], item["count"]))
            need = body_bits(item["items"])
            if need and reader.pos + need * count > reader.limit:
                raise SpecError("%s.%s: 迭代计数 %d 需要 %d bit，本帧只剩 %d bit"
                                " —— 判定位遍历错位，停止猜测"
                                % (frame, item["name"], count, need * count,
                                   reader.limit - reader.pos))
            for i in range(count):
                scope.push()
                dec_items(item["items"], reader, occ, totals, scope, ctx, fid, frame,
                          idx + (i,), expect, state)
                scope.pop()
            continue

        if role in ("nid_message", "nid_packet", "nid_xuser"):
            pos = reader.pos
            value = reader.read(item["bits"])
            want = expect.get(base)
            if want is not None and value != want:
                raise SpecError("%s.%s: 读到 %d，期望 %d —— 位遍历已错位"
                                % (frame, item["name"], value, want))
            if role == "nid_xuser":
                state["starts"].append(pos)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], value, "比特流")
            scope.set(base, value)
            continue

        if role == "l_message":
            pos = reader.pos
            value = reader.read(item["bits"])
            state["lm"] = value
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], value, "声明值",
                    "整条消息字节数")
            continue

        if role == "l_packet":
            frame_index = len(state["lp"])
            start = state["starts"][frame_index]
            pos = reader.pos
            value = reader.read(item["bits"])
            end = start + value
            if end > reader.total:
                raise SpecError("%s.%s: L_PACKET=%d bit 超出数据末尾（第 %d 位）"
                                % (frame, item["name"], value, reader.total))
            if end < reader.pos:
                raise SpecError("%s.%s: L_PACKET=%d bit 小于已读位数（本帧从第 %d 位起，已读到第 %d 位）"
                                % (frame, item["name"], value, start, reader.pos))
            state["lp"].append((value, start, end))
            state["limits"].append(reader.limit)
            reader.limit = min(reader.limit, end)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, item["bits"], value, "声明值",
                    "本包位数（含本包头）")
            continue

        name = display_name(item, idx, occ_no, total)
        if kind == "cond" and not item["when"](scope):
            ctx.row(fid, frame, item, occ_no, total, idx, reader.pos, item["bits"], None,
                    "按限定词省略", item.get("note") or "")
            continue

        bits = item_bits(item, ctx.opts)

        if kind == "array":
            count = scope.get(item["by"])
            if count is None:
                raise SpecError("%s.%s: 找不到重复计数 %s" % (frame, name, item["by"]))
            if reader.pos + bits * count > reader.limit:
                raise SpecError("%s.%s: 重复 %d 次需要 %d bit，本帧只剩 %d bit —— 位遍历错位"
                                % (frame, name, count, bits * count, reader.limit - reader.pos))
            for i in range(count):
                pos = reader.pos
                value = reader.read(bits)
                ctx.row(fid, frame, item, occ_no, total, idx + (i,), pos, bits, value, "比特流",
                        describe(item, value, scope, ctx.opts))
            scope.set(base, count)
            continue

        if kind == "text":
            length = scope.get(item["by"], 0) or 0
            step = char_bits_for(item, ctx.opts)
            pos = reader.pos
            if length:
                if step == 16:
                    data = b"".join(reader.read(16).to_bytes(2, "big") for _ in range(length))
                else:
                    data = bytes(reader.read(8) for _ in range(length))
            else:
                data = b""
            ctx.row(fid, frame, item, occ_no, total, idx, pos, len(data) * 8,
                    decode_text(item, data, ctx.opts), "比特流",
                    "%s，%s=%d（UTF-16 为字符数，GB18030 为字节数）"
                    % (ctx.opts.get("p72_charset") or "utf-16-be", item["by"], length))
            continue

        if kind == "blob":
            end = state["lp"][-1][2] if state["lp"] else reader.limit
            pos = reader.pos
            if (end - pos) % 8:
                raise SpecError("%s.%s: 数据块区内剩 %d bit，不是 8 的整数倍（协议要求 8 bit 整数倍）"
                                % (frame, name, end - pos))
            data = bytes(reader.read(8) for _ in range((end - pos) // 8))
            ctx.row(fid, frame, item, occ_no, total, idx, pos, len(data) * 8, data.hex().upper(),
                    "比特流", "%d 字节" % len(data))
            continue

        if item.get("kind") == "ip":
            pos = reader.pos
            number = reader.read(bits)
            pairs = item.get("pairs", 2)
            scope.set(base, number)
            ctx.row(fid, frame, item, occ_no, total, idx, pos, bits, fmt_ip(number, bits, pairs),
                    "比特流", "双 IP（%d bit）" % bits)
            continue

        pos = reader.pos
        value = reader.read(bits)
        scope.set(base, value)
        ctx.row(fid, frame, item, occ_no, total, idx, pos, bits, value, "比特流",
                describe(item, value, scope, ctx.opts))


def dec_entry(msg, reader, scope, ctx, fid):
    entry_start = reader.pos
    peek = reader.read(8)
    reader.pos = entry_start
    if peek not in PACKETS:
        raise SpecError("未收录的信息包 NID_PACKET=%d（第 %d 位）——停止遍历，后续字节不猜"
                        % (peek, entry_start))
    spec = PACKETS[peek]
    dir_ = frame_dir_for(spec, msg)
    if spec["dir"] and spec["dir"] != msg["dir"]:
        ctx.warn("%s 是%s信息包，出现在%s的 M%d 里"
                 % (packet_label(peek), DIR_NAME[spec["dir"]], DIR_NAME[msg["dir"]], msg["nid"]))
    user_spec = None
    if peek == 44:
        probe = entry_start + 8 + (2 if dir_ == G2T else 0) + L_PACKET_BITS
        if probe + 9 > reader.total:
            raise SpecError("P44 后面数据不足，读不到 NID_XUSER")
        saved = reader.pos, reader.limit
        reader.pos, reader.limit = probe, reader.total
        number = reader.read(9)
        reader.pos, reader.limit = saved
        if number not in USER_PACKETS:
            raise SpecError("未收录的用户包 NID_XUSER=%d（第 %d 位）——停止遍历" % (number, probe))
        user_spec = USER_PACKETS[number]
        if user_spec["dir"] != msg["dir"]:
            ctx.warn("CTCS-%d 是%s用户包，出现在%s的 M%d 里"
                     % (number, DIR_NAME[user_spec["dir"]], DIR_NAME[msg["dir"]], msg["nid"]))
    items = entry_items(spec, user_spec, dir_)
    occ = occ_map(items)
    totals = occ_totals(items)
    expect = {"NID_PACKET": peek}
    if user_spec is not None:
        expect["NID_XUSER"] = user_spec["nid"]
    frame = packet_label(peek, user_spec["nid"] if user_spec else None)
    state = {"starts": [entry_start], "lp": [], "limits": []}
    scope.push()
    dec_items(items, reader, occ, totals, scope, ctx, fid, frame, (), expect, state)
    end = reader.pos
    for index in range(len(state["lp"]) - 1, -1, -1):
        declared, start, frame_end = state["lp"][index]
        computed = end - start
        owner = user_spec if (index and user_spec is not None) else spec
        if index == len(state["lp"]) - 1 and owner is not None and owner.get("fixed_lp") \
                and computed != owner["fixed_lp"]:
            ctx.warn("%s: 计算得 L_PACKET=%d bit，协议固定 %d bit"
                     % (frame, computed, owner["fixed_lp"]))
        reader.limit = state["limits"][index]
        if end < frame_end:
            ctx.warn("%s: 声明 L_PACKET=%d bit，字段只消耗 %d bit，剩余 %d bit 未解析"
                     "（模板/数据版本不一致）" % (frame, declared, computed, frame_end - end))
        reader.pos = frame_end
        end = frame_end
    scope.pop()
    return (peek, user_spec["nid"] if user_spec else None), frame, frame_values(ctx, fid)


def decode_message(data, bit_offset=0, opts=None):
    ctx = Ctx(opts)
    total_bits = len(data) * 8
    result = dict(offset=bit_offset, rows=[], msg=None, name="", ok=False, checks=[],
                  warnings=[], errors=[], size=0, dir="", packets=0, pad_bits=0,
                  next_pos=None, metas=[])
    if bit_offset + 18 > total_bits:
        ctx.errors.append("数据太短：从第 %d 位起只剩 %d bit，连帧头（18 bit）都不够"
                          % (bit_offset, max(0, total_bits - bit_offset)))
        result.update(warnings=ctx.warnings, errors=ctx.errors)
        return result
    reader = BitReader(data)
    reader.pos = bit_offset
    scope = Scope()
    scope.push()
    state = {"starts": [bit_offset], "lp": [], "limits": []}
    try:
        first = reader.read(8)
        reader.pos = bit_offset
        if first not in MESSAGES:
            ctx.errors.append("未知 NID_MESSAGE=%d（第 %d 位）：references/protocol.md 未收录该消息，"
                              "无法按位遍历" % (first, bit_offset))
            result.update(warnings=ctx.warnings, errors=ctx.errors)
            return result
        msg = MESSAGES[first]
        result["msg"] = msg
        result["name"] = "M%d %s" % (msg["nid"], msg["name"])
        result["dir"] = DIR_NAME[msg["dir"]]
        header_items = (HEADER_G2T if msg["dir"] == G2T else HEADER_T2G) + msg["pre"]
        occ = occ_map(header_items)
        totals = occ_totals(header_items)
        dec_items(header_items, reader, occ, totals, scope, ctx, 0, "报文头", (),
                  {"NID_MESSAGE": msg["nid"]}, state)
        declared = state.get("lm")
        if declared is None:
            raise SpecError("没能读到 L_MESSAGE")
        avail = total_bits - bit_offset
        trailing = 0
        if declared * 8 > avail:
            ctx.warn("L_MESSAGE 声明 %d 字节，但数据只剩 %d 字节：按可用长度遍历（报文可能被截断）"
                     % (declared, avail // 8))
            reader.limit = total_bits
        else:
            reader.limit = bit_offset + declared * 8
            trailing = (avail - declared * 8) // 8
            if trailing and not ctx.opts.get("split"):
                ctx.warn("声明 L_MESSAGE=%d 字节，后面还有 %d 字节未属于本报文"
                         "（若是一条拼接流，请加 --split 逐条解析）" % (declared, trailing))
        min_head = 8 + (2 if msg["dir"] == G2T else 0) + L_PACKET_BITS
        metas = []
        frames_values = [(0, "报文头", frame_values(ctx, 0))]
        per_entry = []
        fid = 0
        while reader.pos + min_head <= reader.limit:
            before = reader.pos
            fid += 1
            meta, _label, values = dec_entry(msg, reader, scope, ctx, fid)
            metas.append(meta)
            per_entry.append(values)
            frames_values.append((fid, compact_label(meta), values))
            if reader.pos == before:
                raise SpecError("信息包没有消耗任何位，位遍历卡住")
        pad_bits = reader.limit - reader.pos
        if pad_bits > 7:
            ctx.warn("报文尾部还有 %d bit（%d 字节）没有被解析成信息包" % (pad_bits, pad_bits // 8))
        elif pad_bits:
            pad = reader.read(pad_bits)
            if pad != (1 << pad_bits) - 1:
                ctx.warn("末尾 %d bit 填充位不是全 1（读到 0x%X）：字段位宽或顺序可能与协议不符"
                         % (pad_bits, pad))
        end = reader.pos
        computed_bytes = (end - bit_offset + 7) // 8
        errors, warnings = composition_problems(msg, metas, per_entry, frame_values(ctx, 0))
        sem_errors, sem_warnings = semantic_problems(msg, frames_values)
        for text in errors + sem_errors:
            ctx.warn("组成校验：%s" % text)
        for text in warnings + sem_warnings:
            ctx.warn(text)
        checks = [
            ("L_MESSAGE", "声明 %d 字节，字段到第 %d 位（%d 字节）"
             % (declared, end - bit_offset, computed_bytes),
             "OK" if computed_bytes == declared else "MISMATCH"),
            ("报文上限", "%d / %d 字节" % (declared, MAX_MESSAGE_BYTES),
             "OK" if declared <= MAX_MESSAGE_BYTES else "OVERLONG"),
            ("位遍历闭合", "消费 %d bit，末尾 %d bit" % (end - bit_offset - pad_bits, pad_bits),
             "OK" if pad_bits <= 7 else "%dB-UNPARSED" % (pad_bits // 8)),
            ("填充位", "全 1" if pad_bits <= 7 else "未知", "OK" if pad_bits <= 7 else "CHECK"),
        ]
        result.update(rows=ctx.rows, warnings=ctx.warnings, errors=ctx.errors, checks=checks,
                      ok=not ctx.errors and not ctx.warnings, size=declared, pad_bits=pad_bits,
                      packets=len(metas), metas=metas,
                      next_pos=bit_offset + declared * 8 if declared * 8 <= total_bits else None)
        return result
    except SpecError as exc:
        ctx.errors.append("遍历中断：%s" % exc)
        result.update(rows=ctx.rows, warnings=ctx.warnings, errors=ctx.errors,
                      checks=[("遍历状态", "第 %d 位中断" % reader.pos, "INCOMPLETE")], ok=False)
        return result


# ---------------------------------------------------------------------------
# 解码结果 -> values 结构（供定点修改回环）
# ---------------------------------------------------------------------------
def capture_message(result):
    msg = result.get("msg")
    if msg is None:
        return {}
    buckets = {}
    order = []
    for row in result["rows"]:
        if row["omitted"] or row["source"] == "自动计算":
            continue
        if row["base"] in ("NID_MESSAGE", "NID_PACKET", "NID_XUSER", "L_MESSAGE", "L_PACKET"):
            continue
        if row["fid"] not in buckets:
            buckets[row["fid"]] = {}
            order.append(row["fid"])
        _store(buckets[row["fid"]], row)
    header = buckets.get(0, {})
    packets = []
    codes = []
    metas = result.get("metas") or []
    for fid in order:
        if fid == 0:
            continue
        if fid - 1 >= len(metas):
            continue
        nid, user = metas[fid - 1]
        entry = {"packet": "P%d" % nid}
        if user is not None:
            entry["packet"] = "P44"
            entry["user"] = "CTCS-%d" % user
            codes.append("P44/CTCS-%d" % user)
        else:
            codes.append("P%d" % nid)
        entry["fields"] = buckets[fid]
        packets.append(entry)
    return {
        "intent": {"message": "M%d" % msg["nid"], "target": "both",
                   "packets": codes, "confirmed": True},
        "provenance": {"header": "decoded", "*": "decoded"},
        "header": header,
        "packets": packets,
    }



def _store(target, row):
    if row["total"] > 1:
        key = "%s#%d" % (row["base"], row["occ"])
    else:
        key = row["base"]
    idx = row["idx"]
    value = row["value"]
    if not idx:
        target[key] = value
        return
    holder = target.get(key)
    if not isinstance(holder, list):
        holder = [] if holder is None else [holder]
    _place(holder, list(idx), value)
    target[key] = holder


def _place(container, idx, value):
    first = idx[0]
    while len(container) <= first:
        container.append([] if len(idx) > 1 else None)
    if len(idx) == 1:
        container[first] = value
        return
    if not isinstance(container[first], list):
        container[first] = []
    _place(container[first], idx[1:], value)


# ---------------------------------------------------------------------------
# 条目描述与解析（两个 CLI 共用）
# ---------------------------------------------------------------------------
MESSAGES[2]["ack_fixed"] = True   # 协议 §3.1：M2 的 M_ACK 固定=1


def packet_label(nid, user=None):
    if nid == 44:
        if user in USER_PACKETS:
            return "P44/CTCS-%d %s" % (user, USER_PACKETS[user]["name"])
        return "P44/CTCS-%s" % user
    spec = PACKETS.get(nid)
    return "P%d %s" % (nid, spec["name"] if spec else "未收录信息包")


def compact_label(meta):
    nid, user = meta
    return "P44/CTCS-%d" % user if user is not None else "P%d" % nid


def resolve_message(label):
    if isinstance(label, int):
        if label in MESSAGES:
            return MESSAGES[label]
        raise SpecError("未知消息 NID_MESSAGE=%d" % label)
    key = str(label).strip().upper().replace(" ", "")
    if key in MSG_BY_NAME:
        return MESSAGES[MSG_BY_NAME[key]]
    if key.isdigit() and int(key) in MESSAGES:
        return MESSAGES[int(key)]
    raise SpecError("未知消息 %r：请用 M2/M3/M24/M136 之类的标识（清单见 references/protocol.md）"
                    % (label,))


def resolve_packet(label):
    if isinstance(label, int):
        if label in PACKETS:
            return PACKETS[label]
        raise SpecError("未知信息包 NID_PACKET=%d" % label)
    key = str(label).strip().upper().replace(" ", "")
    if key in PACKET_BY_NAME:
        return PACKETS[PACKET_BY_NAME[key]]
    if key.isdigit() and int(key) in PACKETS:
        return PACKETS[int(key)]
    raise SpecError("未知信息包 %r（写作 P15 或 15）" % (label,))


def resolve_user(label):
    if isinstance(label, int):
        if label in USER_PACKETS:
            return USER_PACKETS[label]
        raise SpecError("未知用户包 NID_XUSER=%d" % label)
    key = str(label).strip().upper().replace(" ", "").replace("CTCS", "CTCS-").replace("--", "-")
    if key in USER_BY_NAME:
        return USER_PACKETS[USER_BY_NAME[key]]
    if key.isdigit() and int(key) in USER_PACKETS:
        return USER_PACKETS[int(key)]
    raise SpecError("未知用户包 %r（写作 CTCS-150 或 150）" % (label,))


def entry_from_spec(entry):
    """把 values 里的条目描述规整成 (packet_spec, user_spec|None, fields_dict)。"""
    if not isinstance(entry, dict):
        raise SpecError("信息包条目必须是对象：{\"packet\": \"P15\", \"fields\": {...}}")
    label = entry.get("packet")
    if label is None:
        label = entry.get("P", entry.get("id"))
    spec = resolve_packet(label)
    user = entry.get("user")
    if user is None:
        user = entry.get("CTCS", entry.get("xuser"))
    if spec["nid"] == 44:
        if user is None:
            raise SpecError("P44 条目必须声明 user（CTCS 用户包号）")
        user_spec = resolve_user(user)
    else:
        if user is not None:
            raise SpecError("P%d 不是 P44 容器，不能带 user=%r" % (spec["nid"], user))
        user_spec = None
    fields = entry.get("fields")
    if fields is None:
        fields = dict((k, v) for k, v in entry.items()
                      if k not in ("packet", "P", "id", "user", "CTCS", "xuser", "fields"))
    if not isinstance(fields, dict):
        raise SpecError("P%d 的 fields 必须是对象" % spec["nid"])
    return spec, user_spec, fields


def values_for_message(doc, label):
    """values JSON 里一条报文的分组 -> (msg, header_values, entries)。"""
    if not isinstance(doc, dict):
        raise SpecError("%s 的取值必须是对象" % label)
    msg = resolve_message(doc["message"]) if "message" in doc else resolve_message(label)
    body = dict((k, v) for k, v in doc.items() if k != "message")
    header = body.get("header", {})
    if not isinstance(header, dict):
        raise SpecError("%s 的 header 必须是对象" % msg["name"])
    raw_entries = body.get("packets", [])
    if isinstance(raw_entries, dict):
        raw_entries = [{"packet": k, "fields": v} for k, v in raw_entries.items()]
    if not isinstance(raw_entries, list):
        raise SpecError("%s 的 packets 必须是数组（顺序即空口排列顺序）" % msg["name"])
    entries = [entry_from_spec(e) for e in raw_entries]
    return msg, header, entries
