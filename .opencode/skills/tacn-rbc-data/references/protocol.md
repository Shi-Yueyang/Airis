# TACN 车地无线通信协议（OBS ↔ RBC）数据格式

> 依据 RA20016_C4D-IND-ATP_CASCO_2003（OBS-RBC 外部接口定义），仅收录 TACN 变体的消息与信息包数据结构。
>
> 本文是编解码脚本的结构真相源；脚本层的约定（L_PACKET 计数口径、P44 嵌套、键写法、
> 定长结果表）见 **附录 C**，源文档里的冲突与缺口见 **附录 B**。

## 0. 数据层级模型

### 0.1 三层结构

数据分三层，自上而下嵌套：

```
第 1 层  消息 Message            —— 空口收发的一整份电报，表达"一次通信意图"
└─ 第 2 层  信息包 Packet         —— 消息体内的自包含数据积木，一条消息含若干个
   └─ 第 3 层  用户包 CTCS-xx     —— 仅嵌于 P44 内的扩展数据，表达"一项 CTCS 特色功能"
```

示例（M136 列车位置报告）：

```
M136 列车位置报告                        【第1层：消息】
 ├─ P0  位置报告              必选       【第2层：信息包】
 ├─ P44 ─→ CTCS-151 工况状态  可选      【P44 内为第3层】
 ├─ P4   错误报告             条件可选   【第2层：信息包】
 └─ P44 ─→ CTCS-54 地图版本   条件可选   【第3层】
```

### 0.2 各层的标识与定义位置

| 层级 | 标识字段 | 定义章节 |
|---|---|---|
| 第 1 层 | NID_MESSAGE（8 bit） | 第 3、4 章 |
| 第 2 层 | NID_PACKET（8 bit） | 第 5、6 章 |
| 第 3 层 | NID_XUSER（9 bit） | 第 8、9 章 |

---

# 总体规则

## 1. 数据编码规则

1. 消息结构 = 消息头 + 预定义变量 + 必选信息包 + 可选信息包 + 填充。
2. 比特流按定义表**从上到下**顺序、**MSB 先行**紧密排列；末尾不足整字节的部分全部填 **1**。
3. `L_MESSAGE` 为整条消息字节数，计算长度与其不符时整条消息无效；每条消息 ≤ **500 字节**。
4. 一个信息包（含其 NID_PACKET/L_PACKET 头）不得拆分到多条消息；接收处理与信息包排列顺序无关。
5. 信息包头：`NID_PACKET` 8 bit + `L_PACKET` 13 bit（单位：**位**）；44 包内用户包用 `NID_XUSER` 9 bit 标识。
6. 距离/长度分辨率 `Q_SCALE`：0=10 cm，1=1 m，2=10 m；速度类 `V_xx` 7 bit 分辨率 5 km/h，TACN 位置报告中 `V_TRAIN` 分辨率 **1 km/h**。
7. `NID_LRBG = NID_C(10 bit，高 7 位大区号+低 3 位分区号) + NID_BG(14 bit)`；方向/距离类字段以 LRBG 为基准。
8. 常用未知哨兵值：NID_LRBG/NID_PRVBG=16777215；D_xx/L_xx(15 bit)=32767；32 bit 字段=0xFFFFFFFF；16 bit=0xFFFF；24 bit=0xFFFFFF。
9. 同一消息内不得含多个同方向同类型信息包；例外：多个 65/66（NID_TSR 须互异，255 除外）、多个 44（内嵌用户包不得重复）。

## 2. 报文帧形

### 2.1 地→车帧头

| 段 | 变量 | 位数 | 说明 |
|---|---|---|---|
| 1 | NID_MESSAGE | 8 | 消息标识号 |
| 2 | L_MESSAGE | 10 | 消息长度（字节，NID_MESSAGE 起至填充结束） |
| 3 | T_TRAIN | 32 | RBC 发送时间戳（以对车载时间的安全估计为基准） |
| 4 | M_ACK | 1 | 车载是否必须确认本消息（0 否 / 1 是） |
| 5 | NID_LRBG | 10+14 | 最近相关应答器组标识号（NID_C + NID_BG） |
| … | 预定义变量 | — | 取决于消息类型（规则 1-1），无则省略 |
| … | 必选信息包 | — | 取决于消息类型 |
| … | 可选信息包 | — | 取决于消息类型 |
| 末 | 填充 | — | 末尾比特补 1 至整字节 |

### 2.2 车→地帧头

| 段 | 变量 | 位数 | 说明 |
|---|---|---|---|
| 1 | NID_MESSAGE | 8 | 消息标识号 |
| 2 | L_MESSAGE | 10 | 消息长度（字节） |
| 3 | T_TRAIN | 32 | 车载时间戳 |
| 4 | NID_ENGINE | 24 | 列车标识号 |
| 5 | 预定义变量 | — | 取决于消息类型（规则 1-1），无则省略 |
| 6 | 必选信息包 | — | 通常为信息包 0 或 1 |
| 7 | 可选信息包 | — | 取决于消息类型 |
| 8 | 填充 | — | 末尾比特补 1 至整字节 |

---

# 第 1 层数据：消息（NID_MESSAGE）

## 3. 地→车消息

### 3.1 M2 目视授权
- 帧头约束：M_ACK 固定=1
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| Q_SCALE | 2 | |
| D_SR | 15 | 至目视授权终点距离 |

- 信息包组成：P63 目视授权范围内应答器列表，可选（§5.9）

### 3.2 M3 行车许可（MA）
- 帧头约束：NID_LRBG=最新位置报告值
- 预定义变量：无
- 信息包组成：

| 序 | 包 | 必选性 | 定义位置 |
|---|---|---|---|
| 1 | P3 配置参数 | 可选 | §5.1 |
| 2 | P15 行车许可 MA | **必选** | §5.3 |
| 3 | P5 链接信息 | 条件可选 | §5.2 |
| 4 | P21 坡度曲线 | 条件可选 | §5.4 |
| 5 | P27 静态速度曲线 | 条件可选 | §5.5 |
| 6 | P65 设置临时限速 | 可选 | §5.10 |
| 7 | P66 取消临时限速 | 可选 | §5.11 |
| 8 | P68 线路条件 | 条件可选 | §5.12 |
| 9 | P80 引导/调车区段设置 | 条件可选 | §5.14 |
| 10 | P44 ─→ CTCS-132 道岔/信号状态 | 条件可选 | §7 / §8.6 |
| 11 | P44 ─→ CTCS-150 EOA 点类型信息 | 可选 | §7 / §8.7 |

### 3.3 M6 确认退出冒进防护模式
地→车帧头（NID_MESSAGE=6），L_MESSAGE=10，无预定义变量、无信息包。

### 3.4 M8 列车数据确认
- 帧头约束：L_MESSAGE=**14**
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| T_TRAIN（回显） | 32 | 被确认 M129 的时间戳回显 |

- 信息包组成：无

### 3.5 M15 有条件紧急停车
- 帧头约束：L_MESSAGE=**13**
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_EM | 4 | 1~15，对每个 ATP 从 1 独立计数 |
| Q_SCALE | 2 | |
| Q_DIR | 2 | 固定 1（正向有效） |
| D_EMERGENCYSTOP | 15 | LRBG 至紧急停车点距离 |

- 信息包组成：无

### 3.6 M16 无条件紧急停车
地→车帧头（NID_MESSAGE=16）+ 预定义变量 NID_EM 4 bit（固定 0）。无信息包。

### 3.7 M18 取消紧急停车
地→车帧头（NID_MESSAGE=18）+ 预定义变量 NID_EM 4 bit（0~15，指定被取消的紧急消息）。无信息包。

### 3.8 M24 通常消息
- 预定义变量：无
- 信息包组成（全部可选，按需组合）：

| 序 | 包 | 备注 | 定义位置 |
|---|---|---|---|
| 1 | P3 配置参数 | | §5.1 |
| 2 | P57 MA 请求参数 | | §5.7 |
| 3 | P58 位置报告参数 | | §5.8 |
| 4 | P65 设置临时限速 | | §5.10 |
| 5 | P66 取消临时限速 | | §5.11 |
| 6 | P72 纯文本消息 | | §5.13 |
| 7 | P44 ─→ CTCS-51 TSRS 电子地图版本 | | §7 / §8.1 |
| 8 | P44 ─→ CTCS-131 IP 化会话管理 | | §7 / §8.5 |
| 9 | P44 ─→ CTCS-80 编组命令 | M_ACK=1 | §7 / §8.2 |
| 10 | P44 ─→ CTCS-81 编组状态 | M_ACK=1 | §7 / §8.3 |
| 11 | P44 ─→ CTCS-82 解编预告 | M_ACK=1 | §7 / §8.4 |
| 12 | P44 ─→ CTCS-83 解编命令 | M_ACK=1 | §7 / §8.3 |
| 13 | P44 ─→ CTCS-152 后车信息 | | §7 / §8.8 |
| 14 | P41 等级切换 | | §5.6 |

### 3.9 M32 系统版本
地→车帧头（NID_MESSAGE=32，L_MESSAGE=**11**）+ 预定义变量 M_VERSION 7 bit = 16。无信息包。

### 3.10 M34 确认前方轨道空闲（TAF 请求）
- 帧头约束：L_MESSAGE=**14**
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| Q_SCALE | 2 | |
| Q_DIR | 2 | 0 反向/1 正向/2 双向/3 备用 |
| D_TAFDISPLAY | 15 | LRBG 至 TAF 窗口起点距离 |
| L_TAFDISPLAY | 15 | 窗口长度，默认 200 m |

- 信息包组成：无

### 3.11 M39 / M41（会话类，纯帧头）
地→车帧头，L_MESSAGE=10，无预定义变量、无信息包。
（39 会话结束确认 / 41 接受列车）

### 3.12 M45 分配坐标系
地→车帧头（NID_MESSAGE=45）+ 预定义变量 Q_ORIENTATION 1 bit（0=反向通过应答器组，1=正向通过应答器组）。无信息包。

## 4. 车→地消息

### 4.1 M129 经过确认的列车数据
- 预定义变量：无
- 信息包组成：

| 序 | 包 | 必选性 | 定义位置 |
|---|---|---|---|
| 1 | P0 或 P1 | **必选** | §6.1 / §6.2 |
| 2 | P11 列车数据 | **必选** | §6.4 |

### 4.2 M132 请求 MA
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| Q_TRACKDEL | 1 | 1=请求重发以 LRBG 起点的全部线路描述；0=未删除 |

- 信息包组成：

| 序 | 包 | 必选性 | 定义位置 |
|---|---|---|---|
| 1 | P0 或 P1 | **必选** | §6.1 / §6.2 |
| 2 | P44 ─→ CTCS-136 发车信息 | 可选 | §7 / §9.3 |

### 4.3 M136 列车位置报告
- 预定义变量：无
- 信息包组成：

| 序 | 包 | 必选性 | 定义位置 |
|---|---|---|---|
| 1 | P0 或 P1 | **必选** | §6.1 / §6.2 |
| 2 | P44 ─→ CTCS-151 列车工况状态 | 可选 | §7 / §9.4 |
| 3 | P4 错误报告 | 条件可选 | §6.3 |
| 4 | P44 ─→ CTCS-54 车载电子地图版本 | 条件可选 | §7 / §9.1 |
| 5 | P44 ─→ CTCS-84 编组列车运行状态 | 条件可选 | §7 / §9.2 |

### 4.4 M146 确认
- 帧头约束：L_MESSAGE=**14**
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| T_TRAIN（回显） | 32 | 被确认消息的时间戳回显 |

- 信息包组成：无

### 4.5 M147 紧急停车确认
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_EM | 4 | 被确认紧急消息标识 0~15 |
| Q_EMERGENCYSTOP | 2 | 0=接受有条件紧急停车；1=忽略有条件紧急停车；2=接受无条件紧急停车；3=备用 |

- 信息包组成：P0 或 P1，必选（§6.1 / §6.2）

### 4.6 M149 前方轨道空闲确认
车→地帧头（NID_MESSAGE=149）+ **P0 或 P1**（必选）。无预定义变量。

### 4.7 M150 任务结束
车→地帧头（NID_MESSAGE=150）+ **P0 或 P1**（必选）。无预定义变量。

### 4.8 M157 SoM 位置报告
- 预定义变量：

| 变量 | 位数 | 取值 |
|---|---|---|
| Q_STATUS | 2 | 0=位置无效；1=位置有效；2=位置未知（LRBG 未知或方向未知时）；3=备用 |

- 信息包组成：

| 序 | 包 | 必选性 | 定义位置 |
|---|---|---|---|
| 1 | P0 或 P1 | **必选** | §6.1 / §6.2 |
| 2 | P4 错误报告 | 条件可选 | §6.3 |

### 4.9 M154 / M155 / M156 / M159（会话类，纯帧头）
车→地帧头，**L_MESSAGE=10**，无预定义变量、无信息包。
（154 版本不兼容 / 155 会话开始 / 156 会话结束 / 159 会话已建立）

---

# 第 2 层数据：信息包（NID_PACKET）

## 5. 地→车信息包

### 5.1 P3 配置参数
- NID_PACKET=3；**L_PACKET=186**
- 被载于：M3 / M24 —— 可选
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_PACKET | 8 | 3 |
| Q_DIR | 2 | 0 反向/1 正向/2 双向 |
| L_PACKET | 13 | 186 |
| Q_SCALE | 2 | |
| D_VALIDNV | 15 | 0 |
| N_ITER | 5 | NID_C 数量 |
| NID_C(k) | 10 | 高 7 位大区号+低 3 位分区号 |
| V_NVSHUNT | 7 | SH 限速，默认 8（40 km/h） |
| V_NVSTFF | 7 | OS 限速 4（20 km/h） |
| V_NVONSIGHT | 7 | CO 限速 4（20 km/h） |
| V_NVUNFIT | 7 | 16（80 km/h）（车载未使用） |
| V_NVREL | 7 | 0（车载未使用） |
| D_NVROLL | 15 | 5 |
| Q_NVSRBKTRG | 1 | 1（车载未使用） |
| Q_NVEMRRLS | 1 | 0（车载未使用） |
| V_NVALLOWOVTRP | 7 | 0（车载未使用） |
| V_NVSUPOVTRP | 7 | 8（车载未使用） |
| D_NVOVTRP | 15 | 32767（车载未使用） |
| T_NVOVTRP | 8 | 60（车载未使用） |
| D_NVPOTRP | 15 | 0 |
| M_NVCONTACT | 2 | 1=常用制动 SB |
| T_NVCONTACT | 8 | 默认 20；255=不监控 |
| M_NVDERUN | 1 | 0（车载未使用） |
| D_NVSTFF | 15 | 32767（车载未使用） |
| Q_NVDRIVER_ADHES | 1 | 0（车载未使用） |

### 5.2 P5 链接信息
- NID_PACKET=5；L_PACKET=变长
- 被载于：M3 —— 条件可选
- 字段：Q_SCALE 2 + D_LINK 15（至下一链接 BG 距离增量，组内多应答器以第一个为准）+ Q_NEWCOUNTRY 1（=1 时带 NID_C 10）+ NID_BG 14 + Q_LINKORIENTATION 1（0 反/1 正）+ Q_LINKREACTION 2（1=常用制动/2=无反应）+ Q_LOCACC 6（默认 5）+ N_ITER 5，其后 (k) 组迭代同上。

### 5.3 P15 行车许可
- NID_PACKET=15；L_PACKET=变长
- 被载于：M3 —— **必选**（MA 的本体）
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_PACKET / Q_DIR / L_PACKET / Q_SCALE | 8/2/13/2 | Q_DIR：0 反/1 正 |
| V_LOA | 7 | 0（车载未使用） |
| T_LOA | 10 | （车载未使用） |
| N_ITER | 5 | 中间区段数；MA 仅一个区段时=0 |
| L_SECTION(k) | 15 | 区段长度（N_ITER>0 时存在） |
| Q_SECTIONTIMER(k) | 1 | 默认 0（车载未使用） |
| T_SECTIONTIMER(k) | 10 | 条件存在（车载未使用） |
| D_SECTIONTIMERSTOPLOC(k) | 15 | 条件存在（车载未使用） |
| **L_ENDSECTION** | 15 | MA 末区段长度 |
| Q_SECTIONTIMER / Q_ENDTIMER | 1/1 | 0（车载未使用） |
| Q_DANGERPOINT | 1 | 0 无/1 后随危险点信息 |
| D_DP | 15 | （车载未使用） |
| V_RELEASEDP | 7 | 危险点开口速度 |
| Q_OVERLAP | 1 | （车载未使用） |
| D_STARTOL / T_OL / D_OL / V_RELEASEOL | 15/10/15/7 | （车载未使用；T_OL=1023 表示∞） |

### 5.4 P21 坡度曲线
- NID_PACKET=21；L_PACKET=变长
- 被载于：M3 —— 条件可选
- 字段：Q_SCALE 2 + D_GRADIENT 15 + Q_GDIR 1（0 下/平坡、1 上坡）+ G_A 8；N_ITER 5 后迭代 D_GRADIENT(k) 15（增量）+ Q_GDIR(k) + G_A(k)。
- 终止约定：最后一个 **G_A=255** = 描述结束；最后一个 G_A≠255 = 坡度无限长。

### 5.5 P27 静态速度曲线（SSP）
- NID_PACKET=27；L_PACKET=变长
- 被载于：M3 —— 条件可选
- 字段：Q_SCALE 2 + D_STATIC 15 + V_STATIC 7（5 km/h）+ Q_FRONT 1（0=尾有效/升速，1=头有效/降速）；
  N_ITER 5（列车类型数）+ NC_DIFF(n) 4 + V_DIFF(n) 7；
  N_ITER 5（速度变化点数）+ 迭代 D_STATIC(k) 15 + V_STATIC(k) 7 + Q_FRONT(k) 1 + N_ITER(k) 5 + NC_DIFF(k,m) 4 + V_DIFF(k,m) 7。
- 终止约定：最后一个 **V_DIFF=127** = 描述结束，否则最后一个 SSP 无限长。
- NC_DIFF：0 主动摆式/1 被动摆式/2 跨风敏区/3 机牵客/4 机牵货（对应 NC_TRAIN 位）。

### 5.6 P41 等级切换
- NID_PACKET=41；L_PACKET=变长
- 被载于：M24 —— 可选
- 字段：Q_SCALE 2 + D_LEVELTR 15（**32767=立即转换**）+ M_LEVELTR 3（1=C0/C2、3=C3、4=CN）+ NID_STM 8（仅 M_LEVELTR=1：1=C0、3=C2）+ L_ACKLEVELTR 15（默认 450）；N_ITER 5 后迭代 M_LEVELTR(k) + NID_STM(k) + L_ACKLEVELTR(k)。
- 取消约定：M_LEVELTR 或 NID_STM 为无效值 = 取消等级转换。

### 5.7 P57 MA 请求参数
- NID_PACKET=57；**L_PACKET=49**
- 被载于：M24 —— 可选
- 字段：T_MAR 8（60）+ T_TIMEOUTRQST 10（1023）+ T_CYCRQST 8（60，两次 MA 循环请求间隔秒数）。

### 5.8 P58 位置报告参数
- NID_PACKET=58；**L_PACKET=56**
- 被载于：M24 —— 可选
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| Q_SCALE | 2 | |
| T_CYCLOC | 8 | 位置报告时间间隔（默认 6；255=无效） |
| D_CYCLOC | 15 | 报告间隔距离；32767=不按距离 |
| M_LOC | 3 | 001=每个应答器点 |
| N_ITER | 5 | 报告点数量 |
| D_LOC(k) | 15 | 报告点位置 |
| Q_LGTLOC(k) | 1 | 1=最大安全前端越过；0=最小安全尾端越过 |

### 5.9 P63 目视授权范围内应答器列表
- NID_PACKET=63；L_PACKET=变长
- 被载于：M2 —— 可选
- 字段：N_ITER 5 后迭代：Q_NEWCOUNTRY(k) 1（=1 时带 NID_C(k) 10）+ NID_BG(k) 14。

### 5.10 P65 设置临时限速
- NID_PACKET=65；**L_PACKET=71**
- 被载于：M3 / M24 —— 可选（可多个，NID_TSR 互异，见规则 1-9）
- 字段：Q_SCALE 2 + NID_TSR 8（0~126 应答器方式；127~254 RBC 自定；255=不可撤销）+ D_TSR 15 + L_TSR 15 + Q_FRONT 1（0 尾/1 头）+ V_TSR 7（5 km/h）。

### 5.11 P66 取消临时限速
- NID_PACKET=66；**L_PACKET=31**
- 被载于：M3 / M24 —— 可选（可多个，见规则 1-9）
- 字段：NID_TSR 8（127~254）。

### 5.12 P68 线路条件
- NID_PACKET=68；L_PACKET=变长
- 被载于：M3 —— 条件可选
- 字段：Q_TRACKINIT 1（**=1 国内不适用，ATP 不接受**）+ D_TRACKCOND 15 + L_TRACKCOND 15 + M_TRACKCOND 4：0000 禁停隧道 / 0001 禁停桥梁 / 0010 禁停其他 / 0011 无电区降弓（预留）/ 0100 无线盲区（预留）/ 1001 无电区关主断 / **1010 防汛区段**；N_ITER 5 后迭代 D/L/M_TRACKCOND(k)。

### 5.13 P72 纯文本消息（DMS）
- NID_PACKET=72；L_PACKET=变长
- 被载于：M24 —— 可选
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| Q_SCALE | 2 | |
| Q_TEXTCLASS | 2 | 0 辅助信息/1 重要信息 |
| Q_TEXTDISPLAY | 1 | 0 条件之一满足即显示/1 组合满足 |
| D_TEXTDISPLAY | 15 | 32767=不受距离限制 |
| M_MODETEXTDISPLAY | 4 | 触发模式；15=不受限 |
| M_LEVELTEXTDISPLAY | 3 | 1=C0/C2、3=C3、4=CN、5=不受限；=1 时带 NID_STM 8 |
| L_TEXTDISPLAY | 15 | 32767=不限 |
| T_TEXTDISPLAY | 10 | 1023=不限 |
| （结束条件）M_MODETEXTDISPLAY / M_LEVELTEXTDISPLAY / NID_STM | 4/3/8 | 同上编码 |
| Q_TEXTCONFIRM | 2 | 0 无需确认/1 显示直到确认/2 结束未确认则常用制动 |
| L_TEXT | 8 | 文本长度（字符个数） |
| X_TEXT(k) | 8×L_TEXT | 文本内容，UTF-16（UNICODE）编码 |

### 5.14 P80 引导/调车区段设置（Mode Profile）
- NID_PACKET=80；L_PACKET=变长
- 被载于：M3 —— 条件可选
- 字段：Q_SCALE 2 + D_MAMODE 15 + M_MAMODE 2（0=引导 CO）+ V_MAMODE 7（0~120 有效，默认 4=20 km/h；127=取本国值 V_NVONSIGHT）+ L_MAMODE 15 + L_ACKMAMODE 15（400）；N_ITER 5 后 (k) 迭代同上。
- 与 CTCS-80（§8.2）同号不同层。

## 6. 车→地信息包

### 6.1 P0 位置报告（方向已知，LRBG 定位）
- NID_PACKET=0；L_PACKET=变长（位）
- 被载于：M129 / M132 / M136 / M147 / M149 / M150 / M157 —— 均为必选位，与 P1 二选一
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_PACKET | 8 | 0 |
| L_PACKET | 13 | 包长度（位） |
| Q_SCALE | 2 | 0=10 cm/1=1 m/2=10 m |
| NID_LRBG | 10+14 | 16777215=未知 |
| D_LRBG | 15 | LRBG 至列车估计前端距离；32767=未知 |
| Q_DIRLRBG | 2 | 0 反向/1 正向/2 未知/3 备用 |
| Q_DLRBG | 2 | 估计前端在 LRBG 哪一侧；同上编码 |
| L_DOUBTOVER | 15 | \|置信下限−D_LRBG\|；32767=未知 |
| L_DOUBTUNDER | 15 | \|置信上限−D_LRBG\|；32767=未知 |
| Q_LENGTH | 2 | 0 无完整性信息/1 完整性装置确认/2 司机确认/3 丢失 |
| L_TRAININT | 15 | 安全车长（1 m），仅 Q_LENGTH=1/2 时存在 |
| V_TRAIN | 7 | 车速，分辨率 1 km/h（TACN） |
| Q_DIRTRAIN | 2 | 0 反向/1 正向/2 未知/3 备用 |
| M_MODE | 4 | 0 FS/1 CO/2 OS/3 SH/5 SL/6 SB/7 TR/8 PT/10 IS/**12 VC**/13 SN/14 预留/15 BS |
| M_LEVEL | 3 | 1=C2 或 C0；3=C3；4=CN |
| NID_STM | 8 | 仅 M_LEVEL=1 时存在：1=C0，3=C2 |

### 6.2 P1 位置报告（方向未知，双 BG）
- NID_PACKET=1；L_PACKET=变长（位）
- 被载于：同 P0，二者按列车方向是否已知**二选一**
- 字段：**同 P0**（§6.1），仅在 NID_LRBG 之后插入：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_PRVBG | 10+14 | 前一应答器组（NID_C+NID_BG），列车由 PRVBG 向 LRBG 运行；16777215=未知 |

### 6.3 P4 错误报告
- NID_PACKET=4；**L_PACKET=29**
- 被载于：M136 / M157 —— 条件可选（检测到错误时）
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_PACKET | 8 | 4 |
| L_PACKET | 13 | 29 |
| M_ERROR | 8 | 0 BG 一致性-链接位置/编号错误；1 BG 一致性-链接 BG 报文错误；2 BG 一致性-未链接 BG 报文错误；3 无线一致性-消息错误；4 无线一致性-时序错误；5 无线一致性-超时；6 非致命错误；7 致命错误；8~255 备用 |

### 6.4 P11 列车数据
- NID_PACKET=11；L_PACKET=变长（取决于内容）
- 被载于：M129 —— 必选
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_PACKET | 8 | 11 |
| L_PACKET | 13 | 取决于内容 |
| NID_OPERATIONAL | 32 | 车次号；4294967295=未知 |
| NC_TRAIN | 15 | SSP 类型位掩码（0 基本/1 主动摆式/2 被动摆式/4 跨风敏区/8 机牵客/16 机牵货） |
| L_TRAIN | 12 | 列车长度 |
| V_MAXTRAIN | 7 | 列车最大允许速度 |
| M_LOADINGGAUGE | 8 | 0 |
| M_AXLELOAD | 7 | 轴重/0.5（≤40 t）；>40 t 填 126 |
| M_AIRTIGHT | 2 | 0=未装 |
| N_ITER | 5 | 牵引类型数量，0 |
| N_ITER | 5 | STM 类型数量 |
| NID_STM(k) | 8 | 1=C0，3=C2 |

---

# 第 3 层数据：用户包（NID_XUSER）

## 7. P44 用户包封装

P44（NID_PACKET=44）携带用户包；一条消息可含多个 P44，内嵌用户包不得重复（规则 1-9）。封装头按方向：

| 方向 | 封装头结构 | 定义位置 |
|---|---|---|
| 地→车 | NID_PACKET 8=44 + Q_DIR 2 + L_PACKET 13 + **NID_XUSER 9**（用户包 ID） | §8 |
| 车→地 | NID_PACKET 8=44 + L_PACKET 13 + **NID_XUSER 9**（用户包 ID） | §9 |

解析：NID_PACKET=44 后跳过封装头，按 NID_XUSER 查 §8/§9。

## 8. 地→车用户包

### 8.1 CTCS-51 TSRS 电子地图版本
- NID_XUSER=51；经 P44 载于：M24 —— 可选
- 字段：NID_XUSER 9=51 + Q_DIR 2（2=双向）+ L_PACKET 13 + N_PKTNUM 6（1~63）+ Q_PKTSEQ 6（0~(N−1)）+ MAPINDEX_FILE（8 bit 整数倍，电子地图索引文件内容）。

### 8.2 CTCS-80 编组命令
- NID_XUSER=80；经 P44 载于：M24 —— 可选，M_ACK=1
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_XUSER | 9 | 80；Q_DIR 2（=2）+ L_PACKET 13 |
| GROUP_ID | 32 | 0xFFFFFFFF=未编组 |
| N_TRAINNUM | 4 | 编组列车数 1~15 |
| Group_NID_ENGINE | 24×N | 按编组顺序的列车 NID_ENGINE |
| NID_ENGINE_PRE | 24 | 前车 NID_ENGINE，默认 0xFFFFFF |
| M_IP_PRE | 64 | 前车双网 IP（ABCD 各 1 字节高→低，两组） |

### 8.3 CTCS-81 编组状态 / CTCS-83 解编命令
- NID_XUSER=81 或 83；经 P44 载于：M24 —— 可选，M_ACK=1
- 字段（81 与 83 结构完全相同）：NID_XUSER + Q_DIR 2（=2）+ L_PACKET 13 + GROUP_ID 32。

### 8.4 CTCS-82 解编预告
- NID_XUSER=82；经 P44 载于：M24 —— 可选，M_ACK=1
- 字段：同 CTCS-81（§8.3），追加 Q_SCALE 2 + D_DECOUPLEPOS 15（至解编点距离）。

### 8.5 CTCS-131 IP 化车地通信会话管理
- NID_XUSER=131；经 P44 载于：M24 —— 可选
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_XUSER | 9 | 131 |
| Q_DIR | 2 | 0/1/2/3 |
| L_PACKET | 13 | |
| Q_SCALE | 2 | |
| Q_CMDTYPE | 1 | 0=会话管理；1=RBC 移交 |
| Q_RBC | 1 | Q_CMDTYPE=0 时：0 终止/1 建立 |
| D_RBCTR | 15 | Q_CMDTYPE=1 时：至移交执行点距离 |
| NID_C / NID_RBC | 10/14 | 目标 RBC 标识 |
| NID_RADIO | 64 | 双 IP：主 IP A、B、C、D 各 1 字节高→低占前 32 位，后 32 位为第二 IP |
| Q_SLEEPSESSION | 1 | 0 忽略/1 考虑；固定填 1 |

### 8.6 CTCS-132 道岔定反位 / 信号状态
- NID_XUSER=132；经 P44 载于：M3 —— 条件可选
- 字段：

| 变量 | 位数 | 说明 |
|---|---|---|
| NID_XUSER | 9 | 132；Q_DIR 2（=2）+ L_PACKET 13 |
| N_STACNT | 8 | 车站数；>0 时存在以下 (i)(j) 字段 |
| NID_STA(i) | 16 | 车站编号 |
| N_TO(i) | 5 | 车站内道岔数量 |
| NID_TO(i)(j) | 8 | 道岔编号 |
| Q_TOSTATUS(i)(j) | 2 | 0 未知/1 定位/2 反位/3 备用 |
| N_SIGSTACNT | 8 | 信号状态车站数 |
| NID_STA(i) | 16 | 车站编号 |
| N_SIG(i) | 5 | 信号机数量 |
| NID_SIG(i)(j) | n | 信号机编号（n 依编号规则） |
| Q_SIGSTATUS(i)(j) | 2 | 0 关闭/1 开放/2 引导/3 备用 |

### 8.7 CTCS-150 EOA 点类型信息
- NID_XUSER=150；经 P44 载于：M3 —— 可选
- 字段：

| 变量 | 位数 | 取值/说明 |
|---|---|---|
| NID_XUSER | 9 | 150；Q_DIR 2 + L_PACKET 13 |
| Q_EOALOC | 8 | 1 区间/2 站内/其他无效 |
| Q_EOATYPE | 8 | 0 前车后端/1 进站信号机/2 阻挡信号机/3 最大长度/4 其他 |
| NID_ENGINE | 24 | =0 类型时前车 NID_ENGINE（不可全 F），否则 0xFFFFFF |
| NID_OPERATIONAL | 32 | =0 类型时前车车次（不可全 F），否则 0xFFFFFFFF |
| V_TRAIN | 16 | =0 类型时前车速度 km/h，否则 0xFFFF |
| Q_DIR_HANDLE | 8 | =0 类型时前车方向手柄（0 故障/1 前/2 后/3 中立/0xFF 未知），否则 0xFF |
| Q_TRACTION_HANDLE | 8 | =0 类型时前车牵引手柄（0 故障/1 牵引/2 制动/3 零/0xFF 未知），否则 0xFF |
| M_HEAD_PRESSURE / M_TAIL_PRESSURE | 16/16 | 0~999 kPa / 0xFFFF 未知 |
| KILOMETER_POST | 32 | 0xFFFFFFFF=未知 |
| RESERVED1 / RESERVED2 | 32/32 | 0xFFFFFFFF |

### 8.8 CTCS-152 后车信息
- NID_XUSER=152；**L_PACKET=240 bit**；经 P44 载于：M24 —— 可选
- 字段：NID_XUSER 152 + Q_DIR 2 + L_PACKET 13 + NID_ENGINE 24（后车，不可 0xFFFFFF）+ NID_OPERATIONAL 32（后车车次，不可全 F）+ V_TRAIN 16（后车速度，不可 0xFFFF）+ Q_DIR_HANDLE 8 + Q_TRACTION_HANDLE 8 + M_HEAD_PRESSURE 16 + M_TAIL_PRESSURE 16 + KILOMETER_POST 32 + RESERVED1/2 32/32（编码同 CTCS-150）。

## 9. 车→地用户包

### 9.1 CTCS-54 车载电子地图版本
- NID_XUSER=54；经 P44 载于：M136 —— 条件可选
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_XUSER | 9 | 54 |
| L_PACKET | 13 | |
| N_PKTNUM | 6 | 拆分总包数 N：1~63 |
| Q_PKTSEQ | 6 | 本包序号：0~(N−1) |
| N_MAPCNT | 6 | 地图块数量 1~63 |
| M_MAPID(k) | 16 | 地图块编号（车站号）；无则 0 |
| M_GEODATAVERSION(k) | 16 | 无则 0 |
| M_GEODATACRC(k) | 32 | 无则 0 |
| M_FIXDATAVERSION(k) | 16 | 无则 0 |
| M_FIXDATACRC(k) | 32 | 无则 0 |
| N_TSRCNT(k) | 8 | 块内临时限速命令总数；无则 0 |
| M_TSRDATACRC(k) | 32 | 无则 0 |

### 9.2 CTCS-84 编组列车运行报告
- NID_XUSER=84；经 P44 载于：M136 —— 条件可选
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_XUSER | 9 | 84 |
| Q_DIR | 2 | 2=双向有效 |
| L_PACKET | 13 | |
| GROUP_ID | 32 | 编组 ID；0xFFFFFFFF=未编组 |
| Q_SCALE | 2 | 0=10 cm/1=1 m/2=10 m/3 备用 |
| D_DIFF | 15 | ATP 与 RBC 计算 EOA 终点距离之差 |

### 9.3 CTCS-136 发车信息
- NID_XUSER=136；**L_PACKET=46**；经 P44 载于：M132 —— 可选
- 字段：NID_XUSER 9=136 + L_PACKET 13 + NID_C 10 + NID_BG 14（出站应答器组编号）。
- 与 M136（消息）同号不同层。

### 9.4 CTCS-151 列车工况状态信息
- NID_XUSER=151；经 P44 载于：M136 —— 可选
- 字段：

| 变量 | 位数 | 取值 |
|---|---|---|
| NID_XUSER | 9 | 151 |
| L_PACKET | 13 | |
| Q_DIR_HANDLE | 8 | 0 故障/1 向前/2 向后/3 中立/其他无效 |
| Q_TRACTION_HANDLE | 8 | 0 故障/1 牵引/2 制动/3 零位/其他无效 |
| M_HEAD_PRESSURE | 16 | 列首风压 0~999 kPa |
| M_TAIL_PRESSURE | 16 | 列尾风压 0~999 kPa |
| KILOMETER_POST | 32 | 公里标；0xFFFFFFFF=未知 |
| RESERVED1 / RESERVED2 | 32/32 | 0xFFFFFFFF |

---

# 附录

## A. 消息 ↔ 包组成总览

| 消息 | 方向 | 预定义变量 | 必选包 | 可选/条件包 |
|---|---|---|---|---|
| M2 | 地→车 | Q_SCALE、D_SR | 无 | P63 |
| M3 | 地→车 | — | P15 | P3、P5、P21、P27、P65、P66、P68、P80、P44(CTCS-132)、P44(CTCS-150) |
| M6 | 地→车 | — | 无 | — |
| M8 | 地→车 | T_TRAIN 回显 | 无 | — |
| M15 | 地→车 | NID_EM、Q_SCALE、Q_DIR、D_EMERGENCYSTOP | 无 | — |
| M16 | 地→车 | NID_EM | 无 | — |
| M18 | 地→车 | NID_EM | 无 | — |
| M24 | 地→车 | — | 无 | P3、P57、P58、P65、P66、P72、P41、P44(CTCS-51/80/81/82/83/131/152) |
| M32 | 地→车 | M_VERSION | 无 | — |
| M34 | 地→车 | Q_SCALE、Q_DIR、D_TAFDISPLAY、L_TAFDISPLAY | 无 | — |
| M39/41 | 地→车 | — | 无 | — |
| M45 | 地→车 | Q_ORIENTATION | 无 | — |
| M129 | 车→地 | — | P0/P1、P11 | — |
| M132 | 车→地 | Q_TRACKDEL | P0/P1 | P44(CTCS-136) |
| M136 | 车→地 | — | P0/P1 | P44(CTCS-151)、P4、P44(CTCS-54)、P44(CTCS-84) |
| M146 | 车→地 | T_TRAIN 回显 | 无 | — |
| M147 | 车→地 | NID_EM、Q_EMERGENCYSTOP | P0/P1 | — |
| M149 | 车→地 | — | P0/P1 | — |
| M150 | 车→地 | — | P0/P1 | — |
| M154/155/156/159 | 车→地 | — | 无 | — |
| M157 | 车→地 | Q_STATUS | P0/P1 | P4 |

## B. 源文档歧义备注

1. P72 文本编码：TACN 表为 UTF-16（160K 表为 GB18030），联调时需核实。本实现默认
   UTF-16BE，可用 `--p72-charset utf-16-le|gb18030` 切换。
2. M16/M18 的 L_MESSAGE：帧头 75 bit + NID_EM 4 bit = 79 bit，正好 10 字节，源表标的 10 与
   实际一致（生成时已按定长校验）。
3. P15 末区段定时：按源文档的两张 M3 样例——`L_ENDSECTION` 之后恒定写出 `T_ENDTIMER`、
   `D_ENDTIMERSTARTLOC` 和第二组 `Q/T/D_SECTIONTIMER`（§5.3 只列了
   `Q_SECTIONTIMER / Q_ENDTIMER` 两个限定词）。单区段 P15 因此是 185 bit；按 §5.3
   解析会少 26 bit。
4. P5 的 NID_C：§5.2 规定 `Q_NEWCOUNTRY=1` 时才带 NID_C，但源文档的 M3 样例在
   `Q_NEWCOUNTRY=0` 时仍写了 NID_C。本实现按 §5.2（条件存在）。
5. CTCS-132 的 NID_SIG 位宽：§8.6 写"n 依编号规则"，没给具体位数。默认按 8 bit，
   可用 `--ctcs132-sig-bits` 调整。
6. 编组类用户包（CTCS-80/81/82/83）载于 M24 时 M_ACK 必须=1（§3.8 表内标注）：
   生成时按硬规则校验，违反直接失败。
7. Q_SCALE 在协议里没有默认值：所有需要 Q_SCALE 的消息/信息包，本实现按 **1 m** 回落，
   并在"回退字段"统计里报出（不静默）；需要 10 cm / 10 m 时必须显式给值。

---

## C. 编解码实现约定（脚本层）

本节记录 `scripts/` 里编解码器**实际用的**约定，以及它们的证据。协议正文没有明说的地方，
一律在这里给出取舍，改动脚本前先读这一节。

### C.1 帧头与位序

| 方向 | 帧头 | 位数 |
|---|---|---|
| 地→车 | NID_MESSAGE 8 + L_MESSAGE 10 + T_TRAIN 32 + M_ACK 1 + NID_C 10 + NID_BG 14 | 75 |
| 车→地 | NID_MESSAGE 8 + L_MESSAGE 10 + T_TRAIN 32 + NID_ENGINE 24 | 74 |

比特流 MSB 先行、字段紧密相连，末尾不足整字节补 **1**。报文无 CRC，也没有帧同步字：
自洽只能靠 L_MESSAGE、包内 L_PACKET、位遍历闭合和组成规则。

### C.2 L_PACKET 到底数的是哪一段

约定：**L_PACKET 计入本包自己的包头**（`NID_PACKET [+Q_DIR] L_PACKET` 起，到包体结束），
用户包的 L_PACKET 从 `NID_XUSER` 起算。用协议给出的定长包反推验证：

| 包 | 计算 | 协议值 | 结论 |
|---|---:|---:|---|
| P3（N_ITER=1） | 23 + 163 | 186 | ✔ |
| P4（车→地，无 Q_DIR） | 21 + 8 | 29 | ✔ |
| P66 | 23 + 8 | 31 | ✔ |
| P57 | 23 + 26 | 49 | ✔ |
| P58（N_ITER=0） | 23 + 33 | 56 | ✔ |
| P65 | 23 + 48 | 71 | ✔ |
| CTCS-136 | 9 + 13 + 24 | 46 | ✔ |
| CTCS-152 | 9 + 2 + 13 + 216 | 240 | ✔ |

### C.3 P44 嵌套

- 地→车：`NID_PACKET 8 + Q_DIR 2 + L_PACKET 13` → `NID_XUSER 9 + Q_DIR 2 + L_PACKET 13` → 包体。
- 车→地：`NID_PACKET 8 + L_PACKET 13` → `NID_XUSER 9 [+ Q_DIR 2] + L_PACKET 13` → 包体；
  目前只有 CTCS-84 的内层头带 Q_DIR（§9.2）。
- **外层 P44 的 L_PACKET 含整个内层用户包**；内层 L_PACKET 只到内层包体结束。核对锚点：
  M24 + P44/CTCS-80（N_TRAINNUM=2）外层 219 bit、内层 196 bit，合计 294 bit / 37 字节。

### C.4 取值 JSON 的键写法

| 写法 | 含义 |
|---|---|
| `NAME` | 该帧只出现一次时直接命中；出现多次时给全部出现处同一值（脚本会提示） |
| `NAME(k)` / `NAME(k,m)` / `NAME(i)(j)` | 迭代组里的那个同名项；括号里的下标个数就是迭代层数 |
| `NAME#n` | 按声明顺序的第 n 个出现处（M8 的 `T_TRAIN#2`、P44 的内层 `Q_DIR#2` 等） |
| `NID_LRBG` / `NID_PRVBG` | 24 bit 复合键，自动拆成对应的 `NID_C` / `NID_BG` |

迭代组的值可以是列表（下标即轮次，用不到的位置写 `null`），也可以给标量广播到每一轮。
条件字段在某轮不出现时，对应的列表位置可以留 `null`，但不能给非列表的标量（会报错）。

### C.5 生成侧的硬校验（不过就什么都不写）

1. 协议定长：`L_MESSAGE`（M6/M8/M15/M32/M34/M39/M41/M146/M154/155/156/159）与
   `L_PACKET`（P3/P57/P58/P65/P66/P4/CTCS-136/CTCS-152）。
2. 报文 ≤ 500 字节。
3. 组成：必选包（M3→P15；M129→P0|P1+P11；M132/136/147/149/150/157→P0|P1）、
   允许的包/用户包、规则 1-9（同类型包不可重复；P65/P66 例外但同类内 NID_TSR 须互异）。
4. 方向：车→地包不能塞进地→车报文，反之亦然。
5. 条件字段：限定词说"不存在"却给了值 → 失败；该出现却没给值且无协议默认 → 失败。
6. 取值：超出位宽/协议上下限 → 失败；values 里没有被消费的键 → 失败（防拼错）。
7. 语义：P68 `Q_TRACKINIT=1` 失败；CTCS-150 `Q_EOATYPE` 与哨兵填写不一致 → 告警；
   CTCS-152 后车字段填全 F → 告警。

### C.6 已知定长结果（交付核对基线）

生成或反解后，可直接用这张表核对 `L_MESSAGE` 与各包 `L_PACKET`：

| 消息/包 | 断言 |
|---|---|
| M2（无 P63） | L_MESSAGE=12 |
| M6 / M39 / M41 / M154 / M155 / M156 / M159 | L_MESSAGE=10 |
| M8 / M146 | L_MESSAGE=14 |
| M15 | L_MESSAGE=13 |
| M32 | L_MESSAGE=11 |
| M34 | L_MESSAGE=14 |
| P15（N_ITER=0，单区段） | L_PACKET=185 |
| P3 / P57 / P58 / P65 / P66 / P4 / CTCS-136 | 186 / 49 / 56 / 71 / 31 / 29 / 46 |

这些数字来自协议本身，**不是**真机比对：仓库里没有任何 RBC 报文的二进制样本。拿到真机
报文后，请先用 `dump_rbc_msg.py` 反解，把 `L_MESSAGE`、各包 `L_PACKET`、`walk` 与本文
对照。

