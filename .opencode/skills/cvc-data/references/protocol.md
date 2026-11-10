# CVC 应用数据协议

本参考说明 cvc-data 脚本（本技能目录的 `scripts/`）使用的二进制帧格式。它是本技能唯一的规范格式文档——路由见 [SKILL.md](../SKILL.md)，命令与工作流见各阶段文档（`decode.md`、`generate.md`、`edit.md`）。

## 文件帧格式

所有整数均为大端：

```text
file = magic:4 | file_length:4 | field_1 | field_2 | ... | crc:4
field = symbol:4 | field_length:4 | body:field_length
```

- `file_length` 计入所有应用字段加末尾 CRC，但不计前 8 字节（`magic | file_length`）。
- CRC 为 CRC-32/ISO-HDLC（`zlib.crc32`），覆盖整个文件，去掉最后 4 个 CRC 字节。
- 字段相邻；没有分隔符或填充。
- 模板中带 `SYMBOL` 的 `PARAM` 包装把嵌套载荷封装在字段 body 内：`symbol:4 | body_length:4 | body`。可选 ATP 包装使用此帧格式；其 8 字节嵌套头计入外层字段 body 的偏移和长度。模板里的 `LENGTH` 描述嵌套 body，不含头部。
- 外层 magic 标识分发类别，不是文件名：

  | 类别（`DIST`） | Magic | 常规文件 |
  |---|---:|---|
  | DP | `0xABABABAB` | `ASW1.bin` |
  | LINE | `0xACACACAC` | `Config2.line1` |
  | TRAIN | `0xADADADAD` | `Config1.train` |

## 应用字段

每个字段由 `<ASW SYMBOL>` 与该字段 symbol 匹配的模板塑形。在参考文件中，字段顺序为先 ATP、后 SDMU：

| 功能 | 模板 | Symbol |
|---|---|---:|
| ATP | `ATPCfgTemplate.xml` | `0x66AA5599` |
| SDMU | `SDMUCfgTemplate.xml` | `0xA5A59696` |

对于每个文件，字段的二进制 body 从模板的 `<PARAMCLASS DIST="DP|LINE|TRAIN">` 中选择。生成器要求同时提供 ATP 和 SDMU 模板，并且无论 `-t` 参数的命令行顺序如何，始终按上述规范顺序输出字段。

`BSWCfgTemplate.xml` 不是这些文件的应用字段模板：它没有 `<ASW SYMBOL>`、`<PARAM>` 字节大小或字段 symbol，工具会跳过它并告警。

## 这些文件之外的流帧格式

完整的拼接应用流可能有一个 8 字节版本尾（`dp_version` 后接 `project_version`，大端）。这些按类拆分的文件不包含该尾；其生成属于流组装器。

## 参考回归尺寸

已知良好的参考数据集有以下字段 body 长度：

| 文件 | ATP body | SDMU body | 文件总计 |
|---|---:|---:|---:|
| `ASW1.bin` | 18 字节 | 14 字节 | 60 字节 |
| `Config2.line1` | 247 字节 | 35 字节 | 310 字节 |
| `Config1.train` | 110 字节 | 44 字节 | 182 字节 |

这些文件各有一个外层帧和一个 CRC。这些尺寸是有用的回归检查，但逐字节往返比较更强。
