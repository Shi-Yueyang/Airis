---
name: package-and-validate
description: >-
  校验 Airis 应用包并构建 app_id-version.opapp.tgz。用于检查 manifest、listing、
  技能与 MCP 绑定是否符合提交就绪规则，或在改包后重新打包。也适用于用户提到
  “校验应用包 / 打包 / 生成 opapp / submit-ready / validate” 的场景。
---

# Package and Validate（Airis 本地开发技能）

## 适用范围

本技能只用于 **Airis 源树**的本地开发，是开发专用技能：

- 放在 `airis/.opencode/skills/package-and-validate/`，单独启动 Airis 时可直接使用。
- 打包脚本内置 `DEV_ONLY_SKILLS` 排除规则，本目录**不会**进入 `airis-<version>.opapp.tgz`。
- 不要把它当作应用运行期能力发布给终端用户。

## DoD 门禁

校验通过（`valid=true`）之前，不要声称应用包 **submit-ready**；失败时修复，或明确列出阻断错误。

说明：

- 本校验器是**提交就绪门禁**（listing、data/ui 绑定、MCP 对齐等），比平台“仅导入”更严。
- 导入 Dev Studio 后仍须平台校验/构建/审批；本地校验不替代审核。

## 独立运行

在 `airis` 根目录执行：

```powershell
python .\.opencode\skills\package-and-validate\scripts\validate_app_package.py .
python .\.opencode\skills\package-and-validate\scripts\build_opapp_tgz.py .
```

脚本也接受显式包路径，便于从其他目录调用：

```powershell
python <项目根>\.opencode\skills\package-and-validate\scripts\validate_app_package.py <项目根>
python <项目根>\.opencode\skills\package-and-validate\scripts\build_opapp_tgz.py <项目根>
```

产物默认写到包目录的上一级：`airis-<version>.opapp.tgz`。

## Checklist（每次执行）

结构：

- [ ] `manifest.json` + `.opencode/` 存在
- [ ] `app_id` ≠ `default`；版本号符合平台格式
- [ ] Listing 满足提交要求：name 2–40、subtitle、description_md ≥100、category、support_contact
- [ ] `chat_empty_state.cards` ≤4；每张卡有 title + prompt
- [ ] 若存在 `agent_ui`：`visible` 为唯一非空 runtime name；`labels` 值为非空字符串；Agent 实际名称由 Dev Studio/平台诊断
- [ ] 若存在 `a2a`：仅在明确要求公开时保留；Skill ID 唯一，模式仅 `text` / `file` / `data`
- [ ] 无 `node_modules`、锁文件、`.env`、真实密钥、`.casco`
- [ ] 若有数据：`data_schema.json` 与 `manifest.data_schema` 同步
- [ ] 若启用工作台：页面与 binding 能在 data_schema 中解析
- [ ] 若技能带 MCP：同级 `mcp.json` 含顶层 `mcpServers`；启用 `user_config` 时 `mcp_targets` 名称对齐
- [ ] 有技能 MCP 时 `opencode.json` 的 `plugin` 含 `oh-my-openagent@…`
- [ ] 除非 CLAWHUB 已就绪，不写 `manifest.skills`

当前 Airis 为场景 A，必须满足：

- [ ] 骨架完整，listing ≥100 字，至少 1 张 empty_state 卡片且带 prompt
- [ ] `.opencode/skills/<name>/SKILL.md` 存在且 `name` 与目录一致
- [ ] 没有半启用的 `user_config` 或空工作台默认入口
- [ ] 校验通过并构建 `.opapp.tgz`

## 打包白名单

`build_opapp_tgz.py` 只打包：

- `manifest.json`
- `data_schema.json`（存在时）
- `.opencode/**`（剔除 `node_modules`、`package.json`、锁文件、`__pycache__`/`.pyc`）
- `user_config.seed_dir`（启用时）

额外剔除：`.opencode/skills/package-and-validate/**`（见 `DEV_ONLY_SKILLS`）。README、`registration.md`、根目录脚本等不会进入发布包。

禁止用整根 `tar -czf .` 代替本脚本。

## 输出

报告以下内容：

- `valid` / `errors` / `warnings`
- tgz 路径与包内容摘要
- 下一步：导入 Dev Studio → 平台校验/构建 → 提交审批