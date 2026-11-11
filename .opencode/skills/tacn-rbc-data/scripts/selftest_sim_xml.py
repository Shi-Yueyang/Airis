#!/usr/bin/env python3
"""RBC 模拟器 XML 生成器的可执行回归（长度基线 + 结构限制）。

基线来自 references/rbc-simulator-input-xml.md 第 7 节的样例：
  * 523-c80.xml：294 bit / 37 字节，P44 外层 219、内层 196；
  * M24-c81/c82/c83、M24-P58、M15；
  * 523-M3.xml：653 bit / 82 字节（P15 66、P21 78、P27 86、P5 69、C150 279）。

这些数字同时验证 rbc_spec 的编码结果和 sim_spec 的模拟器口径转换（P15 条件字段、
P68 的 D_TRACKINIT、CTCS-132 的信号状态组、P72 的 X_TEXT/L_TEXT）。

用法：python <skill-dir>/scripts/selftest_sim_xml.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_rbc_sim_xml as C  # noqa: E402
import rbc_spec as S  # noqa: E402
import sim_spec as X  # noqa: E402

FAILS = []


def check(name, got, want):
    if got != want:
        FAILS.append("%s：得到 %r，期望 %r" % (name, got, want))
        print("FAIL  %s：得到 %r，期望 %r" % (name, got, want))
    else:
        print("ok    %s = %r" % (name, got))


def ok(name):
    print("ok    %s" % name)


def build(body, charset="gb18030", auto=False):
    msg, header, entries = S.values_for_message(body, "selftest")
    X.check_supported(msg, entries)
    result = S.encode_message(msg, header, entries, {"p72_charset": charset})
    X.check_encoded(result)
    plan = X.build_plan(msg, result, auto)
    if charset == "utf-16-be":
        plan["rows"] = C._rewrite_text_length(plan["rows"])
    X.verify_rows(plan["rows"], msg)
    return msg, result, plan


def plen(plan, prefix):
    return [bits for label, bits in plan["packet_lengths"] if label.startswith(prefix)]


def row_value(plan, variable):
    for name, _bits, _desc, value, _kind in plan["rows"]:
        if name == variable:
            return value
    return None


HEADER = {"T_TRAIN": 3277070, "M_ACK": 1, "NID_C": 1018, "NID_BG": 523}

C80 = {
    "message": "M24", "header": HEADER,
    "packets": [{"packet": "P44", "user": "CTCS-80", "fields": {
        "GROUP_ID": 2, "N_TRAINNUM": 2, "Group_NID_ENGINE": [90, 91],
        "NID_ENGINE_PRE": 90, "M_IP_PRE": "172.16.27.100.172.16.28.100"}}],
}
C81 = {"message": "M24", "header": HEADER,
       "packets": [{"packet": "P44", "user": "CTCS-81", "fields": {"GROUP_ID": 2}}]}
C82 = {"message": "M24", "header": HEADER,
       "packets": [{"packet": "P44", "user": "CTCS-82",
                    "fields": {"GROUP_ID": 2, "Q_SCALE": 1, "D_DECOUPLEPOS": 500}}]}
C83 = {"message": "M24", "header": HEADER,
       "packets": [{"packet": "P44", "user": "CTCS-83", "fields": {"GROUP_ID": 2}}]}
P58 = {"message": "M24", "header": HEADER,
       "packets": [{"packet": "P58", "fields": {
           "Q_SCALE": 1, "T_CYCLOC": 4, "D_CYCLOC": 32767, "M_LOC": 1, "N_ITER": 0}}]}
M15 = {"message": "M15", "header": dict(HEADER, NID_EM=1, D_EMERGENCYSTOP=100),
       "packets": []}

M3_523 = {
    "message": "M3", "header": HEADER,
    "packets": [
        {"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 3000}},
        {"packet": "P21", "fields": {
            "Q_SCALE": 1, "D_GRADIENT#1": 0, "Q_GDIR#1": 1, "G_A#1": 1,
            "N_ITER": 1, "D_GRADIENT(k)": 3000, "Q_GDIR(k)": 1, "G_A(k)": 255}},
        {"packet": "P27", "fields": {
            "Q_SCALE": 1, "D_STATIC#1": 0, "V_STATIC#1": 100, "Q_FRONT#1": 0,
            "N_ITER#1": 0, "N_ITER#2": 1, "N_ITER(k)": 0,
            "D_STATIC(k)": 0, "V_STATIC(k)": 80, "Q_FRONT(k)": 0}},
        {"packet": "P5", "fields": {
            "Q_SCALE": 1, "D_LINK": 100, "Q_NEWCOUNTRY": 0, "NID_BG": 524,
            "Q_LINKORIENTATION": 1, "Q_LINKREACTION": 2, "Q_LOCACC": 5, "N_ITER": 0}},
        {"packet": "P44", "user": "CTCS-150", "fields": {"Q_EOALOC": 1}},
    ],
}

P72 = {
    "message": "M24", "header": HEADER,
    "packets": [{"packet": "P72", "fields": {
        "Q_SCALE": 1, "Q_TEXTCLASS": 0, "Q_TEXTDISPLAY": 0, "D_TEXTDISPLAY": 32767,
        "M_MODETEXTDISPLAY": 15, "M_LEVELTEXTDISPLAY": 5, "L_TEXTDISPLAY": 32767,
        "T_TEXTDISPLAY": 1023, "M_MODETEXTDISPLAY#2": 15, "M_LEVELTEXTDISPLAY#2": 5,
        "Q_TEXTCONFIRM": 0, "L_TEXT": 4, "X_TEXT": "测试"}}],
}


def case_c80():
    _msg, _result, plan = build(C80)
    check("C80 总位数", plan["bits"], 294)
    check("C80 字节数", plan["size"], 37)
    check("C80 P44 长度", plen(plan, "P44/CTCS-80"), [219, 196])
    check("C80 XML 行数", len(plan["rows"]), 18)
    check("C80 两行 GROUP_NID_ENGINE",
          [r[0] for r in plan["rows"] if r[0].startswith("GROUP_NID_ENGINE")],
          ["GROUP_NID_ENGINE(0)", "GROUP_NID_ENGINE(1)"])


def case_small():
    _msg, _result, plan = build(C81)
    check("C81 总位数/字节", (plan["bits"], plan["size"]), (154, 20))
    check("C81 P44 长度", plen(plan, "P44/CTCS-81"), [79, 56])
    _msg, _result, plan = build(C82)
    check("C82 总位数/字节", (plan["bits"], plan["size"]), (171, 22))
    check("C82 P44 长度", plen(plan, "P44/CTCS-82"), [96, 73])
    _msg, _result, plan = build(C83)
    check("C83 总位数/字节", (plan["bits"], plan["size"]), (154, 20))
    _msg, _result, plan = build(P58)
    check("P58 总位数/字节", (plan["bits"], plan["size"]), (131, 17))
    check("P58_L_PACKET", plen(plan, "P58"), [56])
    _msg, _result, plan = build(M15)
    check("M15 总位数/字节", (plan["bits"], plan["size"]), (98, 13))


def case_m3():
    _msg, _result, plan = build(M3_523)
    check("M3 总位数", plan["bits"], 653)
    check("M3 字节数", plan["size"], 82)
    check("M3 各包长度", [plen(plan, "P15"), plen(plan, "P21"), plen(plan, "P27"),
                          plen(plan, "P5"), plen(plan, "P44/CTCS-150")],
          [[66], [78], [86], [69], [279, 256]])
    rows = [r[0] for r in plan["rows"]]
    check("C150 TACN 两个 Q_EOATYPE", rows.count("Q_EOATYPE"), 2)
    check("C150 无 Q_EOALOC", "Q_EOALOC" in rows, False)
    check("P15 条件行仍在 XML 里", "T_ENDTIMER" in rows, True)


def case_p72():
    _msg, _result, plan = build(P72)
    check("P72 总位数/字节", (plan["bits"], plan["size"]), (199, 25))
    check("P72 文本行 bits=8", [r[1] for r in plan["rows"] if r[0] == "X_TEXT(L_TEXT)"], [8])
    check("P72 L_TEXT=4", row_value(plan, "L_TEXT"), "4")

    body = {"message": "M24", "header": HEADER,
            "packets": [dict(P72["packets"][0])]}
    body["packets"][0]["fields"] = dict(P72["packets"][0]["fields"])
    body["packets"][0]["fields"]["L_TEXT"] = 2
    _msg, _result, plan = build(body, charset="utf-16-be")
    check("P72 UTF-16 的 L_TEXT 改写为字节数", row_value(plan, "L_TEXT"), "4")


def case_auto_length():
    _msg, _result, plan = build(M3_523, auto=True)
    check("M3 auto L_MESSAGE", row_value(plan, "L_MESSAGE"), X.PLACEHOLDER)
    check("M3 auto P15_L_PACKET", row_value(plan, "P15_L_PACKET"), X.PLACEHOLDER)
    _msg, _result, plan = build(M15, auto=True)
    check("M15 auto L_MESSAGE 仍是数字", row_value(plan, "L_MESSAGE"), "13")


def expect_error(name, fn, exc_types):
    try:
        fn()
    except exc_types as exc:
        ok("%s（%s）" % (name, exc))
        return
    FAILS.append("%s：没有报错" % name)
    print("FAIL  %s：没有报错" % name)


def case_reject():
    def m129():
        body = {"message": "M129", "header": {"T_TRAIN": 1, "NID_ENGINE": 90},
                "packets": []}
        msg, header, entries = S.values_for_message(body, "m129")
        X.check_supported(msg, entries)

    def c51():
        body = {"message": "M24", "header": HEADER,
                "packets": [{"packet": "P44", "user": "CTCS-51",
                             "fields": {"N_PKTNUM": 1, "Q_PKTSEQ": 0,
                                        "MAPINDEX_FILE": "DEADBEEF"}}]}
        msg, header, entries = S.values_for_message(body, "c51")
        X.check_supported(msg, entries)

    def c132():
        body = {"message": "M3", "header": HEADER, "packets": [
            {"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 100}},
            {"packet": "P44", "user": "CTCS-132",
             "fields": {"N_STACNT": 0, "N_SIGSTACNT": 1, "NID_STA#2": 1}}]}
        msg, header, entries = S.values_for_message(body, "c132")
        X.check_supported(msg, entries)
        result = S.encode_message(msg, header, entries, {"p72_charset": "gb18030"})
        X.check_encoded(result)

    def p68():
        body = {"message": "M3", "header": HEADER, "packets": [
            {"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 100}},
            {"packet": "P68", "fields": {"Q_TRACKINIT": 1, "D_TRACKCOND": 1,
                                         "L_TRACKCOND": 1, "M_TRACKCOND": 1,
                                         "N_ITER": 0}}]}
        msg, header, entries = S.values_for_message(body, "p68")
        S.encode_message(msg, header, entries, {"p72_charset": "gb18030"})

    expect_error("拒绝车→地 M129", m129, (X.SimError,))
    expect_error("拒绝 CTCS-51", c51, (X.SimError,))
    expect_error("拒绝 C132 N_SIGSTACNT=1", c132, (X.SimError,))
    expect_error("拒绝 P68 Q_TRACKINIT=1", p68, (S.SpecError,))


def main():
    S.ensure_utf8_stdio()
    for fn in (case_c80, case_small, case_m3, case_p72, case_auto_length, case_reject):
        print("\n== %s ==" % fn.__name__)
        fn()
    print("")
    if FAILS:
        print("失败 %d 项：" % len(FAILS))
        for text in FAILS:
            print("  - %s" % text)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
