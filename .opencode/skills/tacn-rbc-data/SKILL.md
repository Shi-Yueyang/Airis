---
name: tacn-rbc-data
description: "生成、反解、修改并校验 TACN 车地无线（OBS↔RBC）报文：把取值 JSON 生成为 hex 报文串，或把 hex/二进制报文反解成 Markdown 字段报告（含 L_MESSAGE / L_PACKET / 位遍历 / 组成规则自洽检查）。用于 M2/M3/M6/M8/M15/M16/M18/M24/M32/M34/M39/M41/M45 与 M129/M132/M136/M146/M147/M149/M150/M154~M159 等消息、P0~P80 信息包、P44 内 CTCS 用户包（CTCS-51/54/80~84/131/132/136/150/151/152）的生成、反解、定点修改与联调核对。"
---

# TACN RBC 报文

按 `references/protocol.md` 内置的报文定义生成、反解和修改 OBS↔RBC 报文。脚本不含外部
模板，也不需要模板文件：报文结构（位宽、组成、条件字段、定长约束）全在 `scripts/rbc_spec.py`。

## 最短流程

1. `<skill-dir>/scripts/gen_rbc_msg.py --describe M155` —— 看方向、`L_MESSAGE`、帧头字段、
   必选/可选信息包和 values 骨架。
2. 先确认字段取值与产物要求（见下节「需要用户澄清的要点」），再按骨架写取值 JSON
   （`--values` 必填；无信息包也要写 `"packets": []`）。
3. `<skill-dir>/scripts/gen_rbc_msg.py --values values.json -o out/`。
4. `<skill-dir>/scripts/dump_rbc_msg.py out/M155.hex -o report.md`。
5. 按下面「验证与报告纪律」逐项确认，再交付。

## 需要用户澄清的要点

用户只给一个消息号并不算完整需求。生成或修改前，把下面几项逐项澄清：用户已经说清楚的
不要重复问；没说清的可以分多次提问，直到要点收齐再动手。不要替用户编业务值。

| 要确认 | 具体问什么 |
|---|---|
| 报文与数量 | 消息号、单条还是多条、是否含信息包/用户包 |
| 字段取值 | 举例：车→地的 `T_TRAIN`、`NID_ENGINE`，地→车的 `T_TRAIN`、`M_ACK`、`NID_LRBG`，以及必选包的关键字段；实际要问的字段以 `--describe` 列出的必填项为准 |
| 输出格式 | hex 一行连续 / 每字节空格 / 分行（`--hex-style`），要不要 Markdown 报告 |
| 存放位置 | 输出目录，尽量用绝对路径 |
| 文件名 | 默认顶层键 → `<键名>.hex`，是否需要改名 |
| 是否覆盖 | 目标目录已有同名文件时能否覆盖 |

表里“具体问什么”只是常见要点的举例，不是固定问卷；字段清单以 `--describe` 为准。

`--describe` 输出的 values 骨架里是**示例值**（例如 `"NID_ENGINE": 0`），只是占位，
不能直接当真实车号交付。要么问用户，要么在交付说明里明确标为占位。

如果用户把选择权交给你（"你看着办"），用这组默认并说明：plain hex、输出到系统临时目录、
文件名沿用 `<键名>.hex`、不覆盖已有文件；临时 values 也放临时目录，不要写进应用包仓库。

## 何时读哪份文档

| 任务 | 读 |
|---|---|
| 查某条消息的方向/定长/帧头/必选包（不生成） | `gen_rbc_msg.py --describe M155`（一次命令，不必 grep） |
| 把 hex/二进制反解成字段报告、看告警、确认自洽 | `decode.md` |
| 从取值 JSON 生成 hex 报文串 | `generate.md` |
| 在已有报文上只改指定字段，其余保持不变 | `edit.md` |
| 查报文/信息包/用户包的位定义、组成表、字段含义 | `references/protocol.md` |
| 查 L_PACKET 计数口径、P44 嵌套、键写法、定长回归基线 | `references/protocol.md` 附录 B/C |
| 想确认"这套编解码本身没坏" | `scripts/selftest_rbc_msg.py`（53 项，见附录 C.6） |

## 不要做（常见浪费）

- 查消息结构先跑 `--describe`。不要在 `rbc_spec.py` 里搜 `M155`：消息声明是
  `message(155, ...)`，搜消息名字必然搜不到。
- 位定义以 `references/protocol.md` 和 `--describe` 为准；`rbc_spec.py` 是实现，不是查询入口。
- 「验证与报告纪律」就在本文件；只有要解释具体告警/错误时再读 `decode.md`。
- 纯帧头消息（M6/M39/M41/M154/M155/M156/M159）不必通读 `generate.md`，看 `--describe`
  和三类最小样例即可。
- 没改 `rbc_spec.py` 就不要跑 `selftest_rbc_msg.py`；它证明编解码实现，不证明单条报文。
- 不要拿 `--describe` 骨架里的示例值（尤其 `NID_ENGINE=0`）直接生成交付；先对齐字段取值。

## 前置条件

- Python 3（只用标准库）。Windows PowerShell 先执行 `$env:PYTHONUTF8=1`
  （cmd 用 `set PYTHONUTF8=1`），否则中文报错/报告可能乱码；报告建议用 `-o`
  写文件后再读，不要依赖控制台回显。
- 生成：一份取值 JSON（`--values` 必填）。只给必须改的字段即可，协议有默认值的字段会回落
  并计入"回退字段"统计；`-v` 可逐字段查看取值来源。
- 反解：hex 文本（空格/逗号/冒号/`0x` 前缀都行）或原始二进制文件，二者自动判别，
  也可用 `--format hex|bin` 强制。
- 需要修改既有报文时：先用 `dump_rbc_msg.py --values-out` 把整条报文的取值导出来。
