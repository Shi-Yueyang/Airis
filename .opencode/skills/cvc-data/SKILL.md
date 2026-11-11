---
name: cvc-data
description: "使用 ATP 与 SDMU 模板 XML 反解、生成、编辑和校验 CVC 应用数据文件（ASW1.bin、Config2.line1、Config1.train），输出字段遍历报告并做往返校验。适用于这些文件的任何检查、审计、生成、编辑或校验任务，也用于解释 CRC MISMATCH、OUT-OF-RANGE、TEMPLATE/DATA MISMATCH 等解码告警。"
---

# CVC 数据

使用随技能提供的脚本反解、生成和编辑 CVC 应用数据二进制文件。线格式以
`references/protocol.md` 为唯一规范。

## 如何使用本技能

按任务读取对应文档，然后照做。每份阶段文档对本阶段任务都是完整的：

| 任务 | 读 |
|---|---|
| 检查/审计数据文件、解释告警、捕获取值 | `decode.md` |
| 由模板生成数据文件（必须提供 values JSON；一次性覆盖用 `--set`） | `generate.md` |
| 修改既有文件中的指定取值，其余保持不变 | `edit.md` |
| 线格式问题（帧结构、各 DIST 类的 magic、字段顺序） | `references/protocol.md` |

## 前置条件

- Python 3（仅标准库）。脚本只处理本地文件：不调用外部进程，不访问网络。
- 匹配的 ATP 与 SDMU 模板 XML，且模板版本与数据版本一致。
