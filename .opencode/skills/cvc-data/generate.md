# 生成 — 由模板产生 CVC 数据文件

把规范的 ATP + SDMU 模板对序列化成三个按类拆分的数据文件。这是生成器；要在既有数据上构建优先用 `edit.md`，检查文件优先用 `decode.md`。

## 格式参考

线格式、magic 和固定的 ATP→SDMU 字段顺序见本技能目录的 `references/protocol.md`。

## 必需输入

- Python 3，仅标准库。
- 两个模板 XML 都要给，顺序任意 —— 参考帧始终携带 ATP（`0x66AA5599`）和 SDMU（`0xA5A59696`）字段。
- 一份 values JSON（`--values`，**每次运行都必须给**），以及可选的 `--set` 覆盖。
- 一个可写的输出目录，且其中不能有要保留的源文件 —— 生成会覆盖其中的常规文件名 `ASW1.bin`、`Config2.line1`、`Config1.train`，而且每次运行都会写全部三个文件。

## 规则

1. **必须给 `--values`**：裸模板默认值生成会被拒绝，因此不会有任何一次运行悄悄变成默认值运行。
2. **两个模板必须成对**：生成器强制要求 ATP + SDMU 集合，并按协议规范顺序输出字段，与 `-t` 顺序无关。`BSWCfgTemplate.xml` 没有 `<ASW SYMBOL>`，会跳过并告警；其他任何应用字段 symbol 都会被拒绝。
3. **values 必须带命名空间**：扁平键和类共享键会被拒绝 —— 名称在不同模板之间会冲突（`WS_MIN_DIAMETER_1`、`G_ACCELERATION`），所以每个键都必须指明所属字段。
4. **每个键都必须命中模板**：过期名称、错误的类、错误的功能，或超出 `MINVALUE`/`MAXVALUE` 的取值，都会导致生成失败且输出目录保持原样 —— 不会写入任何不完整或误导性的内容。
5. **不要放宽模板范围**：不要为了让某个值通过而修改模板或放宽 `MINVALUE`/`MAXVALUE`；修正取值。
6. **制动规则只检查、不注入**：如果存在 `N_ITEM_SB7`/`N_ITEM_EB`，其计数必须至少为 1，且 `SB7_Decceleration`/`EB_Decceleration` 条目和 `Braking Calculation Parameter` 必须非零，否则生成失败并指出有问题的键。要交给消费端的 values 文件必须携带这些值。

## values 格式

`--values` 只接受带命名空间的形式（即 `dump_cvc_data.py --values-out` 输出的确切形状）—— 下面的每条规则都由生成器强制执行，无需人工预检：

```json
{ "TRAIN": { "ATP": { "TRAIN_ALLOW_SPEED": 220 }, "SDMU": { "WS_MIN_DIAMETER_1": 830 } } }
```

- 顶层按 DIST 类（`DP`/`LINE`/`TRAIN`）或按功能（`ATP`/`SDMU`，跨类适用）分组。
- 取值是整数或 `0x` 十六进制字符串；列表按下标对应 `([k])` 重复条目，标量会填充每个条目。
- 每个参数的优先级：类作用域键 > 功能全局键 > 模板 `DEFAULTVALUE` > `MINVALUE` > 0。values 文件未覆盖的参数沿这条链回落；每次运行都会打印回退计数，`-v` 会列出每个参数的取值来源。

## 工作流

1. **准备 values** — 用 `dump_cvc_data.py --values-out` 从匹配的模板版本捕获一份，或手写你要控制的键。临时覆盖无需改动文件 —— `--set` 可重复，优先于 `--values`，逗号分隔的取值用于对应 `([k])` 条目。
2. **生成** — 生成器是 `scripts/gen_cvc_data.py`；下文的 `<skill-dir>` 指本技能目录。输出路径相对当前工作目录解析。`--help` 列出所有选项；`-v` 打印逐字段偏移表。

   ```sh
   python <skill-dir>/scripts/gen_cvc_data.py \
     -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
     --values values.json \
     --set TRAIN.ATP.TRAIN_ALLOW_SPEED=220 \
     -o scratch/generated
   ```

3. **校验** — 生成输出不是证据。用同一组模板反解生成的文件（见 `decode.md`，或直接执行）：

   ```sh
   python <skill-dir>/scripts/dump_cvc_data.py \
     -t ATPCfgTemplate.xml -t SDMUCfgTemplate.xml \
     scratch/generated/ASW1.bin scratch/generated/Config2.line1 scratch/generated/Config1.train
   ```

   要求每个字段都满足 `crc=OK` 和 `walk=OK`。复现已知数据集时，还要与参考文件逐字节比较。报告告警和任何跳过的检查。
4. **报告** — 写清使用的模板和 values 文件、输出目录、CRC 与字段遍历结果、字节比较结果，以及任何告警或未执行的检查。

## 失败处理

| 错误 | 原因 | 处理 |
|---|---|---|
| `the following arguments are required: --values` | 生成时没有给 values 文件（不支持裸默认值运行）。 | 始终传 `--values`：用 `dump_cvc_data.py --values-out` 捕获一份，或写出你要控制的键。 |
| `no template given for ATP/SDMU` | 只传了模板对中的一个。 | 两个模板都要传。 |
| `un-namespaced key … rejected` | values 文件里有扁平键或类共享键。 | 按 `{class: {function: {NAME: value}}}` 分组，或改用 `--set`。 |
| `values keys matched by no template parameter` | 名称过期/拼错，或类/功能分组错误。 | 从匹配的模板版本重新捕获，或修正键路径。 |
| `value … below MINVALUE / above MAXVALUE` | 覆盖值超出模板边界。 | 修正取值；不要改模板来放宽范围。 |
| `count 0 leaves an empty table` / `effective value 0 breaks the consumer's braking calculation` | values 文件未覆盖或置零了制动除数/表参数。 | 添加具名的 `class.ATP.NAME` 键并给有效非零值；不要依赖回退。 |
| `note: N value(s) not covered by the values file fell back`（提示性） | values 文件没有覆盖每个参数。 | 用 `-v` 检查来源；回退计数较高说明 `MINVALUE`/`0` 回退很多，输出不是可交付配置。 |
| 输出与参考不同 | 取值或模板版本不同。 | 使用从同一版本捕获的取值（`edit.md` 流程）；`-t` 顺序不会导致这种情况。 |

## 限制

- `crc=OK`/`walk=OK` 不能验证消费端的全部领域约束。修改相互依赖的取值时，要检查消费端语义。
- 固定数组包装（`ID_MODE_LIMITED_SPEED`、`ID_SDM_LIMITED_SPEED`）会把写入计数强制为模板的显式条目数；`([k])` REPEAT 组的计数来自其 `N_ITEM` 参数 —— 提高计数需要为该组中每个参数提供列表值。
- 带 `SYMBOL` 的 `PARAM` 包装会序列化为嵌套 TLV（`SYMBOL:4 | payload_length:4 | payload`）。如果模板声明了 `LENGTH`，序列化载荷必须与之匹配，否则生成失败。
- 8 字节流版本尾由流组装器添加，不在这里处理。
