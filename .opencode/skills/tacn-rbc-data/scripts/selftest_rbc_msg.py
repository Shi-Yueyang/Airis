#!/usr/bin/env python3
"""TACN RBC 编解码自检：用协议定长约束 + 往返一致做字节级回归。

RBC 报文没有 CRC，也没有可依赖的真机样本，所以"生成结果是否可信"只有三条硬证据：
  1. 协议里写死的长度（L_MESSAGE 固定值、定长信息包的 L_PACKET）必须逐条命中；
  2. encode 时显式给出的每个值，decode 必须能在同一位置读到（值级往返）；
  3. decode -> capture values -> encode 必须得到同一串字节（字节级往返）。

另带解码健壮性用例（截断、未知消息号、填充位被改、残留字节）和必须被拦住的非法输入。
这些用例同时是"某条报文应该长什么样"的可执行参考。

用法：
    python <skill-dir>/scripts/selftest_rbc_msg.py         # 跑全部用例
    python <skill-dir>/scripts/selftest_rbc_msg.py -v      # 失败时打印 hex
    python <skill-dir>/scripts/selftest_rbc_msg.py -n M3   # 只跑名字含 M3 的用例

退出码：0 全部通过；1 有失败项。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rbc_spec as S  # noqa: E402

CASES = []
NEGATIVES = []
FAILED = []


def case(name, doc, expect_len=None, expect_lp=None):
    CASES.append((name, doc, expect_len, expect_lp))


def negative(name, doc, needle):
    NEGATIVES.append((name, doc, needle))


def LRBG(c, bg):
    return (c << 14) | bg

# ---------------------------------------------------------------------------
# 地 -> 车
# ---------------------------------------------------------------------------
case("M2 目视授权（无 P63）", {
    "M2": {"header": {"T_TRAIN": 11296, "M_ACK": 1, "NID_C": 1023, "NID_BG": 16383,
                      "Q_SCALE": 1, "D_SR": 2000}},
}, expect_len=12)

case("M2 目视授权 + P63 两个应答器组", {
    "M2": {"header": {"T_TRAIN": 11296, "NID_LRBG": LRBG(1018, 523), "Q_SCALE": 1,
                      "D_SR": 2000},
           "packets": [{"packet": "P63", "fields": {"N_ITER": 2, "Q_NEWCOUNTRY(k)": [0, 1],
                                                    "NID_C(k)": [None, 1018],
                                                    "NID_BG(k)": [524, 525]}}]},
})

case("M3 行车许可（P15 单区段）", {
    "M3": {"header": {"T_TRAIN": 34655, "M_ACK": 1, "NID_LRBG": LRBG(1018, 523)},
           "packets": [{"packet": "P15", "fields": {"Q_DIR": 1, "Q_SCALE": 1,
                                                     "L_ENDSECTION": 3000, "V_RELEASEDP": 127}}]},
}, expect_lp={"P15": 185})

case("M3 行车许可（P15+P21+P27+P5+P44/CTCS-150）", {
    "M3": {"header": {"T_TRAIN": 47492, "NID_LRBG": LRBG(1023, 5893)},
           "packets": [
               {"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 5000,
                                            "V_RELEASEDP": 127}},
               {"packet": "P21", "fields": {"Q_SCALE": 1, "D_GRADIENT#1": 0, "Q_GDIR#1": 1,
                                             "G_A#1": 3, "N_ITER": 1,
                                             "D_GRADIENT(k)": 5000, "Q_GDIR(k)": 1,
                                             "G_A(k)": 255}},
               {"packet": "P27", "fields": {"Q_SCALE": 1, "D_STATIC#1": 0, "V_STATIC#1": 20,
                                             "N_ITER#1": 0, "N_ITER#2": 1,
                                             "D_STATIC(k)": 5000, "V_STATIC(k)": 20,
                                             "N_ITER(k)": 0}},
               {"packet": "P5", "fields": {"Q_SCALE": 1, "D_LINK#1": 226, "Q_NEWCOUNTRY#1": 0,
                                           "NID_BG#1": 525, "Q_LINKREACTION#1": 2, "N_ITER": 0}},
               {"packet": "P44", "user": "CTCS-150",
                "fields": {"Q_EOALOC": 1, "Q_EOATYPE": 0, "NID_ENGINE": 90,
                           "NID_OPERATIONAL": 22, "V_TRAIN": 50, "Q_DIR_HANDLE": 1,
                           "Q_TRACTION_HANDLE": 1, "M_HEAD_PRESSURE": 200,
                           "M_TAIL_PRESSURE": 200, "KILOMETER_POST": 200}},
           ]},
})

case("M3 线路条件 P68（防汛区段 + 1 个迭代）", {
    "M3": {"header": {"T_TRAIN": 41, "NID_LRBG": LRBG(1018, 523)},
           "packets": [{"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 2000}},
                       {"packet": "P68", "fields": {"Q_TRACKINIT": 0, "D_TRACKCOND#1": 800,
                                                     "L_TRACKCOND#1": 300, "M_TRACKCOND#1": 10,
                                                     "N_ITER": 1, "D_TRACKCOND(k)": 1500,
                                                     "L_TRACKCOND(k)": 200,
                                                     "M_TRACKCOND(k)": 1}}]},
})

case("M3 引导区段 P80（两段）", {
    "M3": {"header": {"T_TRAIN": 42, "NID_LRBG": LRBG(1018, 523)},
           "packets": [{"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 2000}},
                       {"packet": "P80", "fields": {"Q_SCALE": 1, "D_MAMODE#1": 0,
                                                     "M_MAMODE#1": 0, "V_MAMODE#1": 4,
                                                     "L_MAMODE#1": 400, "N_ITER": 1,
                                                     "D_MAMODE(k)": 800, "V_MAMODE(k)": 8,
                                                     "L_MAMODE(k)": 300}}]},
})

case("M6 确认退出冒进防护", {
    "M6": {"header": {"T_TRAIN": 114950, "NID_LRBG": LRBG(1018, 277)}},
}, expect_len=10)

case("M8 列车数据确认", {
    "M8": {"header": {"T_TRAIN#1": 300, "T_TRAIN#2": 129123}},
}, expect_len=14)

case("M15 有条件紧急停车", {
    "M15": {"header": {"T_TRAIN": 119370, "NID_LRBG": LRBG(1018, 523), "NID_EM": 1,
                       "Q_SCALE": 1, "Q_DIR": 1, "D_EMERGENCYSTOP": 500}},
}, expect_len=13)

case("M16 无条件紧急停车", {
    "M16": {"header": {"T_TRAIN": 100, "NID_LRBG": LRBG(1018, 523), "NID_EM": 0}},
})

case("M18 取消紧急停车", {
    "M18": {"header": {"T_TRAIN": 100, "NID_LRBG": LRBG(1018, 523), "NID_EM": 3}},
})

case("M24 通常消息（P58 + P3）", {
    "M24": {"header": {"T_TRAIN": 7581, "NID_LRBG": LRBG(1023, 16383)},
            "packets": [
                {"packet": "P58", "fields": {"Q_SCALE": 1, "T_CYCLOC": 2, "D_CYCLOC": 32767,
                                              "M_LOC": 1, "N_ITER": 0}},
                {"packet": "P3", "fields": {"Q_SCALE": 1, "N_ITER": 1, "NID_C": [10],
                                             "V_NVSHUNT": 8, "V_NVSTFF": 8, "V_NVONSIGHT": 8,
                                             "V_NVUNFIT": 16, "D_NVPOTRP": 1}},
            ]},
}, expect_lp={"P58": 56, "P3": 186})

case("M24 MA 请求参数 P57", {
    "M24": {"header": {"T_TRAIN": 43, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P57", "fields": {"T_MAR": 60, "T_TIMEOUTRQST": 1023,
                                                      "T_CYCRQST": 60}}]},
}, expect_lp={"P57": 49})

case("M24 纯文本 P72", {
    "M24": {"header": {"T_TRAIN": 20, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P72",
                         "fields": {"Q_SCALE": 1, "D_TEXTDISPLAY": 32767,
                                    "M_MODETEXTDISPLAY#1": 15, "M_LEVELTEXTDISPLAY#1": 5,
                                    "L_TEXTDISPLAY": 32767, "T_TEXTDISPLAY": 1023,
                                    "M_MODETEXTDISPLAY#2": 15, "M_LEVELTEXTDISPLAY#2": 5,
                                    "Q_TEXTCONFIRM": 1, "L_TEXT": 4, "X_TEXT": "注意限速"}}]},
})

case("M24 等级切换 P41（C3 后取消）", {
    "M24": {"header": {"T_TRAIN": 21, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P41",
                         "fields": {"Q_SCALE": 1, "D_LEVELTR": 32767, "M_LEVELTR#1": 3,
                                    "N_ITER": 1, "M_LEVELTR(k)": 1, "NID_STM(k)": 3}}]},
})

case("M24 双条限速 + 一条取消", {
    "M24": {"header": {"T_TRAIN": 22, "NID_LRBG": LRBG(1018, 523)},
            "packets": [
                {"packet": "P65", "fields": {"Q_SCALE": 1, "NID_TSR": 127, "D_TSR": 1000,
                                              "L_TSR": 2000, "Q_FRONT": 1, "V_TSR": 12}},
                {"packet": "P65", "fields": {"Q_SCALE": 1, "NID_TSR": 128, "D_TSR": 4000,
                                              "L_TSR": 500, "Q_FRONT": 1, "V_TSR": 8}},
                {"packet": "P66", "fields": {"NID_TSR": 127}},
            ]},
}, expect_lp={"P65": 71, "P66": 31})

case("M24 CTCS-80 编组命令", {
    "M24": {"header": {"T_TRAIN": 3277070, "M_ACK": 1, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P44", "user": "CTCS-80",
                         "fields": {"GROUP_ID": 2, "N_TRAINNUM": 2,
                                    "Group_NID_ENGINE": [90, 91], "NID_ENGINE_PRE": 90,
                                    "M_IP_PRE": "172.16.27.100.172.16.28.100"}}]},
})

case("M24 CTCS-81 / CTCS-82 / CTCS-83", {
    "M24": {"header": {"T_TRAIN": 3285470, "M_ACK": 1, "NID_LRBG": LRBG(1018, 523)},
            "packets": [
                {"packet": "P44", "user": "CTCS-81", "fields": {"GROUP_ID": 2}},
                {"packet": "P44", "user": "CTCS-82",
                 "fields": {"GROUP_ID": 2, "Q_SCALE": 1, "D_DECOUPLEPOS": 0}},
                {"packet": "P44", "user": "CTCS-83", "fields": {"GROUP_ID": 2}},
            ]},
})

case("M24 CTCS-131 会话管理 + CTCS-152 后车信息", {
    "M24": {"header": {"T_TRAIN": 33, "NID_LRBG": LRBG(1018, 523)},
            "packets": [
                {"packet": "P44", "user": "CTCS-131",
                 "fields": {"Q_SCALE": 1, "Q_CMDTYPE": 0, "Q_RBC": 1, "NID_C": 1018,
                             "NID_RBC": 5, "NID_RADIO": "10.1.1.1.10.1.1.2"}},
                {"packet": "P44", "user": "CTCS-152",
                 "fields": {"NID_ENGINE": 91, "NID_OPERATIONAL": 23, "V_TRAIN": 60,
                             "Q_DIR_HANDLE": 1, "Q_TRACTION_HANDLE": 3, "M_HEAD_PRESSURE": 580,
                             "M_TAIL_PRESSURE": 570, "KILOMETER_POST": 12345}},
            ]},
})

case("M24 CTCS-131 RBC 移交", {
    "M24": {"header": {"T_TRAIN": 33.5 if False else 34, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P44", "user": "CTCS-131",
                         "fields": {"Q_SCALE": 1, "Q_CMDTYPE": 1, "D_RBCTR": 1200,
                                    "NID_C": 1018, "NID_RBC": 6,
                                    "NID_RADIO": "10.2.2.1.10.2.2.2"}}]},
})

case("M3 CTCS-132 道岔/信号状态（双层迭代）", {
    "M3": {"header": {"T_TRAIN": 35, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P15", "fields": {"Q_SCALE": 1, "L_ENDSECTION": 1000}},
                        {"packet": "P44", "user": "CTCS-132",
                         "fields": {"N_STACNT": 1, "NID_STA#1": 701, "N_TO": 2,
                                    "NID_TO": [11, 12], "Q_TOSTATUS": [1, 2],
                                    "N_SIGSTACNT": 1, "NID_STA#2": 701, "N_SIG": 1,
                                    "NID_SIG": [21], "Q_SIGSTATUS": [1]}}]},
})

case("M24 CTCS-51 地图版本（数据块）", {
    "M24": {"header": {"T_TRAIN": 36, "NID_LRBG": LRBG(1018, 523)},
            "packets": [{"packet": "P44", "user": "CTCS-51",
                         "fields": {"N_PKTNUM": 2, "Q_PKTSEQ": 1,
                                    "MAPINDEX_FILE": "DEADBEEF01"}}]},
})

case("M32 系统版本", {"M32": {"header": {"T_TRAIN": 37, "M_VERSION": 16}}}, expect_len=11)

case("M34 TAF 请求", {
    "M34": {"header": {"T_TRAIN": 38, "NID_LRBG": LRBG(1018, 523), "Q_SCALE": 1, "Q_DIR": 2,
                       "D_TAFDISPLAY": 200, "L_TAFDISPLAY": 200}},
}, expect_len=14)

case("M39 / M41 会话纯帧头", {
    "M39": {"header": {"T_TRAIN": 39}},
    "M41": {"header": {"T_TRAIN": 40}},
}, expect_len=10)

case("M45 分配坐标系", {
    "M45": {"header": {"T_TRAIN": 41, "NID_LRBG": LRBG(1018, 523), "Q_ORIENTATION": 1}},
})

# ---------------------------------------------------------------------------
# 车 -> 地
# ---------------------------------------------------------------------------
POSITION = {"Q_SCALE": 1, "NID_LRBG": LRBG(1018, 523), "D_LRBG": 12, "Q_DIRLRBG": 1,
            "Q_DLRBG": 1, "L_DOUBTOVER": 10, "L_DOUBTUNDER": 10, "Q_LENGTH": 1,
            "L_TRAININT": 200, "V_TRAIN": 80, "Q_DIRTRAIN": 1, "M_MODE": 1, "M_LEVEL": 3}

case("M129 列车数据（P0 + P11）", {
    "M129": {"header": {"T_TRAIN": 50, "NID_ENGINE": 90},
             "packets": [{"packet": "P0", "fields": dict(POSITION)},
                         {"packet": "P11", "fields": {"NID_OPERATIONAL": 22, "NC_TRAIN": 8,
                                                      "L_TRAIN": 200, "V_MAXTRAIN": 40,
                                                      "M_AXLELOAD": 28, "N_ITER#1": 0,
                                                      "N_ITER#2": 1, "NID_STM(k)": [3]}}]},
})

case("M132 请求 MA（P1 + CTCS-136）", {
    "M132": {"header": {"T_TRAIN": 51, "NID_ENGINE": 90, "Q_TRACKDEL": 0},
             "packets": [{"packet": "P1", "fields": dict(POSITION, NID_PRVBG=LRBG(1018, 522))},
                         {"packet": "P44", "user": "CTCS-136",
                          "fields": {"NID_C": 1018, "NID_BG": 524}}]},
}, expect_lp={"CTCS-136": 46})

case("M136 位置报告（P0 + CTCS-151 + P4 + CTCS-54 + CTCS-84）", {
    "M136": {"header": {"T_TRAIN": 52, "NID_ENGINE": 90},
             "packets": [
                 {"packet": "P0", "fields": dict(POSITION)},
                 {"packet": "P44", "user": "CTCS-151",
                  "fields": {"Q_DIR_HANDLE": 1, "Q_TRACTION_HANDLE": 3,
                             "M_HEAD_PRESSURE": 580, "M_TAIL_PRESSURE": 575,
                             "KILOMETER_POST": 1024}},
                 {"packet": "P4", "fields": {"M_ERROR": 3}},
                 {"packet": "P44", "user": "CTCS-54",
                  "fields": {"N_PKTNUM": 3, "Q_PKTSEQ": 0, "N_MAPCNT": 2,
                             "M_MAPID": [701, 702], "M_GEODATAVERSION": [5, 5],
                             "M_GEODATACRC": [1234, 5678], "M_FIXDATAVERSION": [2, 2],
                             "M_FIXDATACRC": [99, 100], "N_TSRCNT": [1, 0],
                             "M_TSRDATACRC": [7777, 0]}},
                 {"packet": "P44", "user": "CTCS-84",
                  "fields": {"GROUP_ID": 2, "Q_SCALE": 1, "D_DIFF": 15}},
             ]},
}, expect_lp={"P4": 29})

case("M146 确认", {"M146": {"header": {"T_TRAIN#1": 60, "T_TRAIN#2": 34655}}}, expect_len=14)

case("M147 紧急停车确认", {
    "M147": {"header": {"T_TRAIN": 61, "NID_ENGINE": 90, "NID_EM": 1, "Q_EMERGENCYSTOP": 0},
             "packets": [{"packet": "P0", "fields": dict(POSITION)}]},
})

case("M149 / M150 纯位置报告", {
    "M149": {"header": {"T_TRAIN": 62, "NID_ENGINE": 90},
             "packets": [{"packet": "P0", "fields": dict(POSITION)}]},
    "M150": {"header": {"T_TRAIN": 63, "NID_ENGINE": 90},
             "packets": [{"packet": "P0", "fields": dict(POSITION)}]},
})

case("M154/155/156/159 会话纯帧头", {
    "M154": {"header": {"T_TRAIN": 64, "NID_ENGINE": 90}},
    "M155": {"header": {"T_TRAIN": 65, "NID_ENGINE": 90}},
    "M156": {"header": {"T_TRAIN": 66, "NID_ENGINE": 90}},
    "M159": {"header": {"T_TRAIN": 67, "NID_ENGINE": 90}},
}, expect_len=10)

case("M157 SoM 位置报告 + P4", {
    "M157": {"header": {"T_TRAIN": 68, "NID_ENGINE": 90, "Q_STATUS": 1},
             "packets": [{"packet": "P0", "fields": dict(POSITION)},
                         {"packet": "P4", "fields": {"M_ERROR": 7}}]},
})

case("M136 P0 方向未知（无 L_TRAININT，M_LEVEL=1 带 NID_STM）", {
    "M136": {"header": {"T_TRAIN": 69, "NID_ENGINE": 90},
             "packets": [{"packet": "P1",
                          "fields": {"Q_SCALE": 1, "NID_LRBG": 16777215,
                                     "NID_PRVBG": LRBG(1018, 522), "D_LRBG": 32767,
                                     "Q_DIRLRBG": 2, "Q_DLRBG": 2, "L_DOUBTOVER": 32767,
                                     "L_DOUBTUNDER": 32767, "Q_LENGTH": 0, "V_TRAIN": 0,
                                     "Q_DIRTRAIN": 2, "M_MODE": 1, "M_LEVEL": 1,
                                     "NID_STM": 3}}]},
})

# ---------------------------------------------------------------------------
# 反例
# ---------------------------------------------------------------------------
negative("M3 缺必选 P15", {"M3": {"header": {"T_TRAIN": 1}}}, "缺少必选信息包")
negative("P3 N_ITER=2 撞定长", {"M24": {"header": {"T_TRAIN": 1},
                                        "packets": [{"packet": "P3",
                                                     "fields": {"Q_SCALE": 1, "N_ITER": 2,
                                                                "NID_C": [1, 2]}}]}},
         "计算得 L_PACKET")
negative("P58 N_ITER=1 撞定长", {"M24": {"header": {"T_TRAIN": 1},
                                         "packets": [{"packet": "P58",
                                                       "fields": {"Q_SCALE": 1, "N_ITER": 1,
                                                                  "D_LOC(k)": [100],
                                                                  "Q_LGTLOC(k)": [1]}}]}},
         "计算得 L_PACKET")
negative("P68 Q_TRACKINIT=1", {"M3": {"header": {"T_TRAIN": 1},
                                      "packets": [{"packet": "P15",
                                                   "fields": {"Q_SCALE": 1, "L_ENDSECTION": 100}},
                                                  {"packet": "P68",
                                                   "fields": {"Q_TRACKINIT": 1,
                                                              "D_TRACKCOND#1": 1,
                                                              "L_TRACKCOND#1": 1,
                                                              "M_TRACKCOND#1": 0}}]}},
         "Q_TRACKINIT=1")
negative("编组用户包但 M_ACK=0", {"M24": {"header": {"T_TRAIN": 1, "M_ACK": 0},
                                          "packets": [{"packet": "P44", "user": "CTCS-80",
                                                       "fields": {"GROUP_ID": 1,
                                                                  "N_TRAINNUM": 1,
                                                                  "Group_NID_ENGINE": [90],
                                                                  "M_IP_PRE":
                                                                  "10.0.0.1.10.0.0.2"}}]}},
         "M_ACK")
negative("M2 塞进 P15", {"M2": {"header": {"T_TRAIN": 1, "Q_SCALE": 1, "D_SR": 100},
                                "packets": [{"packet": "P15",
                                             "fields": {"L_ENDSECTION": 1}}]}}, "不在 M2")
negative("P44 用户包不在组成表", {"M2": {"header": {"T_TRAIN": 1, "Q_SCALE": 1, "D_SR": 100},
                                         "packets": [{"packet": "P44", "user": "CTCS-150",
                                                      "fields": {}}]}}, "不承载")
negative("重复 P21（规则 1-9）", {"M3": {"header": {"T_TRAIN": 1},
                                         "packets": [{"packet": "P15",
                                                      "fields": {"Q_SCALE": 1, "L_ENDSECTION": 1}},
                                                     {"packet": "P21", "fields": {}},
                                                     {"packet": "P21", "fields": {}}]}},
         "出现 2 次")
negative("两条限速同 NID_TSR", {"M24": {"header": {"T_TRAIN": 1},
                                        "packets": [{"packet": "P65",
                                                     "fields": {"Q_SCALE": 1, "NID_TSR": 130, "D_TSR": 1,
                                                                "L_TSR": 1, "V_TSR": 1}},
                                                    {"packet": "P65",
                                                     "fields": {"Q_SCALE": 1, "NID_TSR": 130, "D_TSR": 2,
                                                                 "L_TSR": 1, "V_TSR": 1}}]}},
         "NID_TSR=130 重复")
negative("车地包混进地车报文", {"M3": {"header": {"T_TRAIN": 1},
                                       "packets": [{"packet": "P15",
                                                    "fields": {"Q_SCALE": 1, "L_ENDSECTION": 1}},
                                                   {"packet": "P0",
                                                    "fields": dict(POSITION)}]}},
         "车→地信息包")
negative("越界取值", {"M6": {"header": {"T_TRAIN": 1, "M_ACK": 5}}}, "上限")
negative("拼错的键", {"M6": {"header": {"T_TRAIN": 1, "NID_TYPO": 3}}}, "没有被任何字段消费")
negative("序号写错", {"M6": {"header": {"T_TRAIN#2": 1}}}, "没有第 2 个出现处")
negative("条件字段给标量", {"M24": {"header": {"T_TRAIN": 1},
                                    "packets": [{"packet": "P5",
                                                 "fields": {"Q_SCALE": 1, "D_LINK#1": 100,
                                                            "Q_NEWCOUNTRY#1": 0,
                                                            "NID_C": 1018,
                                                            "NID_BG#1": 524,
                                                            "Q_LINKREACTION#1": 2,
                                                            "N_ITER": 0}}]}},
         "不进报文")
negative("文本长度不符", {"M24": {"header": {"T_TRAIN": 1},
                                  "packets": [{"packet": "P72",
                                               "fields": {"Q_SCALE": 1, "L_TEXT": 4, "X_TEXT": "四字好"}}]}},
         "不符")
negative("IP 段数不对", {"M24": {"header": {"T_TRAIN": 1, "M_ACK": 1},
                                 "packets": [{"packet": "P44", "user": "CTCS-80",
                                              "fields": {"GROUP_ID": 1, "N_TRAINNUM": 1,
                                                         "Group_NID_ENGINE": [90],
                                                         "M_IP_PRE": "172.16.27.100"}}]}},
         "IP 需要 8 段")
negative("列表下标越界", {"M24": {"header": {"T_TRAIN": 1},
                                  "packets": [{"packet": "P63",
                                               "fields": {"N_ITER": 2,
                                                          "NID_BG(k)": [524]}}]}},
         "越界")


def lpacket_map(result):
    """{(报文内标签): 声明的 L_PACKET 位数}，P44 内外层分开记录。"""
    out = {}
    metas = result.get("metas") or []
    for row in result["rows"]:
        if row["base"] != "L_PACKET" or row["value"] is None:
            continue
        meta = metas[row["fid"] - 1] if 0 < row["fid"] <= len(metas) else (0, None)
        nid, user = meta
        inner = user is not None and row["occ"] == 2
        label = ("CTCS-%d" % user) if inner else ("P%d" % nid)
        out[label] = row["value"]
    return out


def run_case(name, doc, expect_len, expect_lp):
    problems = []
    for label, body in sorted(doc.items()):
        try:
            msg, header, entries = S.values_for_message(body, label)
            enc = S.encode_message(msg, header, entries)
        except S.SpecError as exc:
            return ["%s: 生成失败 —— %s" % (label, exc)]
        data = enc["data"]
        if expect_len is not None and len(data) != expect_len:
            problems.append("%s: 报文 %d 字节，协议固定 L_MESSAGE=%d 字节"
                            % (label, len(data), expect_len))
        for text in enc["warnings"]:
            problems.append("%s: 生成告警 —— %s" % (label, text))

        dec = S.decode_message(data)
        for text in dec["errors"]:
            problems.append("%s: 解码报错 —— %s" % (label, text))
        for text, got, verdict in dec["checks"]:
            if verdict != "OK":
                problems.append("%s: 解码自洽检查 %s -> %s（%s）" % (label, text, verdict, got))
        for text in dec["warnings"]:
            problems.append("%s: 解码告警 —— %s" % (label, text))

        # 定长信息包
        got_lp = lpacket_map(dec)
        for key, want in sorted((expect_lp or {}).items()):
            if key not in got_lp:
                problems.append("%s: 解码结果里没有 %s 的 L_PACKET" % (label, key))
            elif got_lp[key] != want:
                problems.append("%s: %s L_PACKET=%d，协议固定 %d"
                                % (label, key, got_lp[key], want))

        # 值级往返：显式给过的每个值，必须能在解码结果同一位置读到
        def index(rows, only_explicit):
            table = {}
            for row in rows:
                if row["omitted"] or row["source"] in ("自动计算", "固定"):
                    continue
                if only_explicit and row["source"] == "协议默认":
                    continue
                table[(row["fid"], row["base"], row["occ"], row["idx"], row["total"])] = row["value"]
            return table

        enc_keys = index(enc["rows"], True)
        dec_keys = index(dec["rows"], False)
        for key, value in sorted(enc_keys.items(), key=lambda kv: str(kv[0])):
            got = dec_keys.get(key, "（没读到）")
            if got != value:
                problems.append("%s: 第 %d 帧 %s%s 输入 %r，回读 %r"
                                % (label, key[0], key[1],
                                   "(%s)" % ",".join(str(i) for i in key[3]) if key[3] else "",
                                   value, got))

        # 字节级往返：回读值重新生成必须得到同一串
        captured = S.capture_message(dec)
        try:
            again = S.encode_message(msg, captured["header"],
                                     [S.entry_from_spec(e) for e in captured["packets"]])
        except S.SpecError as exc:
            problems.append("%s: 用回读值重新生成失败 —— %s" % (label, exc))
        else:
            if again["data"] != data:
                problems.append("%s: 回读值重新生成后字节不同\n        原串 %s\n        重生成 %s"
                                % (label, data.hex().upper(), again["data"].hex().upper()))
    return problems


def run_negative(name, doc, needle):
    label, body = list(sorted(doc.items()))[0]
    try:
        msg, header, entries = S.values_for_message(body, label)
        S.encode_message(msg, header, entries)
    except S.SpecError as exc:
        if needle not in str(exc):
            return ["报错信息不含 %r，实际是：%s" % (needle, exc)]
        return []
    except Exception as exc:  # noqa: BLE001
        return ["抛出非 SpecError：%r" % (exc,)]
    return ["本该失败却生成成功"]


def run_robustness():
    problems = []

    def build(doc):
        label, body = list(sorted(doc.items()))[0]
        msg, header, entries = S.values_for_message(body, label)
        return msg, S.encode_message(msg, header, entries)["data"]

    doc = {"M3": {"header": {"T_TRAIN": 70, "NID_LRBG": (1018 << 14) | 523},
                  "packets": [{"packet": "P15", "fields": {"Q_SCALE": 1,
                                                            "L_ENDSECTION": 2500}}]}}
    _msg, data = build(doc)
    res = S.decode_message(data[:5])
    if not res["errors"]:
        problems.append("报文被截断到 5 字节，解码没有报错")
    res = S.decode_message(bytes([0x77, 0x0A]) + b"\x00" * 8)
    if not any("NID_MESSAGE" in e for e in res["errors"]):
        problems.append("未知 NID_MESSAGE 没有被识别")

    doc = {"M16": {"header": {"T_TRAIN": 1, "NID_EM": 0}}}
    _msg, data = build(doc)
    broken = bytearray(data)
    broken[-1] ^= 0x01
    res = S.decode_message(bytes(broken))
    if not any("填充位" in w for w in res["warnings"]):
        problems.append("末尾填充位被改动，解码没有告警")

    doc = {"M24": {"header": {"T_TRAIN": 1},
                   "packets": [{"packet": "P66", "fields": {"NID_TSR": 130}}]}}
    _msg, data = build(doc)
    res = S.decode_message(data + b"\x55")
    if not any("未属于本报文" in w or "L_MESSAGE" in w for w in res["warnings"]):
        problems.append("数据里多出 1 字节，解码没有提示 L_MESSAGE 之外的残留")

    doc = {"M3": {"header": {"T_TRAIN": 1},
                  "packets": [{"packet": "P15", "fields": {"Q_SCALE": 1,
                                                            "L_ENDSECTION": 2500}}]}}
    _msg, data = build(doc)
    junk = bytearray(data)
    junk[-1] = 0x99          # 让最后一个包声明变长，制造越界
    res = S.decode_message(bytes(junk))
    if not (res["errors"] or res["warnings"]):
        problems.append("报文被破坏后解码既无错误也无告警")
    return problems


def main():
    ap = argparse.ArgumentParser(description="TACN RBC 编解码自检（无真机样本时的字节级回归）")
    ap.add_argument("-v", "--verbose", action="store_true", help="失败时打印解码字段行")
    ap.add_argument("-n", "--name", help="只跑名字里含该串的用例")
    args = ap.parse_args()

    passed = 0
    for name, doc, expect_len, expect_lp in CASES:
        if args.name and args.name not in name:
            continue
        problems = run_case(name, doc, expect_len, expect_lp)
        if problems:
            FAILED.append(name)
            print("FAIL  %s" % name)
            for text in problems:
                print("      - %s" % text)
            if args.verbose:
                for label, body in sorted(doc.items()):
                    msg, header, entries = S.values_for_message(body, label)
                    data = S.encode_message(msg, header, entries)["data"]
                    print("      hex: %s" % data.hex().upper())
        else:
            passed += 1
            print("ok    %s" % name)

    print("--- 反例（必须被拦住）")
    for name, doc, needle in NEGATIVES:
        if args.name and args.name not in name:
            continue
        problems = run_negative(name, doc, needle)
        if problems:
            FAILED.append(name)
            print("FAIL  %s" % name)
            for text in problems:
                print("      - %s" % text)
        else:
            passed += 1
            print("ok    %s" % name)

    print("--- 解码健壮性")
    problems = run_robustness()
    if problems:
        FAILED.append("解码健壮性")
        for text in problems:
            print("      - %s" % text)
    else:
        passed += 1
        print("ok    截断 / 未知消息号 / 填充位改动 / 残留字节 / 破坏位")

    print("-" * 64)
    print("通过 %d 项，失败 %d 项" % (passed, len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
