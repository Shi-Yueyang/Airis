---
name: smartcore-plug
description: "根据 SmartCore_plug.xls 生成 SmartCore_plug.ctcs（SmartCore 车载应用配置数据文件）。将 Data 工作表中每行的取值按 size 列（字节数）大端序列化，末尾追加 CRC-32（poly 0x04C11DB7，init 0，非反射）与 64 字节零填充，输出可直接烧录的 .ctcs 二进制文件。用于 SmartCore plug 配置数据的生成、校验与联调核对。"
---

# SmartCore Plug 配置数据生成

将 SmartCore_plug.xls 中的 Data 工作表转换为 SmartCore_plug.ctcs 二进制配置文件。

## 前置条件

- Python 3.8+，依赖 `xlrd` 读取 .xls（BIFF8 格式）。
- 输入：`SmartCore_plug.xls`，至少包含 `Data` 工作表，列：A=字段名，B=size（字节数），C=Value；模板 xls 用于定义字段偏移和大小。
- 输出：`SmartCore_plug.ctcs`，2020 字节（1956 字节数据 + 4 字节 CRC + 64 字节零填充）。

## 功能流程

### 生成 .ctcs 文件
1. 读取 xls 的 Data 工作表，按行顺序序列化（详见 `references/format.md`）。
2. 运行 `scripts/gen_ctcs.py generate <input.xls> -o <output.ctcs>`。
3. 运行 `scripts/selftest_ctcs.py` 验证输出与参考样本字节一致。

### 查询配置项值
从 .ctcs 文件中查询指定配置项的当前值，需要模板 xls 定义字段的结构和偏移。
运行 `scripts/gen_ctcs.py query <input.ctcs> --field <field_name> -t <template.xls>`。

### 编辑/定制配置项值
修改 .ctcs 文件中指定配置项的值，自动更新 CRC 校验和，需要模板 xls 定义字段的偏移和大小。
运行 `scripts/gen_ctcs.py edit <input.ctcs> --field <field_name> --value <new_value> -t <template.xls> -o <output.ctcs>`。

## 格式要点（详见 references/format.md）

- 每行有正整数 size 的字段，按 size 列大端序列化。
- 值为 `0x...` 字符串时按十六进制解析；为数字时直接取整。
- 最后两行：`ID_CRC_DATA`（0xee8f，2 字节）+ `CRC_DATA`（4 字节，初始 0）。
- CRC-32（poly 0x04C11DB7，init 0，非反射，无 xorout）覆盖除最后 4 字节外的全部字节。
- 末尾追加 64 字节零填充。

## 不要做

- 不要修改 xls 中的字段顺序或 size 列——输出严格按行顺序序列化。
- 不要跳过任何有 size 的行（包括 ID_ 开头的标识符行）。
- 不要自行更换 CRC 算法或多项式——已与原始工具字节级核对一致。

## 验证纪律

- 生成后必须运行 `selftest_ctcs.py`，要求字节级一致（PASS）。
- 查询/编辑时必须提供模板 xls，否则无法确定字段的偏移和大小；编辑后会自动更新 CRC，确保文件完整性。
