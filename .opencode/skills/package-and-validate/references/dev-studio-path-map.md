# Dev Studio path map

本地包路径与 Dev Studio 草稿文件一一对应（导入或后续 files API 写入时同路径）：

| Package path | Dev Studio draft |
|--------------|------------------|
| `manifest.json` | project root `manifest.json` |
| `.opencode/**` | project `.opencode/**` |
| `.ark-user-config-defaults/**` | MCP 用户配置模板文件 |
| `data_schema.json` | 可选副本；与 `manifest.data_schema` 保持同步 |

当前主路径：写本地目录 / `.opapp.tgz` → 导入 Dev Studio。
