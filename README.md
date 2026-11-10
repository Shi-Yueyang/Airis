# Airis 铁路测试数据智能体

- **app_id**: `airis`
- **版本**: 1.4.1
- **类型**: 对话型应用
- **用途**: 面向铁路产品研发与测试人员，用自然语言驱动测试数据的反解、生成、定点修改与校验。

## 项目结构

```text
.
├── manifest.json
├── README.md
└── .opencode/
    ├── opencode.json
    ├── agents/
    │   └── airis.md
    └── skills/
        ├── cvc-data/                 # 应用能力：CVC 数据反解 / 生成 / 定点修改
        │   ├── SKILL.md
        │   ├── decode.md
        │   ├── generate.md
        │   ├── edit.md
        │   ├── references/protocol.md
        │   └── scripts/
        │       ├── dump_cvc_data.py
        │       └── gen_cvc_data.py
        ├── tacn-rbc-data/            # 应用能力：TACN 车地无线报文生成 / 反解 / 定点修改 / 模拟器输入
        │   ├── SKILL.md
        │   ├── decode.md
        │   ├── generate.md
        │   ├── sim-xml.md
        │   ├── edit.md
        │   ├── references/
        │   │   ├── protocol.md
        │   │   └── rbc-simulator-input-xml.md
        │   └── scripts/
        │       ├── rbc_spec.py       # 报文定义 + 位打包引擎（CLI 共用）
        │       ├── gen_rbc_msg.py
        │       ├── dump_rbc_msg.py
        │       ├── sim_spec.py       # 模拟器 XML 行渲染与长度重算
        │       ├── gen_rbc_sim_xml.py
        │       ├── selftest_rbc_msg.py
        │       └── selftest_sim_xml.py
        ├── smartcore-plug/          # 应用能力：SmartCore_plug.xls → SmartCore_plug.ctcs
        │   ├── SKILL.md
        │   ├── references/format.md
        │   └── scripts/
        │       ├── gen_ctcs.py
        │       └── selftest_ctcs.py
        └── package-and-validate/     # 开发工具：校验 + 打包（不随发布包分发）
            ├── SKILL.md
            ├── references/dev-studio-path-map.md
            └── scripts/
                ├── validate_app_package.py
                ├── build_opapp_tgz.py
                └── package_lib.py
```

## 环境要求

- OpenCode
- Python 3：`cvc-data`、`tacn-rbc-data` 与打包校验脚本只依赖标准库；`smartcore-plug` 额外需要 `xlrd`（读 `.xls`）
- Windows 命令行建议先 `set PYTHONUTF8=1`，否则中文报错可能显示成乱码

## 启动

在项目根目录执行：

```powershell
opencode
```

启动后可使用 Airis 主 Agent、`cvc-data`、`tacn-rbc-data`、`smartcore-plug`，以及本地开发技能 `package-and-validate`。

## 应用能力

### cvc-data：CVC 应用数据文件

| 文件 | 类别 | 说明 |
|------|------|------|
| `ASW1.bin` | DP | 应用数据 |
| `Config2.line1` | LINE | 线路配置 |
| `Config1.train` | TRAIN | 列车配置 |

主要流程：

- 反解三件套并输出字段遍历 Markdown 报告，解释 CRC、越界和模板版本告警。
- 用 `--values` 命名空间化 JSON 从 ATP/SDMU 模板生成三件套，支持 `--set` 临时覆盖。
- 从现有数据捕获 values，只改指定键后重新生成，并核对差异是否只包含目标字段。
- 生成或修改后重新反解，要求 `crc=OK`、`walk=OK`。

### tacn-rbc-data：TACN 车地无线（OBS↔RBC）报文

报文结构内置（来源 `references/protocol.md`），不需要模板文件：

- 生成：按取值 JSON 输出 hex 报文串，覆盖地→车 M2/M3/M6/M8/M15/M16/M18/M24/M32/M34/M39/M41/M45，
  车→地 M129/M132/M136/M146/M147/M149/M150/M154~M159，P0~P80 信息包与 P44 内
  CTCS-51/54/80~84/131/132/136/150/151/152 用户包。
- 模拟器输入：把同一份取值 JSON 渲染成 RBC 模拟器的 `DataTable` XML（RBC→车，UTF-8 BOM，
  行序即线序，自动回填 `L_MESSAGE`/`L_PACKET`）；只支持模拟器分派表内的消息/信息包/用户包，
  生成后按 `rbc-simulator-input-xml.md` 第 7 节的长度基线校验。
- 反解：hex 文本或原始二进制 → Markdown 字段报告（起始位/位宽/取值/含义），并给出
  `L_MESSAGE`、包内 `L_PACKET`、位遍历闭合、填充位、组成规则的自洽结论。
- 定点修改：反解导出取值 → 只改目标键 → 重新生成 → 再反解并做键级差异对比。
- 生成门禁：取值 JSON 每个分组必须带 `intent`（确认消息/产物/包顺序/`confirmed=true`）与
  `provenance`（逐段来源 user/decoded/placeholder）；缺确认、包顺序不符、来源未标注或占位值
  未加 `--allow-placeholder` 时生成器 exit 1，不写任何文件。
- 生成侧硬校验：协议定长包、500 字节上限、必选包与组成表、方向、条件字段、取值越界、
  规则 1-9（同类型包不可重复、临时限速编号互异）。
- 自检：`scripts/selftest_rbc_msg.py` 提供 53 项可执行回归（含 17 个反例），
  覆盖全部消息/信息包/用户包的编解码往返与定长断言；`scripts/selftest_sim_xml.py`
  覆盖模拟器 XML 的长度基线与结构限制；`scripts/selftest_gate.py` 覆盖生成门禁的拒绝路径
  与 `--values-out` 回喂。

> RBC 报文没有 CRC，仓库里也没有真机报文样本；"自洽通过"只证明长度、包长、位遍历与组成
> 自洽，不证明 RBC 侧业务语义。协议里的冲突与实现取舍见 `references/protocol.md` 附录 B/C。
> 模拟器 XML 的 P15 长度按模拟器模板计算（条件字段不打包），与 hex 生成器当前 P15 口径可能
> 不同；模拟器输入以 `sim-xml.md` 为准。

### smartcore-plug：SmartCore 车载应用配置（`SmartCore_plug.xls` → `SmartCore_plug.ctcs`）

- 生成：把 xls 的 Data 工作表每行按 `size` 列（字节数）大端序列化，末尾追加 CRC-32
  （poly 0x04C11DB7，init 0，非反射）与 64 字节零填充，输出 2020 字节可烧录的 `.ctcs` 文件。
- 查询配置：按模板 xls 的字段结构，读取 `.ctcs` 中指定配置项的当前值。
- 编辑定制：修改 `.ctcs` 中指定配置项，自动重算 CRC 并输出新文件。
- 自检：`scripts/selftest_ctcs.py` 要求生成结果与参考样本字节级一致；无参考样本时
  校验 CRC 值与原始工具日志一致。
- 验证边界：格式基于单个参考样本逆向得出，64 字节零填充为观察到的固定尾部；模板结构
  变化时需重新核对 `references/format.md`。

## 添加新技能

1. 在 `.opencode/skills/<skill-name>/` 下创建 `SKILL.md`，`name` 与目录名保持一致。
2. 在 frontmatter 的 `description` 中写清触发场景关键词，便于主 Agent 发现。
3. 需要脚本时放在技能目录的 `scripts/`，参考文档放 `references/`，并在 `SKILL.md` 中说明何时读取。
4. 若技能需要外部 MCP，再添加同级 `mcp.json`，并同步 `manifest.user_config` / `opencode.json` 的插件声明。
5. 修改后重新校验并打包，递增版本号。

## 校验与打包

在项目根目录执行：

```powershell
$env:PYTHONUTF8=1
python .\.opencode\skills\package-and-validate\scripts\validate_app_package.py .
python .\.opencode\skills\package-and-validate\scripts\build_opapp_tgz.py .
```

产物默认写到项目目录的上一级：

```text
airis-1.4.1.opapp.tgz
```

`package-and-validate` 是开发专用技能，打包时会被自动排除，不会出现在 `.opapp.tgz` 中。包内只包含 `manifest.json`、`.opencode/` 运行配置和应用技能。

## 发布

1. 将 `.opapp.tgz` 导入 Dev Studio。
2. 在平台完成校验与构建。
3. 提交审批。本地校验通过只代表提交就绪门禁通过，不替代平台审核。
