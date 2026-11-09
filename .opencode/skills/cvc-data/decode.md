# 反解 — 检查 CVC 数据文件

使用 ATP 与 SDMU 模板 XML 把 CVC 应用数据二进制反解成字段遍历报告。只读：本流程绝不写入源文件。

## 格式参考

线格式（TLV 帧结构、各 DIST 类的 magic、固定的 ATP→SDMU 字段顺序、参考回归尺寸）定义在本技能目录的 `references/protocol.md`。

## 输入

- 按惯例命名为 `ASW1.bin`（DP）、`Config2.line1`（LINE）、`Config1.train`（TRAIN）的数据文件，但实际按 magic 识别，不按文件名。只支持单个按类拆分的文件；带 8 字节版本尾的拼接流不能在这里反解。
- ATP 与 SDMU 模板 XML（`ATPCfgTemplate.xml`、`SDMUCfgTemplate.xml`），确保每个字段都有模板。模板按 `<ASW SYMBOL>` 匹配字段，不按参数顺序。
- Python 3，仅标准库。

## 规则

1. **只读**：绝不编辑或覆盖源文件；反解只产生报告和可选的 values 捕获。
2. **不猜测**：未知 magic、文件过短、长度越界、缺字段都只报告；没有模板的字段列为未反解，不要为无法反解的区域编造取值。
3. **先判定可信再依赖**：只有每个文件都显示 `crc=OK`、每个字段都显示 `walk=OK` 且没有未计入字节、并且没有告警触发时，解码值才可信。
4. **先处理告警**：`CRC MISMATCH`、`TEMPLATE/DATA MISMATCH`、`OUT-OF-RANGE`、`no template for field` 等告警必须解决或解释清楚，再使用任何解码或捕获的取值。

## 工作流

1. **准备输入** — 确认数据文件是按类拆分的单文件，并准备匹配的 ATP 与 SDMU 模板 XML。模板版本必须与数据版本一致。
2. **执行反解** — 解码器是 `scripts/dump_cvc_data.py`；下文的 `<skill-dir>` 指本技能目录。输入输出路径相对当前工作目录解析。可以在一次调用中反解所有文件：

   ```sh
   python <skill-dir>/scripts/dump_cvc_data.py \
     -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
     ASW1.bin Config2.line1 Config1.train \
     -o decoded_report.md
   ```

   `-o` 把 Markdown 报告写入文件；不给则输出到 stdout。加 `--values-out values.json` 还会捕获完整的带命名空间 `{class: {function: {NAME: value}}}` JSON，`scripts/gen_cvc_data.py --values` 可直接用它重新生成（这是 `edit.md` 的捕获步骤）。REPEAT 组输出为列表。遍历失败的字段不会进入捕获；`EXTRA-SLOT` 行没有模板名，会跳过并告警。
3. **解读报告** —
   - 文件行：`DIST=… magic=0x… crc=OK|BAD file=…B fields=[0x66AA5599=18B, …]`
     —— CRC 覆盖整个文件去掉末尾 4 字节。
   - 字段行：`field=… body=…B walk=OK` | `walk=OK+NB-unaccounted`（模板消费的字节少于 body 实际长度） |
     `walk=INCOMPLETE(template-needs-more)`（body 在遍历中途耗尽）。后两种都表示模板/数据版本不匹配。
   - 表格行：每个参数的偏移（相对字段 body）、字节数、名称、十六进制和十进制取值。标记：`OUT-OF-RANGE [min..max]`（取值超出模板边界）和 `EXTRA-SLOT`（计数强制产生的条目多于模板固定的数量）。
   - 带 `SYMBOL` 的 `PARAM` 包装是嵌套 TLV。对于可选包装，解码器会在当前偏移检查其 4 字节 symbol；存在则读取 4 字节载荷长度，只遍历该有界载荷。参数偏移仍相对外层字段 body，因此包含 8 字节嵌套头。声明长度与模板长度不一致、包装载荷未被完全消费，都会作为告警报告。
4. **判定是否可信** — 逐文件确认 `crc=OK`；逐字段确认 `walk=OK` 且没有未计入字节；确认没有告警（`CRC MISMATCH`、`TEMPLATE/DATA MISMATCH`、`OUT-OF-RANGE`、`no template for field`、字段与 CRC 之间的未计入字节）。依赖任何解码或捕获的取值之前，先解决告警；`crc=OK walk=OK` 仍不能验证消费端领域语义。
5. **报告** — 写清输入文件、模板、每个文件的 CRC 与字段遍历结果、告警清单，以及没有执行的检查。

## 失败处理

解码器只报告、不猜测：未知 magic、文件过短、长度越界和缺字段会产生按文件的 `ERROR` 行，批处理继续；没有提供模板的字段 symbol 会列为未反解。不要为无法反解的区域编造取值——说明失败了什么、为什么。

| 现象 | 原因 | 处理 |
|---|---|---|
| `CRC MISMATCH` | 存储的 CRC 与覆盖范围内计算出的 CRC 不一致。 | 视为文件损坏/被修改；对照可信来源核实。 |
| `TEMPLATE/DATA MISMATCH` | 模板版本与数据版本不一致。 | 提供匹配的模板；在信任取值前检查二进制内容。 |
| `no template for field 0x…` | 某个字段 symbol 没有对应的 `-t` 模板。 | 同时传入 ATP 和 SDMU 模板。 |
| `OUT-OF-RANGE` | 存储值超出模板 `MINVALUE`/`MAXVALUE`。 | 报告它；检查是数据还是模板一侧有误。 |
| 未知 magic / 文件过短 | 不是按类拆分的文件，或流被截断/拼接。 | 先把流拆成按类文件；这些工具不反解组装后的流。 |

## 限制

- `crc=OK`/`walk=OK` 不能验证消费端的全部领域约束；相互依赖的取值要按消费端语义检查。
- 这些工具只处理按类拆分的文件；拼接流及其 8 字节版本尾属于流组装器，不在本流程范围内。
