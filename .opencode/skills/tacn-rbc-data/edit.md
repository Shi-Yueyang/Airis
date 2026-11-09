# 定点修改 — 只改目标字段，其余原样保留

已有报文是唯一事实来源：除了要求改的字段，其它一切都要**经过验证**地保持不变。
不需要第三个脚本：这就是"反解 → 改取值 → 重新生成 → 再反解对比"的组合。

开始前先对齐：要改哪些字段、改成什么值、产物目录与文件名、是否允许覆盖已有文件。
用户没说清就先问，清单见 `SKILL.md` 的「需要用户澄清的要点」。

## 规则

1. 永远不要覆盖或改写输入的 hex/二进制文件；中间产物放临时目录。
2. 改之前先完整反解一次。有 `L_MESSAGE`/`L_PACKET` 不一致、`未解析位数`、`未知信息包`
   等错误时报文本身不可靠，**不要**在它上面做修改。
3. 只改取值 JSON 里的目标键；不要顺手"修正"别的字段，也不要为了通过校验去改脚本定义。
4. 改完必须重新生成并再反解，用两次导出做**键级差异**对比，差异必须只有目标字段。
5. 需要改迭代计数（`N_ITER`）时，要同步给出该组每一轮的取值；计数变化本身也会出现在差异里。

## 流程

```sh
# 1. 反解原报文，导出完整取值（包含所有已解出字段，含协议默认值）
python <skill-dir>/scripts/dump_rbc_msg.py orig.hex --values-out before.json -o before_report.md

# 2. 在 before.json 里只改目标键，另存为 edited.json（保留原文件）
#    例：把 M3 的 L_ENDSECTION 从 3000 改成 2500
#        "L_ENDSECTION": 3000  ->  "L_ENDSECTION": 2500

# 3. 重新生成
python <skill-dir>/scripts/gen_rbc_msg.py --values edited.json -o new/

# 4. 再反解一次并导出
python <skill-dir>/scripts/dump_rbc_msg.py new/M3.hex --values-out after.json -o after_report.md

# 5. 对比 before.json 与 after.json
```

第 5 步的对比脚本（贴进 `python -` 即可）：

```python
import json

def flat(doc, prefix=""):
    out = {}
    for key, value in doc.items():
        if isinstance(value, dict):
            out.update(flat(value, prefix + key + "."))
        elif isinstance(value, list):
            out[prefix + key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            out[prefix + key] = value
    return out

before = flat(json.load(open("before.json", encoding="utf-8")))
after = flat(json.load(open("after.json", encoding="utf-8")))
for key in sorted(set(before) | set(after)):
    if before.get(key) != after.get(key):
        print("%-60s %r -> %r" % (key, before.get(key), after.get(key)))
```

输出里**只应该出现**你改过的键。出现别的键就按失败处理（见下）。

## 校验清单

- 反解（原报文）：`L_MESSAGE` 一致、每个包 `L_PACKET` 一致、位遍历闭合、无告警。
- 生成：退出码 0，且没有新增回退字段（`回退 N 字段` 与原始报文导出的取值一致）。
- 反解（新报文）：与第 1 步同样的检查全部通过。
- 差异：键级 diff 恰好等于目标字段；没有连带变化。
- 无改动重生成（可选但推荐）：用 `before.json` 直接生成，输出必须与原报文**逐字节相同**。
  这一步能立刻暴露"取值没导全"或"默认值不稳定"。

## 失败处理

| 现象 | 原因 | 处理 |
|---|---|---|
| 原报文反解就有错误 | 报文被截断/来自别的版本/缺定义 | 先解决反解问题，不要在坏数据上改 |
| 生成时报"没有被消费的键" | 键名拼错，或这个字段不在该包里 | 按 `decode.md` 报告里的字段名改 |
| 生成时报定长不符（P3/P58/P65/P4/CTCS-136） | 改了会影响包长的计数 | 这些包是定长的，计数不能改 |
| 差异里多出 `N_ITER` 或列表长度 | 改了迭代轮数 | 正常，但要确认每一轮都给齐了 |
| 差异里多出没改过的字段 | 取值没导全/默认值不一致/条件字段联动 | 重新完整反解后重做，不要手工补 |
| 无改动重生成与原报文不同 | 原报文里有实现未覆盖的位（例如条件字段写法不同） | 先补 `references/protocol.md` 附录 C 与脚本定义，再回来改 |

## 边界

- 只能修改"已经能完整反解"的报文。缺定义的部分不能保留，也就不能安全修改。
- 一次修改后生成的报文，其 `L_MESSAGE`/`L_PACKET` 会被重新计算并回填；如果目标就是改长度，
  这属于预期变化，请在报告里说明。
- 报文没有 CRC，"改完能生成"不构成正确性证据；差异对比 + 重新反解自洽才是。
