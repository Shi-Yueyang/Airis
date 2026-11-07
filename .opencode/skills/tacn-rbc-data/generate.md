# 生成 — 从取值 JSON 产出 hex 报文

把"一条报文"写成一份取值 JSON，脚本按 `references/protocol.md` 的位定义打包，输出 hex 文本。
报文结构内置，没有模板文件；要生成新报文只需给值。

## 开始前先对齐（缺失就问）

生成前先确认这几项，缺什么问什么，不要替用户编业务值：

1. **报文与数量**：消息号、单条还是多条、是否含信息包/用户包。
2. **字段取值**：`T_TRAIN`、`NID_ENGINE`（车→地）或 `M_ACK`/`NID_LRBG`（地→车），
   以及必选包的关键字段。`--describe` 骨架里的值是示例，**不能原样交付**。
3. **输出格式**：`--hex-style plain|spaced|lines`，是否需要 `dump_rbc_msg.py` 报告。
4. **存放位置**：输出目录，尽量给绝对路径。
5. **文件名**：默认顶层键 → `<键名>.hex`；要别的名字就改顶层键，并用 `"message"` 指定消息号。
6. **是否覆盖**：目标目录已有同名文件时能否覆盖。

完整清单见 `SKILL.md` 的「先问清楚，再动手」。用户说"你看着办"时的默认：plain hex、
系统临时目录、文件名沿用 `<键名>.hex`、不覆盖已有文件，并在交付说明里写明这些选择。

## 输入

- Python 3（标准库）。
- 一份取值 JSON（`--values`，生成时必填）：顶层每个键是一条报文，键名就是输出文件名；
  只查结构用 `--describe M155`，不需要 JSON。
- 可写输出目录（`-o`，默认当前目录）；同名文件会被覆盖。生成前先把目录和文件名跟用户
  对齐，并检查目标文件是否已存在。

## 取值 JSON 的形状

```json
{
  "M3": {
    "header": {"T_TRAIN": 34655, "M_ACK": 1, "NID_LRBG": 16681259},
    "packets": [
      {"packet": "P15", "fields": {"Q_DIR": 1, "Q_SCALE": 1, "L_ENDSECTION": 3000,
                                   "V_RELEASEDP": 127}},
      {"packet": "P21", "fields": {"Q_SCALE": 1, "D_GRADIENT#1": 0, "Q_GDIR#1": 1,
                                   "G_A#1": 1, "N_ITER": 1, "D_GRADIENT(k)": 3000,
                                   "Q_GDIR(k)": 1, "G_A(k)": 255}},
      {"packet": "P44", "user": "CTCS-150",
       "fields": {"Q_EOATYPE": 0, "NID_ENGINE": 90, "NID_OPERATIONAL": 22,
                  "V_TRAIN": 50, "Q_DIR_HANDLE": 1, "Q_TRACTION_HANDLE": 1,
                  "M_HEAD_PRESSURE": 200, "M_TAIL_PRESSURE": 200,
                  "KILOMETER_POST": 200}}
    ]
  },
  "M24_523": {
    "message": "M24",
    "header": {"T_TRAIN": 3277070, "M_ACK": 1, "NID_LRBG": 16681259},
    "packets": [
      {"packet": "P44", "user": "CTCS-80",
       "fields": {"GROUP_ID": 2, "N_TRAINNUM": 2, "Group_NID_ENGINE": [90, 91],
                  "NID_ENGINE_PRE": 90,
                  "M_IP_PRE": "172.16.27.100.172.16.28.100"}}
    ]
  }
}
```

- 顶层键生成 `<键名>.hex`；想固定文件名又不想用消息号当名字，就在分组里写 `"message": "M24"`。
- `packets` 是**数组**：顺序即空口排列顺序；同一条报文可以有多个 P65/P66/P44。
- 方向由消息号决定：M2/M3/…/M45 是地→车，M129/…/M159 是车→地。帧头字段因此不同
  （地→车是 `M_ACK+NID_LRBG`，车→地是 `NID_ENGINE`），脚本按消息自动处理。
- 每条报文都有 `header`；预定义变量（M2 的 `Q_SCALE/D_SR`、M15 的 `NID_EM` 等）也写在
  `header` 里，因为它们在信息包之前。

## 最小样例（三类消息）

先用 `gen_rbc_msg.py --describe M155` 看结构，再套下面三类骨架。示例 hex 是本实现的
自测基线，**不是真机样本**。

**1）纯帧头：M155**（车→地，10 字节，无信息包）

```json
{"M155":{"message":"M155","header":{"T_TRAIN":34655,"NID_ENGINE":90},"packets":[]}}
```

```
9B02800021D7C00016BF
```

**2）帧头 + 预定义变量：M16**（地→车，10 字节，无信息包）

```json
{"M16":{"message":"M16","header":{"T_TRAIN":34655,"M_ACK":1,
                                  "NID_LRBG":16681259,"NID_EM":0},"packets":[]}}
```

```
1002800021D7FFD12561
```

**3）帧头 + 必选包：M149**（车→地，P0 或 P1 必选；下面用 P0）

```json
{"M149":{"message":"M149","header":{"T_TRAIN":34655,"NID_ENGINE":90},
  "packets":[{"packet":"P0","fields":{
    "Q_SCALE":1,"NID_LRBG":16681259,"D_LRBG":100,
    "Q_DIRLRBG":1,"Q_DLRBG":1,"L_DOUBTOVER":5,"L_DOUBTUNDER":5,
    "Q_LENGTH":0,"V_TRAIN":50,"Q_DIRTRAIN":1,"M_MODE":3,"M_LEVEL":3}}]}}
```

```
9506000021D7C000168000E4FF449580645000A0014649BF
```

注意方向和帧头字段：地→车是 `M_ACK + NID_LRBG`，车→地是 `NID_ENGINE`；`--describe`
会直接标出来，不要混用。上面三个 hex 已用 `dump_rbc_msg.py` 反解核对（自洽通过）。

## 字段名怎么写

| 写法 | 用途 | 例子 |
|---|---|---|
| `NAME` | 普通字段 | `L_ENDSECTION` |
| `NAME(k)` / `NAME(k,m)` / `NAME(i)(j)` | 迭代组里的字段，括号下标个数=迭代层数 | `G_A(k)`、`NC_DIFF(k,m)`、`NID_TO(i)(j)` |
| `NAME#n` | 同名字段按声明顺序第 n 个 | `T_TRAIN#2`（M8 的回显）、`Q_DIR#2`（P44 内层头） |
| `NID_LRBG` / `NID_PRVBG` | 24 bit 复合键，自动拆成 `NID_C`+`NID_BG` | `"NID_LRBG": 16681259` |

**同名字段的坑**：P21/P27/P80/P68 的首组字段和迭代组字段同名。`D_GRADIENT` 这种裸名会给
两处同一值，脚本会提示；要分别赋值就写 `D_GRADIENT#1`（首组）+ `D_GRADIENT(k)`（迭代组）。
P41 的 `M_LEVELTR`、P72 的 `M_MODETEXTDISPLAY`、P11 的两个 `N_ITER` 同理。

## 取值怎么写

| 类型 | 写法 |
|---|---|
| 整数 | `34655`，或 `0x875F` |
| 迭代组 | 列表（下标=轮次，用不到的位置写 `null`），或标量广播到每一轮 |
| 变长数组 | 列表，长度必须等于对应计数（`N_ITER`/`N_TRAINNUM` 等） |
| 双 IP（64 bit） | `"172.16.27.100.172.16.28.100"`（两段 IPv4，高位在前） |
| P72 文本 | 字符串；`L_TEXT` 在 UTF-16 下写字符个数，GB18030 下写字节数 |
| CTCS-51 数据块 | hex 串，如 `"DEADBEEF01"` |

迭代计数（`N_ITER`）必须给：脚本不会从列表长度反推，也不允许"少给一轮"——计数与列表长度
不符会直接失败，并指出是哪一帧、哪一轮。

## 默认值与回退

优先级：显式取值 → 协议默认值（`protocol.md` 的"取值"列）→ 失败。

- 回落次数会在结尾打印：`提示: 共 N 个字段没有在 values 里给值…`。`-v` 列出每个字段的
  取值来源（`[协议默认]` / `[字段名]`），交付前扫一眼这些来源。
- **没有默认值的字段必须给**，否则失败并指出字段（例如 `L_ENDSECTION`、`D_LRBG`、
  `M_ERROR`、`V_STATIC`）。
- `Q_SCALE` 协议没有默认值，本实现按 1 m 回落并计入回退统计；要 10 cm/10 m 必须显式给值。
- 条件字段：限定词说"不存在"却给了标量值 → 失败（不会悄悄丢掉）。迭代组里可以给列表，
  某轮不出现的位置写 `null`。

## 生成硬校验（不过就一个文件都不写）

1. 协议定长：M6/M39/M41/M154/155/156/159=10 字节、M15=13、M8/M146=14、M32=11、M34=14；
   P3=186、P57=49、P58=56、P65=71、P66=31、P4=29、CTCS-136=46 位。
2. 报文 ≤ 500 字节。
3. 组成：M3 必须有 P15；M129 必须 P0|P1 + P11；M132/M136/M147/M149/M150/M157 必须 P0|P1；
   信息包/用户包必须在 §3.8/§4 的组成表里；同类型包不可重复（P65/P66/P44 例外，但同类内
   `NID_TSR` 须互异、用户包不得重复）。
4. 车→地包不能塞进地→车报文（双向都查）。
5. 含 CTCS-80/81/82/83 的 M24 必须 `M_ACK=1`；M2 的 `M_ACK` 固定 1。
6. P68 `Q_TRACKINIT=1` 直接失败（国内 ATP 不接受）。
7. values 里有没被消费的键 → 失败（防拼错、防放错包）。

## 命令

```sh
python <skill-dir>/scripts/gen_rbc_msg.py --describe M155
python <skill-dir>/scripts/gen_rbc_msg.py --values values.json -o out/
python <skill-dir>/scripts/gen_rbc_msg.py --values values.json --message M3 -o out/ -v
python <skill-dir>/scripts/gen_rbc_msg.py --values values.json \
  --set M3.P15.L_ENDSECTION=3000 --set M24.header.NID_LRBG=16681259
python <skill-dir>/scripts/gen_rbc_msg.py --values values.json -o out/ --hex-style spaced
```

Windows PowerShell 先执行 `$env:PYTHONUTF8=1`（cmd 用 `set PYTHONUTF8=1`）。

| 选项 | 用途 |
|---|---|
| `--describe M155` | 只打印消息结构（方向/定长/帧头/必选包/values 骨架），不生成文件；不需要 `--values` |
| `--values PATH` | 取值 JSON（生成时必填） |
| `-o DIR` | 输出目录（默认当前目录） |
| `--message M3` | 只生成指定报文（可重复；名字是顶层键） |
| `--set 路径=值` | 临时覆盖：`M3.header.NID_BG=523`、`M3.P15.L_ENDSECTION=3000`、`M3.P65[2].NID_TSR=128`、`M3.P44.CTCS-150.NID_ENGINE=90`；逗号分隔表示列表 |
| `--hex-style plain\|spaced\|lines` | 一行连续（默认）/ 每字节空格 / 每行若干字节 |
| `--p72-charset` | P72 文本编码 |
| `--ctcs132-sig-bits` | CTCS-132 的 NID_SIG 位宽 |
| `-v` | 打印每个字段的偏移、位宽、取值来源 |

输出示例：

```
M3.hex     M3 行车许可 MA     78 字节  L_MESSAGE=78  回退 21 字段  包=[P15,P21,P44/CTCS-150]
    hex: 0313800021D7…
    L_MESSAGE: 78 字节（自动回填）
    位遍历闭合: 617 bit = 78 字节 + 7 bit 补 1（OK）
```

## 生成后必须做的核对

1. 用 `dump_rbc_msg.py` 把生成的 hex 反解回来：要求 `L_MESSAGE` 一致、每个包 `L_PACKET`
   一致、位遍历闭合、组成校验无错误、无告警（`decode.md`）。
2. 复现场景：与参考数据**逐字节**比对（不是只比长度）。
3. 定点修改场景：解码 → 再导出 values → 与改过的 values 对比，差异必须只有目标字段（`edit.md`）。
4. 想确认实现本身没坏：`python <skill-dir>/scripts/selftest_rbc_msg.py`。

## 排错

| 报错 | 原因 | 处理 |
|---|---|---|
| `未给取值，协议也没有默认值` | 该字段必须给值 | 按 `references/protocol.md` 的字段表补值 |
| `P3 … 计算得 L_PACKET=186，协议固定 186` 之类不符 | 迭代计数/条件字段与协议定长冲突 | 按协议给的计数（P3 的 `N_ITER` 必须=1，P58 必须=0） |
| `缺少必选信息包：P15 …` | 报文组成不全 | 补必选包 |
| `… 不在 M3（行车许可 MA）的信息包组成里` | 该包不属于这条消息 | 换消息或去掉该包（注意 CTCS-132/150 只由 M3 承载） |
| `… 是车→地信息包，不能放进地→车的 M3` | 方向搞反 | 检查 packet 与消息号 |
| `values 里的键没有被任何字段消费：…` | 拼错/放错包/序号写错 | 按提示改键名；`-v` 看实际字段名 |
| `该名字在本帧声明了 N 次…请用 NAME#n` | 同名多处的字段只给了第 1 个 | 改成 `NAME#1` / `NAME#2` 或 `NAME(k)` |
| `当前限定词下该字段不进报文` | 条件字段给了值但限定词=0 | 改正限定词，或删掉该字段 |
| `文本按 … 编码得 N 字节，与 L_TEXT=… 不符` | `L_TEXT` 是字符数，编码后字节数对不上 | 校正 `L_TEXT`（UTF-16 每字符 2 字节） |
| `IP 需要 8 段` | 双 IP 只给了一个地址 | 写成 `A.B.C.D.E.F.G.H` |
| `列表只有 N 项，取第 [k] 轮时越界` | 列表没覆盖迭代轮次 | 补齐列表，用不到的位置写 `null` |
| 把 `--set` 的包序号当成 0 起 | 脚本按 1 起数 | `P65[1]` 是第一个 |
