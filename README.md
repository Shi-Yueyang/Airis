# Airis 铁路测试数据智能体

- **app_id**: `airis`
- **版本**: 1.2.0
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
- Python 3（`cvc-data` 与打包校验脚本只依赖标准库）

## 启动

在项目根目录执行：

```powershell
opencode
```

启动后可使用 Airis 主 Agent、`cvc-data`，以及本地开发技能 `package-and-validate`。

## 应用能力

`cvc-data` 处理 CVC 应用数据文件：

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

## 添加新技能

1. 在 `.opencode/skills/<skill-name>/` 下创建 `SKILL.md`，`name` 与目录名保持一致。
2. 在 frontmatter 的 `description` 中写清触发场景关键词，便于主 Agent 发现。
3. 需要脚本时放在技能目录的 `scripts/`，参考文档放 `references/`，并在 `SKILL.md` 中说明何时读取。
4. 若技能需要外部 MCP，再添加同级 `mcp.json`，并同步 `manifest.user_config` / `opencode.json` 的插件声明。
5. 修改后重新校验并打包，递增版本号。

## 校验与打包

在项目根目录执行：

```powershell
python .\.opencode\skills\package-and-validate\scripts\validate_app_package.py .
python .\.opencode\skills\package-and-validate\scripts\build_opapp_tgz.py .
```

产物默认写到项目目录的上一级：

```text
airis-1.2.0.opapp.tgz
```

`package-and-validate` 是开发专用技能，打包时会被自动排除，不会出现在 `.opapp.tgz` 中。包内只包含 `manifest.json`、`.opencode/` 运行配置和应用技能。

## 发布

1. 将 `.opapp.tgz` 导入 Dev Studio。
2. 在平台完成校验与构建。
3. 提交审批。本地校验通过只代表提交就绪门禁通过，不替代平台审核。