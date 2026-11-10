---
name: tacn-rbc-data
description: "生成、反解、修改并校验 TACN 车地无线（OBS↔RBC）报文：把取值 JSON 生成为 hex 报文串或 RBC 模拟器 DataTable XML 输入文件，或把 hex/二进制报文反解成 Markdown 字段报告（含 L_MESSAGE / L_PACKET / 位遍历 / 组成规则自洽检查）。用于 M2/M3/M6/M8/M15/M16/M18/M24/M32/M34/M39/M41/M45 与 M129/M132/M136/M146/M147/M149/M150/M154~M159 等消息、P0~P80 信息包、P44 内 CTCS 用户包（CTCS-51/54/80~84/131/132/136/150/151/152）的生成、反解、定点修改与联调核对。"
---

# TACN RBC 报文

按 `references/protocol.md` 内置的报文定义生成、反解和修改 OBS↔RBC 报文。脚本不含外部
模板，也不需要模板文件：报文结构（位宽、组成、条件字段、定长约束）全在 `scripts/rbc_spec.py`。
同一份取值 JSON 还可以渲染成 RBC 模拟器的 `DataTable` XML 输入文件（`sim-xml.md`）。

## 0. 生成门禁（GATE，未通过禁止生成）

生成或修改前，先在回复里贴出确认单，逐项写清「值 + 来源」：

| 项 | 值 | 来源 |
|---|---|---|
| 消息号 / 方向 / 条数 | | |
| 信息包列表（按空口顺序） | | |
| 每个必填字段 | | |
| 占位字段清单 | | |
| 产物形态（hex / sim-xml / both） | | |
| 输出目录 / 文件名 / 是否覆盖 | | |

- 来源只能填「用户」「用户授权占位」「反解导出」「协议默认」；不得用 `--describe` 骨架代填。
- 任一格未确认 → 停止提问，不得调用生成脚本。
- 组成类问题必须单选；用户多选出现互斥项时，先复述并确认，不得自行取舍。
- 确认单写进 values JSON 的 `intent` + `provenance`（格式与失败对照见 `references/gate.md`）；
  脚本会检查，缺 `confirmed=true`、包顺序不符、未标注来源、占位值未授权都会 exit 1。

## 如何使用本技能

按任务读取对应文档，然后照做。每份阶段文档对本阶段任务都是完整的：

| 任务 | 读 |
|---|---|
| **生成/修改前必过：确认单、intent/provenance、`--allow-placeholder`** | `references/gate.md` |
| 查某条消息的方向/定长/帧头/必选包（不生成） | `gen_rbc_msg.py --describe M155`（一次命令，不必 grep） |
| 把 hex/二进制反解成字段报告、看告警、确认自洽 | `decode.md` |
| 从取值 JSON 生成 hex 报文串 | `generate.md` |
| 从取值 JSON 生成 RBC 模拟器 DataTable XML 输入文件 | `sim-xml.md` |
| 在已有报文上只改指定字段，其余保持不变 | `edit.md` |
| 查报文/信息包/用户包的位定义、组成表、字段含义 | `references/protocol.md` |
| 查 L_PACKET 计数口径、P44 嵌套、键写法、定长回归基线 | `references/protocol.md` 附录 B/C |
| 验证编解码实现是否仍符合协议基线 | `scripts/selftest_rbc_msg.py`（53 项，见附录 C.6） |
| 验证模拟器 XML 生成器是否仍符合长度基线 | `scripts/selftest_sim_xml.py`（长度基线 + 结构限制） |
| 验证生成门禁是否仍然拦得住 | `scripts/selftest_gate.py`（缺 intent/占位/包顺序/段来源） |

生成/修改的最短流程：

1. `<skill-dir>/scripts/gen_rbc_msg.py --describe M155` —— 看方向、`L_MESSAGE`、帧头字段、
   必选/可选信息包。骨架里的 `<待确认>`/`confirmed=false` 不能直接生成，只作形状参考。
2. **过门禁**：按 `references/gate.md` 贴出确认单并收齐取值；写入 `intent` + `provenance`。
3. `<skill-dir>/scripts/gen_rbc_msg.py --values values.json -o out/`（含占位值时必须显式加
   `--allow-placeholder`）。
4. `<skill-dir>/scripts/dump_rbc_msg.py out/M155.hex -o report.md`。
5. 按下面「校验与报告纪律」逐项确认，再交付；审计行要原样写进交付说明。

常见浪费：

- 查消息结构先跑 `--describe`。不要在 `rbc_spec.py` 里搜 `M155`：消息声明是
  `message(155, ...)`，搜消息名字必然搜不到。
- 位定义以 `references/protocol.md` 和 `--describe` 为准；`rbc_spec.py` 是实现，不是查询入口。
- 「校验与报告纪律」就在本文件；只有要解释具体告警/错误时再读 `decode.md`。
- 纯帧头消息（M6/M39/M41/M154/M155/M156/M159）不必通读 `generate.md`，看 `--describe`
  和三类最小样例即可。
- 没改 `rbc_spec.py` 就不要跑 `selftest_rbc_msg.py`；它证明编解码实现，不证明单条报文。
- 不要拿 `--describe` 骨架直接生成：骨架里是 `<待确认>` + `confirmed=false`，照抄必然被门禁拒绝；先对齐字段取值并写 `intent`/`provenance`。
- 模拟器 XML 不是 hex 的另一种排版：字段名、条件行和 P15 口径按模拟器模板走；不要用 hex 的 `L_PACKET` 当 XML 基线（`sim-xml.md` 限制）。

## 需要用户澄清的要点（门禁的输入）

用户只给一个消息号并不算完整需求。动手前逐项收齐；用户已经说清楚的不要重复问，
没说清的分多次提问。**不要替用户编业务值**，也不要把示例值当成默认值。

| 要确认 | 具体问什么 |
|---|---|
| 报文与数量 | 消息号、单条还是多条、是否含信息包/用户包（含哪些、顺序） |
| 字段取值 | 举例：车→地的 `T_TRAIN`、`NID_ENGINE`，地→车的 `T_TRAIN`、`M_ACK`、`NID_LRBG`，以及必选包的关键字段；实际要问的字段以 `--describe` 的「需给值」为准 |
| 占位授权 | 哪些字段可以先用占位值，是否允许本次生成（决定要不要 `--allow-placeholder`） |
| 输出格式 | hex 一行连续 / 每字节空格 / 分行（`--hex-style`），hex 还是模拟器 XML，要不要 Markdown 报告 |
| 存放位置 | 输出目录，尽量用绝对路径 |
| 文件名 | 默认顶层键 → `<键名>.hex`；模拟器默认 `dataTableM<n>.xml`，是否需要改名 |
| 是否覆盖 | 目标目录已有同名文件时能否覆盖 |

收齐后把答案写进 `intent`（`message`/`target`/`packets`/`confirmed`）和 `provenance`
（逐段来源），详见 `references/gate.md`。**确认单没有贴出、`confirmed` 不是 true 时，
脚本会拒绝生成**；不要靠“先跑一下再说”。

如果用户把选择权交给你（"你看着办"），用这组默认并说明：plain hex、输出到系统临时目录、
文件名沿用 `<键名>.hex`、不覆盖已有文件；临时 values 也放临时目录，不要写进应用包仓库。

## 前置条件

- Python 3（只用标准库）。Windows PowerShell 先执行 `$env:PYTHONUTF8=1`
  （cmd 用 `set PYTHONUTF8=1`），否则中文报错/报告可能乱码；报告建议用 `-o`
  写文件后再读，不要依赖控制台回显。
- 生成：一份取值 JSON（`--values` 必填），每个分组都要有 `intent` + `provenance`（见
  `references/gate.md`）。只给必须改的字段即可，协议有默认值的字段会回落并计入
  "回退字段"统计；`-v` 可逐字段查看取值来源。含 `placeholder` 时加 `--allow-placeholder`。
- 反解：hex 文本（空格/逗号/冒号/`0x` 前缀都行）或原始二进制文件，二者自动判别，
  也可用 `--format hex|bin` 强制。
- 需要修改既有报文时：先用 `dump_rbc_msg.py --values-out` 把整条报文的取值导出来。
- 生成模拟器 XML：取值 JSON 与 hex 相同，但报文必须是 RBC→车且信息包/用户包在模拟器分派表内；先跑 `gen_rbc_sim_xml.py --list`（`sim-xml.md`）。

## 校验与报告纪律

- **没有 CRC 就不能靠"能生成"下结论**。可依赖的最低标准是：反解报告中
  `L_MESSAGE` 一致、每个包的 `L_PACKET` 声明与计算一致、位遍历闭合（末尾只剩 ≤7 bit 补 1）、
  组成校验无错误、无告警。
- **生成后必须反解回来核对**：`gen_rbc_msg.py` 自己打印的 checks 只是生成侧的自洽，
  交付前用 `dump_rbc_msg.py` 再解一遍；定点修改还要核对"只有目标字段变了"。
- **不猜**：未知 NID_MESSAGE、未收录的信息包/用户包、位流越界一律报出来并停止该条报文，
  不要用"大概是这样"补字段。缺定义就补 `rbc_spec.py` + 附录 C，而不是手写偏移。
- **报告即证据**：写清输入文件、用了哪些 `--set`、字节数、L_MESSAGE/L_PACKET、告警清单，
  以及没做的检查（尤其：没有真机样本时不要声称与 RBC 侧字节一致）。
- **审计行必须进报告**：生成器打印的 `审计: 用户 N / 解码 N / 占位 N / 协议默认 N` 与
  `占位:` 清单要原样保留；占位不为 0 时逐项说明“尚未核对、需替换”。

## 固有限制

- 仓库里**没有** RBC 报文真机样本，所以"自洽通过"只证明长度/包长/位遍历/组成自洽，
  不证明 RBC 侧业务语义；附录 C.6 的定长基线来自协议本身。
- P44 外层 L_PACKET 是否包含整个内层用户包，是唯一没有协议直接证据的取舍（附录 C.3）。
- CTCS-152 的 `L_PACKET=118` 与其字段表冲突，本实现按字段表（附录 B-5）。
- P15 末区段定时字段按源文档 M3 样例的字段顺序实现，与 ETCS 标准的分组方式可能有差异（附录 B-3）。
- 文本编码（P72）默认 UTF-16BE，GB18030 需显式切换（附录 B-1）。
- 一条消息 ≤ 500 字节；含多条报文的流请用 `--split`，不要当成一条报文反解。
