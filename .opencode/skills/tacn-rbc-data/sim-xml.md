# 生成模拟器输入 — RBC 模拟器 DataTable XML

把与 `generate.md` 相同的取值 JSON 渲染成 RBC 模拟器的 `DataTable` XML（RBC→车）。这是另一条产物：hex 报文串给测试仪器/监视工具，XML 给 RBC 模拟器加载。文件格式以本技能目录的 `references/rbc-simulator-input-xml.md` 为准。

## 格式参考

`references/rbc-simulator-input-xml.md` 定义了根元素、`<data>` 的四个必填属性、行序即线序、`L_MESSAGE` 按字节/`L_PACKET` 按位、条件行与迭代展开、P44 嵌套、IP 与文本的特殊取值，以及模拟器 C# 分派表支持的消息/信息包/用户包。

## 必需输入

- Python 3（仅标准库）。Windows PowerShell 先执行 `$env:PYTHONUTF8=1`。
- 一份取值 JSON（`--values`，**每次运行都必须给**），形状与 `generate.md` 完全相同：`header` + `packets`，
  外加每个分组的 `intent` + `provenance` 门禁块（`references/gate.md`）。字段名写法（`NAME(k)`、`NAME#n`、
  `NID_LRBG`、双 IP、文本）也相同。
- 一个可写的输出目录（`-o`，默认当前目录）。默认文件名是 `dataTableM<消息号>.xml`（模拟器消息编辑器按这个名字自动加载）；同名文件会被覆盖。
- 同一份取值里的报文必须是 RBC→车消息，且信息包/用户包在模拟器分派表里（见 `--list`）。

## 规则

1. **只支持 RBC→车**：M2/M3/M6/M8/M15/M16/M18/M24/M32/M34/M39/M41/M45。M129/M132/M136 等车→地消息不是模拟器输入；需要 hex 报文串请用 `generate.md`。
2. **信息包/用户包受两层约束**：先满足 `references/protocol.md` 的组成表，再满足模拟器的 C# 分派表。模拟器不支持的信息包/用户包会在编码前被拒绝，不会写出半成品。
3. **行序就是线序**：字段顺序、位宽和条件行位置由模拟器模板决定；不要按名字重排、合并或删除行。条件字段（`Q_SECTIONTIMER`、`Q_ENDTIMER`、`Q_DANGERPOINT`、`Q_OVERLAP`、`Q_NEWCOUNTRY`、`Q_CMDTYPE` 等）即使不打包，也必须保留行。
4. **迭代按计数展开**：计数 `N` 就写 `N` 组 `(0)…(N-1)` 行；`N=0` 时整组不写。CTCS-80 的 `GROUP_NID_ENGINE(k)` 行数必须等于 `N_TRAINNUM`。P58 的 `N_ITER` 只能为 0；CTCS-132 的 `N_SIGSTACNT` 只能为 0；P68 的 `Q_TRACKINIT` 只能为 0。
5. **长度按模拟器口径**：`L_MESSAGE` 是字节数（`ceil(总位数/8)`）；`P##_L_PACKET` 是本包从 `NID_PACKET` 起的位数；内层 `L_PACKET` 从 `NID_XUSER` 起算；外层 `P44_L_PACKET = 23 + 内层 L_PACKET`。生成器会按模拟器的打包路径重算并回填，不用手工算。
6. **特殊取值**：普通字段写无符号十进制；双 IP 写八段点分十进制（`A.B.C.D.E.F.G.H`）；P72 的 `X_TEXT(L_TEXT)` 行 `bits` 固定写 8，实际长度由 `L_TEXT` 决定，`L_TEXT` 是**编码后的字节数**。
7. **文本编码**：默认按模拟器的 GB18030；模拟器文本设置为 UTF-16BE 时用 `--p72-charset utf-16-be`。XML 里的 `L_TEXT` 一律是编码后的字节数；取值 JSON 仍按协议实现的规则写（GB18030 为字节数，UTF-16 为字符数），生成器会换算成字节数。
8. **输出格式**：UTF-8 with BOM、`<?xml version="1.0" encoding="utf-8"?>`、`<DataTable>`；每行四个属性齐全，第 1 行必须是数值 `NID_MESSAGE`。写完后生成器会读回校验结构、属性和取值位宽。模拟器按**当前工作目录**的 `dataTableM<n>.xml` 自动加载；输出到别的目录时，把文件放到模拟器的工作目录再打开。

## 取值 JSON 格式

与 `generate.md` 相同；额外支持在分组里用 `"file"` 或 `"filename"` 指定输出文件名（例如 `"file": "523-M3.xml"`）。不指定时用 `dataTableM<消息号>.xml`，同类型多条会依次加 `_2`、`_3`。

```json
{
  "m24_c80": {
    "message": "M24",
    "intent": {"message": "M24", "target": "sim-xml",
               "packets": ["P44/CTCS-80"], "confirmed": true},
    "provenance": {"header": "user", "P44/CTCS-80": "user"},
    "header": {"T_TRAIN": 3277070, "M_ACK": 1, "NID_C": 1018, "NID_BG": 523},
    "packets": [
      {"packet": "P44", "user": "CTCS-80", "fields": {
        "GROUP_ID": 2, "N_TRAINNUM": 2, "Group_NID_ENGINE": [90, 91],
        "NID_ENGINE_PRE": 90,
        "M_IP_PRE": "172.16.27.100.172.16.28.100"}}
    ]
  }
}
```

- 方向由 `message` 决定；帧头字段仍是 `T_TRAIN`、`M_ACK`、`NID_LRBG`/`NID_C`+`NID_BG`。
- 信息包数组顺序即空口顺序；P44 用 `user` 指定 CTCS 用户包。
- `intent.target` 要写 `sim-xml`（hex 与 XML 都要生成时写 `both`）；`intent.packets` 必须与
  实际包顺序一致。门禁块格式见 `references/gate.md`，含 `placeholder` 时加 `--allow-placeholder`。
- 字段名冲突、迭代列表、默认值回退的规则见 `generate.md`；本流程不重复定义。

## 工作流

1. **准备取值** — 用 `gen_rbc_msg.py --describe <消息号>` 看报文结构，按 `SKILL.md` 的确认单收齐取值并写 `intent` + `provenance`（`references/gate.md`），再写 `header` + `packets`。先跑 `--list` 确认消息/信息包/用户包在模拟器支持范围内。
2. **生成** — 生成器是 `scripts/gen_rbc_sim_xml.py`；下文的 `<skill-dir>` 指本技能目录，输出路径相对当前工作目录解析。

   ```sh
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --list
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json -o out/
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json --message m24_c80 -v
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json --auto-length -o out/
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json \
     --set m24_c80.P44.CTCS-80.N_TRAINNUM=2
   python <skill-dir>/scripts/gen_rbc_sim_xml.py --values values.json --p72-charset utf-16-be
   ```

   | 选项 | 用途 |
   |---|---|
   | `--list` | 列出模拟器支持的报文/信息包/用户包，不生成文件 |
   | `--values PATH` | 取值 JSON（生成时必填） |
   | `-o DIR` | XML 输出目录（默认当前目录） |
   | `--message m24_c80` | 只生成指定分组（可重复；按顶层键匹配，不是消息号） |
   | `--set 路径=值` | 临时覆盖，写法与 `gen_rbc_msg.py` 相同（首段是顶层键）；被覆盖字段自动记为 `user` |
   | `--allow-placeholder` | 允许 `provenance` 标为 `placeholder` 的占位/示例值；不加则拒绝生成 |
   | `--auto-length` | M3/M24 的 `L_MESSAGE` 与所有 `*L_PACKET` 写 `自动计算不填`；简单消息仍写数字 |
   | `--p72-charset gb18030\|utf-16-be` | P72 文本编码（默认 GB18030） |
   | `-v` | 打印每一行 XML 的变量/位宽/取值 |

3. **校验** — 生成输出不是证据：
   - 生成器已读回 XML，检查根元素、四个属性、第 1 行 `NID_MESSAGE`、取值位宽和行数；失败会直接报错，不会留下未校验的文件。
   - 对照参考长度：`M24 + P44/CTCS-80（N_TRAINNUM=2）` 应为 294 bit / 37 字节（外层 219、内层 196）；`M3 + P15+P21+P27+P5+P44/CTCS-150-TACN` 应为 653 bit / 82 字节（P15 66、P21 78、P27 86、P5 69、C150 279）。完整基线跑 `python <skill-dir>/scripts/selftest_sim_xml.py`。
   - 在模拟器里加载并发送一次，核对它实际发出的字节/长度；本仓库没有模拟器可执行文件，这一步只能在装有 RBC 模拟器的环境完成。
4. **报告** — 写清取值文件、输出文件、消息号与信息包、`L_MESSAGE`/各包长度、XML 行数、回退字段、
   `审计` 行与占位字段清单、告警，以及没有执行的检查（尤其是“没有在模拟器里实际加载/发送”）。

## 失败处理

| 报错 | 原因 | 处理 |
|---|---|---|
| `缺少 intent` / `intent.confirmed 不是 true` | 门禁块没写或确认单没完成 | 按 `references/gate.md` 补；不得绕过 |
| `intent.packets 声明 …，实际包顺序是 …` | 组成与声明不一致 | 先确认包顺序，再改 `intent.packets` |
| `这份取值标的是 hex，不能用来生成 sim-xml` | `target` 不匹配 | 改成 `sim-xml` 或 `both` |
| `provenance 缺少 …` / `有 N 个占位字段` | 来源未标注 / 占位未授权 | 补来源；占位加 `--allow-placeholder` |
| `RBC 模拟器只支持 RBC→车消息：…；M129 不是模拟器输入` | 取值里混入了车→地消息 | 车→地报文用 `generate.md` 生成 hex，不要给模拟器 |
| `RBC 模拟器不支持 P44/CTCS-51` | 模拟器只有 CTCS-51 模板、没有分派分支 | 去掉该用户包；或改用 hex 报文 |
| `RBC 模拟器不支持 P%d` | 信息包不在模拟器分派表 | 按 `--list` 换包；模拟器不能靠 XML 定义新包 |
| `N_SIGSTACNT 必须为 0` | 模拟器不打包 CTCS-132 的信号状态迭代组 | 把 `N_SIGSTACNT` 设为 0，只保留道岔状态 |
| `P68 Q_TRACKINIT=1` | 模拟器要求 `Q_TRACKINIT=0`，否则后续行会被误读 | 设为 0；国内 ATP 也不接受 1 |
| `文本按 … 编码得 N 字节，与 L_TEXT=… 不符` | `L_TEXT` 与实际编码长度不一致 | GB18030 下写字节数；UTF-16BE 下协议实现写字符数，生成 XML 时会自动换算成字节数 |
| `第 N 行 … 超出 X bit` | 取值超过字段位宽 | 修正取值；模拟器不会做范围检查，生成器会提前拦住 |
| `缺必选信息包` / `不在 … 的信息包组成里` | 报文组成不符合 `protocol.md` | 按 `generate.md` 的组成规则补包或换消息 |
| `输出文件名重复` | 多个分组用了同一个 `file`/`filename` | 改成不同文件名，或删除自定义名让默认名自动加序号 |
| `XML 读回失败` / `行数不符` | 写盘或编码异常 | 保留现场并报告；不要手工改 XML 绕过校验 |

## 限制

- 模拟器的报文/信息包/用户包分派是 C# 硬编码的，XML 只能填值，不能定义新包；`--list` 之外的组合不要尝试。
- M27/M28/M33 与 CTCS-64 不在本仓库的协议定义里，本流程暂不支持；它们的结构可查 `references/rbc-simulator-input-xml.md` 附录 A，但需要先补协议定义。
- P15 的长度按模拟器模板计算（`Q_ENDTIMER`/`Q_DANGERPOINT`/`Q_OVERLAP` 后的字段为条件字段）。这与 `gen_rbc_msg.py` 当前协议实现的 P15 恒存在口径不同；同一份取值生成的 hex 与 XML 在 P15 的 `L_PACKET` 上可能不一致，模拟器输入以本流程为准。
- 模拟器不打包 CTCS-132 的信号状态迭代组；`N_SIGSTACNT` 只能为 0。
- 仓库里没有 RBC 模拟器可执行文件；XML 结构校验和长度基线只能证明“文件符合本文档描述的格式”，最终仍要在模拟器里加载/发送一次。
- 默认的 `dataTableM<n>.xml` 只对单条同类型报文能自动加载；多条同类型报文请用 `file`/`filename` 区分，否则 `_2`/`_3` 文件不会被消息编辑器按名字自动加载。
