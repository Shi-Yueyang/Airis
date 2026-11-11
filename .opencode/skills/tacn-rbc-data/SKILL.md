---
name: tacn-rbc-data
description: "生成、反解、修改并校验 TACN 车地无线（OBS↔RBC）报文：把取值 JSON 生成为 hex 报文串或 RBC 模拟器 DataTable XML 输入文件（也支持按测试场景一次生成多条报文序列），或把 hex/二进制报文反解成 Markdown 字段报告（含 L_MESSAGE / L_PACKET / 位遍历 / 组成规则自洽检查）。用于 M2/M3/M6/M8/M15/M16/M18/M24/M32/M34/M39/M41/M45 与 M129/M132/M136/M146/M147/M149/M150/M154~M159 等消息、P0~P80 信息包、P44 内 CTCS 用户包（CTCS-51/54/80~84/131/132/136/150/151/152）的生成、反解、定点修改与联调核对。"
---

# TACN RBC 报文

按 `references/protocol.md` 内置的报文定义生成、反解和修改 OBS↔RBC 报文。脚本不含外部
模板，也不需要模板文件：报文结构（位宽、组成、条件字段、定长约束）全在 `scripts/rbc_spec.py`。
同一份取值 JSON 还可以渲染成 RBC 模拟器的 `DataTable` XML 输入文件（`sim-xml.md`）。

## 生成门禁（GATE，未通过禁止生成）

生成或修改前先在回复里贴出确认单，逐项写清「值 + 来源」，并把确认结果写进 values JSON 的
`intent` + `provenance`。确认单长什么样、每一格该问什么、失败怎么对照，见 `references/gate.md`；
脚本会检查，缺 `confirmed=true`、包顺序不符、未标注来源、占位值未授权都会 exit 1。

## 如何使用本技能

按任务读取对应文档，然后照做。每份阶段文档对本阶段任务都是完整的：

| 任务 | 读 |
|---|---|
| **生成/修改前必过：确认单、要问哪些项、intent/provenance、`--allow-placeholder`** | `references/gate.md` |
| 查某条消息的方向/定长/帧头/必选包（不生成） | `gen_rbc_msg.py --describe M155`（一次命令，不必 grep） |
| 把 hex/二进制反解成字段报告、看告警、确认自洽 | `decode.md` |
| 从取值 JSON 生成 hex 报文串 | `generate.md` |
| 从取值 JSON 生成 RBC 模拟器 DataTable XML 输入文件 | `sim-xml.md` |
| 按测试场景生成一组报文（模拟器 XML 序列） | `scenario.md` |
| 在已有报文上只改指定字段，其余保持不变 | `edit.md` |
| 查报文/信息包/用户包的位定义、组成表、字段含义 | `references/protocol.md` |

## 前置条件

- Python 3（只用标准库）。

