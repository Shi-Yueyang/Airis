# AGENTS.md

Airis 是一个 OpenCode **应用包**（对话型智能体），不是可执行程序。唯一交付物是 `airis-<version>.opapp.tgz`，内容只有 `manifest.json` + `.opencode/`。仓库没有构建系统、没有测试框架、没有 CI —— 唯一的机器校验是下面的打包校验脚本。

## 真实边界

- `manifest.json` — 包的唯一元数据源；`app_id` + `version` 决定产物文件名。
- `.opencode/opencode.json` — 故意只留 `$schema`。只有某个技能带 `mcp.json` 时才需要加 `plugin: ["oh-my-openagent@…"]`，别顺手往里塞配置。
- `.opencode/skills/<name>/` — 一个技能一个目录；`SKILL.md` frontmatter 的 `name` **必须等于目录名**，否则 OpenCode 不会加载它，而校验器不会报错（见下）。
- `.opencode/agents/airis.md` — 主 Agent 提示词，末尾「当前版本」小节列出已启用技能，是能力声明的第二处真相源。
- `README.md` / `registration.md` — 不进发布包。`registration.md` 是参赛报名表，不要当技术文档维护。

## 改动后的收尾顺序（在仓库根目录执行）

```powershell
$env:PYTHONUTF8=1        # 不设则脚本输出里的中文报错变成乱码
python .\.opencode\skills\package-and-validate\scripts\validate_app_package.py .
python .\.opencode\skills\package-and-validate\scripts\build_opapp_tgz.py .
```

- `valid=true` 之前不要声称 submit-ready；`build` 在校验失败时直接 exit 1 且不产出。
- 产物写到仓库的**上一级目录**（`C:\casco\`），不在仓库内；找不到 tgz 先往上级看。
- 版本号要手动递增 `manifest.json.version`，必须 `MAJOR.MINOR.PATCH`；脚本不会自动改。
- 禁止用 `tar -czf` 整目录代替脚本。白名单和剔除逻辑在 `package_lib.py`：`DEV_ONLY_SKILLS` 会把 `package-and-validate` 排除出发布包，README / registration / 根目录文件也都不进包。

## 新增或启用一个技能时，四处必须同步

`manifest.json`（`listing` + `chat_empty_state.cards`）、`.opencode/agents/airis.md` 的能力说明、`README.md` 的结构图与能力表、`.opencode/skills/<name>/SKILL.md`。只建目录不算启用。

## 当前已知的坑

- `tacn-rbc-data` 已接线：`SKILL.md` + `decode.md` / `generate.md` / `edit.md` + `references/protocol.md`
  （含附录 B 源文档歧义、附录 C 编解码约定）+ `scripts/` 四个文件（`rbc_spec.py` 是共享的报文定义与位打包引擎）。
- RBC 报文没有 CRC，仓库里也没有真机样本：`selftest_rbc_msg.py`（53 项）只能证明长度/包长/位遍历/组成自洽。
  改动 `rbc_spec.py` 后先跑它，再跑反解报告核对，不要只看"生成成功"。
- `agents/airis.md` 现在只把平台配置、应答器轨旁报文列为未启用（TACN RBC 已启用），改动时别把两边写反。

## 校验器会阻断的硬规则

- `listing`：name 2–40 字、subtitle 非空且 ≤120 字、`description_md` ≥100 字、`category`、`support_contact` 必填。
- `chat_empty_state.cards` ≤4，每张卡必须有 `title` + `prompt`。
- `agent_ui.visible` 必须是非空字符串数组且不能重复，`agent_ui.labels.<name>` 的值必须是非空字符串（不限制只能列一个 Agent）。
- `node_modules` / `.casco` 只出 **warning**，构建脚本会主动剔除（`STRIP_HINTS`），不会阻断；完整清单见 `package-and-validate/SKILL.md`。

## Python 脚本必须兼容 3.8

本机是 Python 3.8.10（`scripts/__pycache__` 是 `cpython-38`）。脚本只用标准库；需要 `list[str]` / `dict[str, Any]` 这类注解时加 `from __future__ import annotations`（`package-and-validate/scripts` 这样做）；不要用 `match`，也不要在运行时求值的 `X | Y`。`cvc-data/scripts` 两个脚本完全不写注解，改它们时保持这个风格。

## CVC 数据任务

先加载 `cvc-data` 技能并按 `SKILL.md` 的路由表读 `decode.md` / `generate.md` / `edit.md`，不要凭记忆拼参数：`--values` 每次必填（裸模板默认值生成会被拒绝）、ATP 与 SDMU 模板必须同时给（`-t` 顺序无关，按 `<ASW SYMBOL>` 匹配）、生成目录会覆盖同名三件套且每次都写全部三个文件、生成后必须用同一组模板重新反解并要求 `crc=OK` 且 `walk=OK` 才能说完成。退出码为 0 不等于数据正确。

## TACN RBC 报文任务

先加载 `tacn-rbc-data` 技能并按 `SKILL.md` 的路由表读 `decode.md` / `generate.md` / `edit.md`，不要凭记忆拼位定义：报文结构只以 `references/protocol.md` 为准（脚本常量在 `scripts/rbc_spec.py`），`--values` 必填、`--set` 只做临时覆盖、生成后必须用 `dump_rbc_msg.py` 反解回来核对（`L_MESSAGE`、每包 `L_PACKET`、位遍历闭合、组成校验），定点修改必须做两次导出的键级差异。改 `rbc_spec.py` 后先跑 `selftest_rbc_msg.py`。没有真机样本时不要声称与 RBC 侧字节一致。

## 语言

面向平台与用户的文本（`manifest.json`、README、agent 提示词、脚本报错）用简体中文；`cvc-data` 的技能文档用英文，`tacn-rbc-data` 的技能文档用中文（`references/protocol.md` 本身是中文协议摘录）。改文件时跟随该文件已有语言，不要混译。
