# RBC Simulator — `DataTable` XML Message Format

Reverse-engineered specification of the XML files in `RBC-XML/`, verified against the
RbcSimulator source code.
---

## 1. One-minute summary

A message XML is a **flat, ordered list of bit fields**. Each `<data>` element is one
field of the message as it appears on the wire, in order:

```xml
<?xml version="1.0" encoding="utf-8"?>
<DataTable>
  <data variable="NID_MESSAGE" bits="8"  description="消息标识号" value="24" />
  <data variable="L_MESSAGE"   bits="10" description="消息长度(字节)" value="自动计算不填" />
  ...
</DataTable>
```

* Element order **is** the bit order of the message. There is no other structure.
* `bits` is the field width in bits. Values are written **MSB-first**, big-endian.
* `variable` / `description` are documentation. Only the **position** matters at packing
  time (a handful of names drive GUI behaviour: `NID_MESSAGE`, `L_MESSAGE`,
  `NID_PACKET`, `NID_XUSER`, `N_TRAINNUM`, `L_TEXT`, `X_TEXT(L_TEXT)`).
* Length fields (`L_MESSAGE`, `P##_L_PACKET`, inner `L_PACKET`) are usually stored as the
  literal string `自动计算不填` ("auto-calculated, leave empty") and are overwritten at
  send time with the computed value.

---

## 2. Schema

### 2.1 Grammar

```xml
<?xml version="1.0" encoding="utf-8"?>
<DataTable>
  <data variable="..." bits="..." description="..." value="..." />
  <data ... />
  ...
</DataTable>
```

* Exactly one root element, conventionally `<DataTable>`.
* Zero or more `<data>` children, **in wire order**.
* No namespaces, no attributes on the root, no schema declaration.
* XML comments are allowed (ignored by the loader).

### 2.2 `<data>` attributes

All four attributes are **mandatory**. The loader dereferences
`node.Attributes["..."].Value` without null checks (`Form2.cs:361-364`), so a missing
attribute throws `NullReferenceException` while opening the message.

| Attribute | Type | Required | Meaning | Internal column |
|---|---|---|---|---|
| `variable` | string | yes | Field name (ETCS/CTCS variable, e.g. `NID_PACKET`). Informational; may repeat; may contain spaces (`M_LOC `) and index suffixes (`NID_C(0)`, `N_TRACKCOND(k)`). | `变量` |
| `bits` | integer | yes | Field width in bits, `1..64`. Parsed with `int.Parse`; must be plain decimal. | `位数` (Int32) |
| `description` | string | yes | Human description, usually Chinese. Never parsed. May be empty. | `说明` |
| `value` | string | yes | Field value. Usually decimal; see §4 for exceptions. Must not be empty in a saved file. | `取值` |

Recommended attribute order is the one the simulator's writer emits:
`variable`, `bits`, `description`, `value` (`Form2.cs:2444-2449`). The parser does not care
about attribute order.

### 2.3 XSD (validation aid)

```xml
<?xml version="1.0" encoding="utf-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="DataTable">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="data" minOccurs="1" maxOccurs="unbounded">
          <xs:complexType>
            <xs:attribute name="variable"    type="xs:string" use="required"/>
            <xs:attribute name="bits"        use="required">
              <xs:simpleType>
                <xs:restriction base="xs:positiveInteger">
                  <xs:minInclusive value="1"/>
                  <xs:maxInclusive value="64"/>
                </xs:restriction>
              </xs:simpleType>
            </xs:attribute>
            <xs:attribute name="description" type="xs:string" use="required"/>
            <xs:attribute name="value"       type="xs:string" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
```

The XSD catches structural mistakes only; the semantic rules below (order, counts,
supported packet IDs) are not expressible in XSD.

---

## 3. File-level rules

| Item | Rule |
|---|---|
| Encoding | UTF-8. All supplied examples and files written by the simulator are UTF-8 **with BOM**. `XmlDocument.Load` auto-detects, so BOM is optional, but keep UTF-8. |
| XML version | `1.0`. |
| Root | `<DataTable>`. The loader actually selects `//data` anywhere in the document, so the root name is not enforced (`Form2.cs:358`), but every tool in the project writes `<DataTable>`. |
| File name | Only matters to the GUI: message editor `M<n>` loads `dataTableM<n>.xml` from the **current working directory** (`File.Exists("dataTableM24.xml")`, `Form2.cs:672`). Names such as `523-c80.xml`, `M24-P58.xml` are archives/examples — same format, but nothing auto-loads them by name. |
| Saving | The GUI writes the same format back through `SaveDataTableToFile` (`Form2.cs:2434-2455`); it refuses to save if any `value` is empty. |
| Other XMLs | `config/config.xml` (GB2312, `<root><config>…`) and `lrbg/lrbg.xml` (`<LRBG><LRBG{id}><P5>…`) use unrelated formats. Do not confuse them with this one. |

---

## 4. Value syntax

### 4.1 Ordinary numeric fields

* Plain **unsigned decimal ASCII**: `0`, `24`, `32767`, `4294967295`.
* No hex (`0x…`), no sign, no thousands separators, no units.
* Must fit in `bits` bits: `0 <= value <= 2^bits - 1`.
  There is **no range validation** — an oversized value is silently truncated to the
  low bits by the packing routines. Author-side validation is your responsibility.
* Surrounding whitespace is tolerated by `int.Parse`, but avoid it.
* For `bits` 1–8 → byte conversion; 9–16 → word; 17–32 → dword; 33–64 → qword
  (`Form2.cs:2869-2889`). No field may exceed 64 bits.

### 4.2 "Auto-calculated" placeholders

The literal string:

```
自动计算不填
```

means *"computed at send time, do not fill in"*. It is valid **only** where the packer
skips parsing the value:

| Field | Files where the placeholder is safe |
|---|---|
| `L_MESSAGE` | M3, M24 (their packers skip row 1). M2/M28 also ignore it, but their editors rewrite it with a numeric value. |
| `P##_L_PACKET` (P3, P5, P15, P21, P27, P41, P42, P49, P57, P63, P65, P66, P68, P72, P80, P131) | Any message whose packer has a dedicated routine (all packets dispatched by M2/M3/M24/M28) |
| inner `L_PACKET` of a CTCS packet | Same |
| outer `P44_L_PACKET` | Same |

Do **not** use it in a "simple" message (M6, M15, M16, M18, M27, M32, M33, M34, M39,
M41, M45, …). Those are packed row-by-row by `Pack_Datatable_Message_to_BitArray`
(`Form2.cs:2859-2890`), which parses **every** `value` as an integer.

### 4.3 Special encodings

| Field | Format | Where |
|---|---|---|
| `M_IP_PRE` (64 bits) | Eight dot-separated decimal octets: `172.16.27.100.172.16.28.100` | P44 / CTCS 80 |
| `NID_RADIO` (64 bits) inside CTCS 131 | Eight dot-separated decimal octets: `1.2.3.4.5.6.7.8` | P44 / CTCS 131 |
| `NID_RADIO` (64 bits) in ETCS P131 | Plain 64-bit decimal integer | P131 |
| `X_TEXT(L_TEXT)` | Arbitrary text string. Encoded **GB18030** by default, or **UTF-16BE** when the P72 text-encoding setting is 1 (`Form2.cs:6231-6248`). The `bits` attribute of this row (8 in the templates) is ignored — the packed length is `L_TEXT × 8`. | P72 |
| `L_TEXT` | Byte length of the encoded `X_TEXT` (8-bit field, so max 255 bytes). Recomputed by the GUI when the text cell is edited (`Form2.cs:227-277`); if authoring XML by hand it must match the encoded byte length exactly. | P72 |
| `GROUP_NID_ENGINE(k)` | One row per train, count given by `N_TRAINNUM` (see §6.4) | P44 / CTCS 80 |

### 4.4 Duplicate names are normal

`variable` is **not** a key. The same name appears many times in one file:

* `Q_DIR` appears once in every packet header, plus once more in the inner CTCS header.
* `NID_PACKET` appears once per packet block.
* `NID_C`/`NID_BG` appear in the message header and again in P5/P63/P49 link entries.
* `Q_EOATYPE` appears twice in the TACN variant of CTCS 150.

Never load these rows into a dictionary keyed by `variable`.

---

## 5. Bit-level semantics

### 5.1 Packing order

Fields are packed in document order into one continuous bit stream:

1. Each value is converted to an MSB-first bit array (big-endian for multi-byte values).
2. The low `bits` bits of that representation are appended at the current bit index.
3. Bytes are emitted by taking bit 0 as the most significant bit of byte 0
   (`Form2.cs:2849-2854`, `DataProcess.cs:24-34`, `DataProcess.cs:100-110`).

So the first field in the file is the **first (most significant) bits of the first byte**
on the wire, exactly like the ETCS/CTCS bit-stream notation (e.g. `NID_MESSAGE` is the
first 8 bits of byte 0).

### 5.2 Length units — the classic trap

| Field | Unit | Definition |
|---|---|---|
| `L_MESSAGE` (10 bits) | **bytes** | `ceil(total_message_bits / 8)` |
| `P##_L_PACKET` (13 bits) | **bits** | bits from that packet's `NID_PACKET` through its last packed field |
| inner `L_PACKET` (13 bits) | **bits** | bits from `NID_XUSER` through the last packed field |
| outer `P44_L_PACKET` (13 bits) | **bits** | bits from the outer `NID_PACKET` through the end of the inner packet (i.e. `8+2+13 + inner L_PACKET`) |

`L_PACKET` includes its own 13 bits and the packet header bits. It counts only fields
that are actually **packed** — conditional fields skipped because of a qualifier are
consumed as rows but do not contribute bits.

### 5.3 Trailing padding (observed implementation detail)

The send path initialises its bit buffer with `1`s, not `0`s
(`Enumerable.Repeat<byte>(1, 4000)`, `Form1.cs:1306`). If the message length is not a
multiple of 8, the unused bits of the last byte remain `1`. If you need defined padding,
make sure the field list produces a whole number of bytes.

---

## 6. Message structure

### 6.1 Header

Rows 0..N-1 are the message header; after that come packet blocks (for M2/M3/M24/M28) or
plain fields (simple messages).

**Row 0 must be `NID_MESSAGE` with a numeric value.** The GUI routes an edited table by
reading `Rows[0][3]` and switching on it (`Form1.cs:1223-1279`); if it is not numeric the
save/send path throws.

Layouts used by the simulator's editor (from the fallback templates in `Form2.cs` and the
sample files):

| Message | Header rows after `NID_MESSAGE(8), L_MESSAGE(10), T_TRAIN(32), M_ACK(1), NID_C(10), NID_BG(14)` | Then |
|---|---|---|
| M2 | `Q_SCALE(2), D_SR(15)` | packet blocks P72 / P63 |
| M3 | — | packet blocks (any supported ETCS/CTCS packet) |
| M6 | — | end |
| M8 | `T_TRAIN(32)` (acknowledged timestamp) | end |
| M15 | `NID_EM(4), Q_SCALE(2), Q_DIR(2), D_EMERGENCYSTOP(15)` | end |
| M16 | `NID_EM(4)` | end |
| M18 | `NID_EM(4)` | end |
| M24 | — | packet blocks (same dispatcher as M3) |
| M27 | `T_TRAIN(32)` | end |
| M28 | `T_TRAIN(32)` | packet block P49 |
| M32 | `M_VERSION(7)` | end |
| M33 | `Q_SCALE(2), D_REF(16)` | end |
| M34 | `Q_SCALE(2), Q_DIR(2), D_TAFDISPLAY(15), L_TAFDISPLAY(15)` | end |
| M39 | — | end |
| M41 | — | end |
| M45 | `Q_ORIENTATION(1)` | end |

Only M2, M3, M24 and M28 parse packet blocks; everything else is a flat sequence of
fields. `NID_MESSAGE` is not validated against the file name — keep them consistent
yourself.

### 6.2 Packet blocks

For M3/M24, after the 6 header rows the packer loops:

1. Read the next row's `value` as `NID_PACKET`.
2. Dispatch to that packet's packer, which consumes a **fixed, position-dependent**
   sequence of rows (header `NID_PACKET`, `Q_DIR`, `P##_L_PACKET`, then its fields,
   iteration groups, conditional fields).
3. Repeat until all rows are consumed.

Supported `NID_PACKET` values in the dispatcher (`Form2.cs:4461-4516` for M3,
`4573-4628` for M24; same list in the M2/M28 dispatchers with fewer entries):

| Context | Supported `NID_PACKET` |
|---|---|
| M2 | `72`, `63` |
| M3, M24 | `3`, `5`, `15`, `21`, `27`, `41`, `42`, `44`, `57`, `58`, `65`, `66`, `68`, `72`, `80`, `131` |
| M28 | `49` |

An unsupported value is **not** an error: the dispatcher's `default:` branch consumes
nothing, the outer loop advances by one row, and every following row is misinterpreted as
a packet header. The message is silently corrupted. Only use the IDs above.

> **The XML cannot define new packets.** Row interpretation is hardcoded per packet in C#
> (`Pack_Message_P##_to_BitArray` plus a `switch` case, and for CTCS packets a packer
> plus a `NID_XUSER` branch). Adding a new packet type requires changing the simulator
> code and its GUI template; the file format described here stays the same.

Blocks may appear in any order. Each block must be complete and in the template order
described in Appendix A.

### 6.3 Nested CTCS packets (P44 / `NID_XUSER`)

CTCS custom packets are wrapped in ETCS packet 44:

```
[outer] NID_PACKET(8)=44
        Q_DIR(2)
        P44_L_PACKET(13)            ← auto, bits from NID_PACKET through inner end
        NID_XUSER(9)                ← selects the CTCS packet
[inner] Q_DIR(2)
        L_PACKET(13)                ← auto, bits from NID_XUSER through inner end
        ... CTCS payload ...
```

Supported `NID_XUSER` values (`Form2.cs:6478-6521`):

| `NID_XUSER` | CTCS packet | Notes |
|---|---|---|
| 64 | 列车长度 | `L_TRAIN(15)` |
| 80 | 编组命令 | variable train count, IP address |
| 81 | 编组状态 | `GROUP_ID` only |
| 82 | 解编预告 | `Q_SCALE`, `D_DECOUPLEPOS` |
| 83 | 解编命令 | `GROUP_ID` only |
| 131 | RBC 通信管理 | dotted IP in `NID_RADIO` |
| 132 | 道岔信息 | nested station/switch counts |
| 150 | EOA 点类型 | two variants (see below) |
| 152 | 后车信息 | fixed structure |

51 has a C# template (`Initial_DataTable_P44_C51`) but **no dispatch case** — it cannot be
sent.

**C150 variants.** `Pack_Message_P44_C150_to_BitArray` and
`Pack_Message_P44_C150_TACN_to_BitArray` have different field lists. The simulator picks
the TACN variant when the project combo box selects **TACN** (`project_ID == 2`,
`Form1.cs:8864-8874`). An XML for the TACN variant is recognisable by the **two
`Q_EOATYPE` rows** and the additional `Q_DIR_HANDLE`, `Q_TRACTION_HANDLE`,
`M_HEAD_PRESSURE`, `M_TAIL_PRESSURE`, `KILOMETER_POST` rows (`523-M3.xml` is such a
file). The non-TACN variant has one `Q_EOATYPE` and no handle/pressure/kilometer rows.

### 6.4 Iteration rows

Variable-count sections are expanded physically in the file; the count field tells the
packer how many row groups to consume:

```xml
<data variable="P21_N_ITER" bits="5" description="包含坡度变化点的数量" value="1" />
<data variable="D_GRADIENT(0)" bits="15" ... />
<data variable="Q_GDIR(0)"    bits="1"  ... />
<data variable="G_A(0)"       bits="8"  ... />
```

* The suffix convention is **documentation only**: `(k)` for the first iteration level,
  `(k,m)` for a nested level, or concrete `(0)`, `(1)` as written by the GUI. The packer
  identifies them by position, not by name.
* If the count is `N`, exactly `N` groups must follow, in template order. **If `N = 0`,
  the group rows must be absent entirely** — the template's single example group is only
  an editing placeholder. The GUI deletes/inserts these rows when the count cell is
  edited (`Form2.cs:3285-3355`), and the saved files show the result: `523-M3.xml` has
  `P15_N_ITER=0` with no `L_SECTION(k)` rows, `N_ITER=0` with no `NC_DIFF(n)` rows, while
  `P21_N_ITER=1` carries exactly one `(0)` group. A hand-written file with stray group
  rows and count 0 will be misread: the packer does not skip them.
* Conditional *single* fields (the `?` rows in Appendix A) are different — they must
  always be present, because the packer advances past them positionally even when it does
  not pack them.

Important exceptions:

* **P58** — `Pack_Message_P58_to_BitArray` never loops over `P58_N_ITER`
  (`Form2.cs:5737-5803`). The field must be `0`; there is no way to express trailing
  location entries through this simulator.
* **CTCS 80** — the number of `GROUP_NID_ENGINE(k)` rows must equal `N_TRAINNUM`
  (`MessagePacker.cs:188-197`). The GUI expands/collapses these rows when `N_TRAINNUM`
  is edited (`Form2.cs:3642-3680`); a hand-written file must contain the expanded rows,
  e.g. `N_TRAINNUM=2` → `GROUP_NID_ENGINE(0)` and `GROUP_NID_ENGINE(1)`.
* **CTCS 132** — nested: `N_STACNT` × [ `NID_STA`, `N_TO` × [ `NID_TO`, `Q_TOSTATUS` ] ],
  then a single `N_SIGSTACNT`. The signal-station iteration present in the C# template is
  commented out; the packer only packs the `N_SIGSTACNT` byte
  (`Form2.cs:6693-6735`).

### 6.5 Conditional fields

Fields guarded by a qualifier (`Q_SECTIONTIMER`, `Q_ENDTIMER`, `Q_DANGERPOINT`,
`Q_OVERLAP`, `Q_NEWCOUNTRY`, `Q_CMDTYPE`, …) are **always present as rows**. If the
qualifier says "absent", the packer still advances past the row(s) but does not pack
them, and they do not count toward `L_PACKET`.

Example — P5 in `523-M3.xml` has `Q_NEWCOUNTRY=0` but still carries `NID_C` and `NID_BG`.
`NID_C` is skipped (not packed) because `Q_NEWCOUNTRY=0`; `NID_BG` is packed. Removing
the `NID_C` row would shift every field after it.

Authoring rule: **never delete conditional rows.** Set the qualifier to 0 and leave the
dependent rows in place with any in-range value.

### 6.6 Length calculation recipes

```
packet_bits  = Σ bits of every row from NID_PACKET through the last packed field
               (iteration groups × count; skipped conditional rows excluded)

inner_packet_bits = Σ bits of every row from NID_XUSER through the last packed field
outer_p44_bits    = 8 + 2 + 13 + inner_packet_bits

message_bits = header_bits + Σ packet/payload bits
L_MESSAGE    = ceil(message_bits / 8)      // bytes
P##_L_PACKET = packet_bits                 // bits
L_PACKET     = inner_packet_bits           // bits
```

When the simulator writes the file it usually stores `自动计算不填` in these slots and
computes the real numbers at send time (`Form2.cs:4518-4522` and `4631-4635` for
`L_MESSAGE`; `MessagePacker.cs:227-237` for the P44/CTCS lengths).

The GUI also recomputes `L_MESSAGE` when it opens any table **except M3/M24**, as
`ceil(sum of every row's bits / 8)` (`Form2.cs:288-295`). For simple messages that equals
the packed length; for M2/M28 the packer recomputes it again at send time. M3/M24 keep the
file's value (normally the placeholder).

---

## 7. Annotated examples

### 7.0 What is in `RBC-XML/`

| File | Content |
|---|---|
| `dataTableM2.xml` | M2, header + `Q_SCALE`, `D_SR` (8 rows) |
| `dataTableM3.xml` | M3 with P15 + P21 + P27 |
| `dataTableM6.xml`, `dataTableM15.xml`, `dataTableM16.xml`, `dataTableM18.xml` | Simple messages, flat row list |
| `dataTableM24.xml` | M24 with P58 + P3 |
| `523-M3.xml` | M3 for NID_BG 523: P15 + P21 + P27 + P5 + P44/C150-TACN |
| `523-c80.xml` | M24 + P44/CTCS 80, `N_TRAINNUM = 2` |
| `523-c81.xml` | M24 + P44/CTCS 81 |
| `M24-P58.xml` | M24 + P58 |
| `M24-c82.xml` | M24 + P44/CTCS 82 |
| `M24-c83.xml` | M24 + P44/CTCS 83 |

The name is descriptive only (`dataTableM<n>.xml` is the GUI working file for message
`n`; `523-*`/`M24-*` are archived scenarios). Nothing in the loader derives semantics from
the name.

### 7.1 `523-c80.xml` — M24 carrying CTCS 80 (N_TRAINNUM = 2)

```xml
<DataTable>
  <!-- M24 header: 8 + 10 + 32 + 1 + 10 + 14 = 75 bits -->
  <data variable="NID_MESSAGE" bits="8"  description="消息标识号" value="24" />
  <data variable="L_MESSAGE"   bits="10" description="消息长度(字节)" value="自动计算不填" />
  <data variable="T_TRAIN"     bits="32" description="车载设备时钟" value="3277070" />
  <data variable="M_ACK"       bits="1"  description="确认标识位" value="1" />
  <data variable="NID_C"       bits="10" description="地区编号" value="1018" />
  <data variable="NID_BG"      bits="14" description="应答器标识号" value="523" />

  <!-- P44 wrapper: 8 + 2 + 13 = 23 bits, then inner packet -->
  <data variable="NID_PACKET"   bits="8"  description="信息包标识号" value="44" />
  <data variable="Q_DIR"        bits="2"  description="验证方向" value="2" />
  <data variable="P44_L_PACKET" bits="13" description="信息包位数" value="自动计算不填" />
  <data variable="NID_XUSER"    bits="9"  description="CTCS信息包标识码" value="80" />

  <!-- inner CTCS 80 header: 9 + 2 + 13 = 24 bits -->
  <data variable="Q_DIR"        bits="2"  description="验证方向" value="2" />
  <data variable="L_PACKET"     bits="13" description="信息包位数" value="自动计算不填" />

  <!-- C80 payload -->
  <data variable="GROUP_ID"      bits="32" description="编组ID" value="2" />
  <data variable="N_TRAINNUM"    bits="4"  description="编组列车数量" value="2" />
  <data variable="GROUP_NID_ENGINE(0)" bits="24" description="编组中列车NIDEngine" value="90" />
  <data variable="GROUP_NID_ENGINE(1)" bits="24" description="编组中列车NIDEngine" value="91" />
  <data variable="NID_ENGINE_PRE" bits="24" description="前车NIDEngine" value="90" />
  <data variable="M_IP_PRE"       bits="64" description="前车IP地址"
        value="172.16.27.100.172.16.28.100" />
</DataTable>
```

Computed lengths:

| Quantity | Sum | Value |
|---|---|---|
| header | `8+10+32+1+10+14` | 75 bits |
| C80 payload | `32+4+2×24+24+64` | 172 bits |
| inner `L_PACKET` | `9+2+13+172` | **196** |
| outer `P44_L_PACKET` | `8+2+13+196` | **219** |
| message | `75+219` | 294 bits |
| `L_MESSAGE` | `ceil(294/8)` | **37 bytes** |

### 7.2 `M24-P58.xml` — M24 carrying P58

The packet block is:

```xml
<data variable="NID_PACKET"  bits="8"  description="信息包标识号" value="58" />
<data variable="Q_DIR"       bits="2"  description="验证方向" value="2" />
<data variable="P58_L_PACKET" bits="13" description="信息包位数" value="56" />
<data variable="Q_SCALE"     bits="2"  description="距离/长度分辨率" value="1" />
<data variable="T_CYCLOC"    bits="8"  description="位置报告的时间间隔" value="4" />
<data variable="D_CYCLOC"    bits="15" description="列车在两个位置报告间的距离" value="32767" />
<data variable="M_LOC "      bits="3"  description="列车必须报告其位置的特殊地点/时刻" value="1" />
<data variable="P58_N_ITER"  bits="5"  description="包含列车位置的数量" value="0" />
```

`P58_L_PACKET = 8+2+13+2+8+15+3+5 = 56` bits, which is exactly the numeric value in the
file. Header 75 + 56 = 131 bits → `L_MESSAGE = ceil(131/8) = 17`.

### 7.3 `M24-c82.xml` and `M24-c83.xml`

| File | NID_XUSER | Packed structure | inner `L_PACKET` | outer `P44_L_PACKET` | message bits | `L_MESSAGE` |
|---|---|---|---|---|---|---|
| `M24-c82.xml` | 82 | `GROUP_ID32, Q_SCALE2, D_DECOUPLEPOS15` (`+49`) | `24+49 = 73` | `23+73 = 96` | `75+96 = 171` | **22** |
| `M24-c83.xml` | 83 | `GROUP_ID32` (`+32`) | `24+32 = 56` | `23+56 = 79` | `75+79 = 154` | **20** |
| `523-c81.xml` | 81 | `GROUP_ID32` (`+32`) | 56 | 79 | 154 | **20** |

The wrapper bits are always `23 + 24 = 47` before the payload.

### 7.4 `523-M3.xml` — M3 with P15 + P21 + P27 + P5 + P44/C150-TACN

Row order is exactly the concatenation of the packet templates (Appendix A). Things worth
noticing:

* `Q_DIR` is `1` in every packet header and inner CTCS header in this file (nominal
  direction); `523-c80.xml` uses `2` (both directions). `Q_DIR` is a normal 2-bit value
  and is **not** auto-filled.
* P15 has `P15_N_ITER = 0` and therefore **no** `L_SECTION(k)` rows: with count 0 the
  packer consumes no group rows, so the next row (`L_ENDSECTION`) is the next real field.
* P21 has `P21_N_ITER = 1` and one expanded group `D_GRADIENT(0), Q_GDIR(0), G_A(0)`.
* P27 has `N_ITER = 0` (train-type group — no `NC_DIFF/V_DIFF` rows present) followed by
  `P27_N_ITER = 1` (speed-change group) and its expanded `(0)` row group.
* P5 has `Q_NEWCOUNTRY = 0`; `NID_C` is present but not packed. P5 contributes
  69 bits, not 79, because the 10-bit `NID_C` is skipped.
* The last block is P44 / C150 **TACN** (`NID_XUSER=150`, two `Q_EOATYPE` rows, handle and
  pressure fields, kilometer post).
* Total: header 75 + P15 66 + P21 78 + P27 86 + P5 69 + P44/C150-TACN 279 = 653 bits →
  `L_MESSAGE = ceil(653/8) = 82` bytes.
* Note that a naive sum of every `bits` attribute in the file gives **782**, not 653. The
  129-bit difference is exactly the skipped conditional rows: P15's four optional
  blocks (`25 + 25 + 22 + 47 = 119`) plus P5's `NID_C` (10). This is why length must be
  computed along the same pack path, not by summing the XML.

### 7.5 A "simple" message — `dataTableM15.xml`

No packet dispatch; every row is packed in order:

```xml
NID_MESSAGE(8) L_MESSAGE(10) T_TRAIN(32) M_ACK(1) NID_C(10) NID_BG(14)
NID_EM(4) Q_SCALE(2) Q_DIR(2) D_EMERGENCYSTOP(15)
```

`75+4+2+2+15 = 98` bits → `L_MESSAGE = 13`. The `13` in the file is numeric, not a
placeholder, because the generic packer parses all values.

---

## 8. Authoring checklist

1. **Encoding/root**: UTF-8, `<?xml version="1.0" encoding="utf-8"?>`, `<DataTable>`,
   `<data …/>` children with all four attributes.
2. **Row 0** is `NID_MESSAGE(8)` with the numeric message type.
3. **Header** matches §6.1 for that message type, in the exact order and widths. Keep
   `L_MESSAGE` as `自动计算不填` only for M3/M24.
4. **Packets**: for M3/M24 start each block with `NID_PACKET(8), Q_DIR(2), P##_L_PACKET(13)`
   and follow Appendix A exactly. Block order is free; block internal order is not.
5. **Supported IDs only** — an unknown `NID_PACKET`/`NID_XUSER` is consumed as ordinary
   rows and corrupts everything after it.
6. **Never delete conditional single-field rows** (`?` in Appendix A); the packer always
   advances past their position, whether or not it packs them.
7. **Expand iterations exactly**: `N` count ⇒ `N` row groups, in order, with no group rows
   at all when `N = 0`. For C80, `N_TRAINNUM` ⇒ that many `GROUP_NID_ENGINE(k)` rows.
8. **Values fit the width**: `0 ≤ value < 2^bits`. Use dotted 8-octet form only for the
   fields listed in §4.3.
9. **Special strings**: `自动计算不填` only in auto-length slots; P72 `L_TEXT` must equal
   the encoded byte length of `X_TEXT`.
10. **Validate lengths** with the formulas in §6.6. A mismatch does not fail at load time;
    the packer overwrites the fields, but a structurally wrong row count shifts and
    corrupts the message.
11. **Empty `value` is invalid** for saved files; the GUI refuses to save such a table.

---

## 9. Common failure modes

| Symptom | Likely cause |
|---|---|
| `NullReferenceException` while opening the message | One `<data>` lacks `variable`, `bits`, `description` or `value`. |
| `FormatException` on send | A non-numeric `value` in a simple (generic-packed) message, e.g. `自动计算不填` in M6/M15/…. Values > 2^64 also throw. |
| Message opens but everything after a point is garbage | Unsupported `NID_PACKET`/`NID_XUSER` (dispatcher `default:` skips one row, then misreads the rest), or a missing/extra conditional/iteration row. |
| Wrong length field on the wire | Hand-edited `L_MESSAGE`/`L_PACKET` used in a code path that does not recompute it, or unit confusion: `L_MESSAGE` is **bytes**, `L_PACKET` is **bits**. |
| `L_MESSAGE` too small / truncated | Author computed bits instead of bytes, or omitted iteration groups from the sum. |
| Text garbled at the receiver | `X_TEXT` written as UTF-8 instead of the configured GB18030/UTF-16BE, or `L_TEXT` not equal to the encoded byte count. |
| P58 trailing location entries ignored | The P58 packer does not loop; keep `P58_N_ITER = 0`. |
| C150 layout mismatch | TACN project selected or not: TACN uses two `Q_EOATYPE` rows plus handle/pressure/kilometer fields. |

---

# Appendix A — Packet field catalog

Notation: fields are listed in **row order**; `Name(bits)`. `×` marks an iteration
group whose count comes from the preceding `N_ITER`-style field — when the count is `0`,
no group rows are present. `?` marks a conditional field row that is always present but
packed only when its qualifier holds. Template defaults are in `Form2.cs`
(`Initial_DataTable_*`); packers are in `Form2.cs` / `MessagePacker.cs`.

### P3 — National values (ETCS 3)
```
NID_PACKET(8) Q_DIR(2) P3_L_PACKET(13) Q_SCALE(2) D_VALIDNV(15) P3_N_ITER(5)
  ×NID_C(k)(10)
V_NVSHUNT(7) V_NVSTFF(7) V_NVONSIGHT(7) V_NVUNFIT(7) V_NVREL(7) D_NVROLL(15)
Q_NVSRBKTRG(1) Q_NVEMRRLS(1) V_NVALLOWOVTRP(7) V_NVSUPOVTRP(7) D_NVOVTRP(15)
T_NVOVTRP(8) D_NVPOTRP(15) M_NVCONTACT(2) T_NVCONTACT(8) M_NVDERUN(1)
D_NVSTFF(15) Q_NVDRIVER_ADHES(1)
```

### P5 — Linking
```
NID_PACKET(8) Q_DIR(2) P5_L_PACKET(13) Q_SCALE(2) D_LINK(15) Q_NEWCOUNTRY(1)
  ?NID_C(10)                    packed only if Q_NEWCOUNTRY = 1
NID_BG(14) Q_LINKORIENTATION(1) Q_LINKREACTION(2) Q_LOCACC(6) P5_N_ITER(5)
  ×[ D_LINK(k)(15) Q_NEWCOUNTRY(k)(1) ?NID_C(k)(10) NID_BG(k)(14)
     Q_LINKORIENTATION(k)(1) Q_LINKREACTION(k)(2) Q_LOCACC(k)(6) ]
```

### P15 — MA / LOA
```
NID_PACKET(8) Q_DIR(2) P15_L_PACKET(13) Q_SCALE(2) V_LOA(7) T_LOA(10) P15_N_ITER(5)
  ×[ L_SECTION(k)(15) Q_SECTIONTIMER(k)(1)
     ?[ T_SECTIONTIMER(k)(10) D_SECTIONTIMERSTOPLOC(k)(15) ] ]
L_ENDSECTION(15)
Q_SECTIONTIMER(1)   ?[ T_SECTIONTIMER(10) D_SECTIONTIMERSTOPLOC(15) ]
Q_ENDTIMER(1)       ?[ T_ENDTIMER(10) D_ENDTIMERSTARTLOC(15) ]
Q_DANGERPOINT(1)    ?[ D_DP(15) V_RELEASEDP(7) ]
Q_OVERLAP(1)        ?[ D_STARTOL(15) T_OL(10) D_OL(15) V_RELEASEOL(7) ]
```

### P21 — Gradient
```
NID_PACKET(8) Q_DIR(2) P21_L_PACKET(13) Q_SCALE(2) D_GRADIENT(15) Q_GDIR(1) G_A(8)
P21_N_ITER(5)
  ×[ D_GRADIENT(k)(15) Q_GDIR(k)(1) G_A(k)(8) ]
```

### P27 — Static speed profile
```
NID_PACKET(8) Q_DIR(2) P27_L_PACKET(13) Q_SCALE(2) D_STATIC(15) V_STATIC(7) Q_FRONT(1)
N_ITER(5)
  ×[ NC_DIFF(n)(4) V_DIFF(n)(7) ]
P27_N_ITER(5)
  ×[ D_STATIC(k)(15) V_STATIC(k)(7) Q_FRONT(k)(1) N_ITER(k,m)(5)
      ×[ NC_DIFF(k,m)(4) V_DIFF(k,m)(7) ] ]
```

### P41 — Level transition
```
NID_PACKET(8) Q_DIR(2) P41_L_PACKET(13) Q_SCALE(2) D_LEVELTR(15) M_LEVELTR(3)
  ?NID_STM(8)                   when M_LEVELTR = 1
L_ACKLEVELTR(15) P41_N_ITER(5)
  ×[ M_LEVELTR(k)(3) ?NID_STM(k)(8) L_ACKLEVELTR(k)(15) ]
```

### P42 — RBC session management
```
NID_PACKET(8) Q_DIR(2) P42_L_PACKET(13) Q_RBC(1) NID_C(10) NID_RBC(14) NID_RADIO(64)
Q_SLEEPSESSION(1)
```

### P57 — Request to shorten MA
```
NID_PACKET(8) Q_DIR(2) P57_L_PACKET(13) T_MAR(8) T_TIMEOUTRQST(10) T_CYCRQST(8)
```

### P58 — Position report parameters
```
NID_PACKET(8) Q_DIR(2) P58_L_PACKET(13) Q_SCALE(2) T_CYCLOC(8) D_CYCLOC(15) M_LOC(3)
P58_N_ITER(5)
```
**The packer never loops.** Keep `P58_N_ITER = 0`; no trailing `D_CYCLOC(k)/M_LOC(k)` rows.

### P63 / P49 — Linking (limited)
```
NID_PACKET(8) Q_DIR(2) P##_L_PACKET(13) P##_N_ITER(5)
  ×[ Q_NEWCOUNTRY(k)(1) ?NID_C(k)(10) NID_BG(k)(14) ]
```
P63 is dispatched by M2, P49 by M28.

### P65 / P66 — Temporary speed restriction
```
P65: NID_PACKET(8) Q_DIR(2) P65_L_PACKET(13) Q_SCALE(2) NID_TSR(8) D_TSR(15)
     L_TSR(15) Q_FRONT(1) V_TSR(7)
P66: NID_PACKET(8) Q_DIR(2) P66_L_PACKET(13) NID_TSR(8)
```

### P68 — Track condition
```
NID_PACKET(8) Q_DIR(2) P68_L_PACKET(13) Q_SCALE(2) Q_TRACKINIT(1)
  Q_TRACKINIT = 0:
      D_TRACKINIT(15)                          ← row present, skipped (not packed)
      D_TRACKCOND(15) L_TRACKCOND(15) M_TRACKCOND(4) P68_N_ITER(5)
        ×[ D_TRACKCOND(k)(15) L_TRACKCOND(k)(15) M_TRACKCOND(k)(4) ]
  Q_TRACKINIT = 1:
      D_TRACKINIT(15)                          ← packed, then the packer returns
```
The template spells the field `L_ TRACKCOND` with an accidental space; only its position
matters.

Practical note: the GUI always keeps the whole row set in the table (it only manages the
`(k)` groups). With `Q_TRACKINIT = 1` the packer stops after `D_TRACKINIT`, leaving the
later rows unconsumed, and the M3/M24 dispatcher then misreads them. Keep
`Q_TRACKINIT = 0`.

### P72 — Text message
```
NID_PACKET(8) Q_DIR(2) P72_L_PACKET(13) Q_SCALE(2) Q_TEXTCLASS(2) Q_TEXTDISPLAY(1)
D_TEXTDISPLAY(15) M_MODETEXTDISPLAY(4) M_LEVELTEXTDISPLAY(3) ?NID_STM(8)
L_TEXTDISPLAY(15) T_TEXTDISPLAY(10) M_MODETEXTDISPLAY_END(4) M_LEVELTEXTDISPLAY_END(3)
?NID_STM(8) Q_TEXTCONFIRM(2) L_TEXT(8) X_TEXT(L_TEXT bytes)
```
`NID_STM` is packed only when its preceding `M_LEVELTEXTDISPLAY*` equals 1.
`L_TEXT` is the encoded byte count of `X_TEXT`; `X_TEXT`'s own `bits` attribute is ignored.

### P80 — Mode profile
```
NID_PACKET(8) Q_DIR(2) P80_L_PACKET(13) Q_SCALE(2) D_MAMODE(15) M_MAMODE(2)
V_MAMODE(7) L_MAMODE(15) L_ACKMAMODE(15) P80_N_ITER(5)
  ×[ D_MAMODE(k)(15) M_MAMODE(k)(2) V_MAMODE(k)(7) L_MAMODE(k)(15) L_ACKMAMODE(k)(15) ]
```

### P131 — RBC transition
```
NID_PACKET(8) Q_DIR(2) P131_L_PACKET(13) Q_SCALE(2) D_RBCTR(15) NID_C(10) NID_RBC(14)
NID_RADIO(64, decimal) Q_SLEEPSESSION(1)
```

### P44 — CTCS wrapper
```
NID_PACKET(8) Q_DIR(2) P44_L_PACKET(13) NID_XUSER(9)
  Q_DIR(2) L_PACKET(13) <CTCS payload>
```

#### CTCS 64 — Train length
```
NID_XUSER(9)=64 Q_DIR(2) L_PACKET(13) L_TRAIN(15)
```

#### CTCS 80 — Formation command
```
NID_XUSER(9)=80 Q_DIR(2) L_PACKET(13)
GROUP_ID(32) N_TRAINNUM(4)
  × GROUP_NID_ENGINE(k)(24)       exactly N_TRAINNUM rows (none when 0)
NID_ENGINE_PRE(24) M_IP_PRE(64, 8 dotted octets)
```

#### CTCS 81 — Formation status
```
NID_XUSER(9)=81 Q_DIR(2) L_PACKET(13) GROUP_ID(32)
```

#### CTCS 82 — Decoupling announcement
```
NID_XUSER(9)=82 Q_DIR(2) L_PACKET(13) GROUP_ID(32) Q_SCALE(2) D_DECOUPLEPOS(15)
```

#### CTCS 83 — Decoupling command
```
NID_XUSER(9)=83 Q_DIR(2) L_PACKET(13) GROUP_ID(32)
```

#### CTCS 131 — RBC communication management
```
NID_XUSER(9)=131 Q_DIR(2) L_PACKET(13) Q_SCALE(2) Q_CMDTYPE(1)
  ?Q_RBC(1)                          packed when Q_CMDTYPE = 0
  ?D_RBCTR(15)                       packed when Q_CMDTYPE = 1
NID_C(10) NID_RBC(14) NID_RADIO(64, 8 dotted octets) Q_SLEEPSESSION(1)
```
Both `Q_RBC` and `D_RBCTR` rows are always present; one is skipped based on `Q_CMDTYPE`.

#### CTCS 132 — Switch information
```
NID_XUSER(9)=132 Q_DIR(2) L_PACKET(13) N_STACNT(8)
  ×[ NID_STA(16) N_TO(5)
      ×[ NID_TO(8) Q_TOSTATUS(2) ] ]
N_SIGSTACNT(8)
```
The packer does not iterate signal stations; only the `N_SIGSTACNT` byte is packed.

#### CTCS 150 — EOA point type (non-TACN)
```
NID_XUSER(9)=150 Q_DIR(2) L_PACKET(13) Q_EOATYPE(8) NID_ENGINE(24)
NID_OPERATIONAL(32) V_TRAIN(16) RESREVED(32) RESREVED(32)
```

#### CTCS 150 — TACN variant
```
NID_XUSER(9)=150 Q_DIR(2) L_PACKET(13) Q_EOATYPE(8) Q_EOATYPE(8) NID_ENGINE(24)
NID_OPERATIONAL(32) V_TRAIN(16) Q_DIR_HANDLE(8) Q_TRACTION_HANDLE(8)
M_HEAD_PRESSURE(16) M_TAIL_PRESSURE(16) KILOMETER_POST(32)
RESREVED(32) RESREVED(32)
```

#### CTCS 152 — Following train information
```
NID_XUSER(9)=152 Q_DIR(2) L_PACKET(13) NID_ENGINE(24) NID_OPERATIONAL(32) V_TRAIN(16)
Q_DIR_HANDLE(8) Q_TRACTION_HANDLE(8) M_HEAD_PRESSURE(16) M_TAIL_PRESSURE(16)
KILOMETER_POST(32) RESERVED1(32) RESERVED2(32)
```

---

# Appendix B — Where the format is enforced in code

| Concern | Location |
|---|---|
| Load `<data>` rows into the table | `Form2.cs:355-367` (and one copy per message editor) |
| Save table to XML | `Form2.cs:2434-2455` |
| Mandatory attribute dereference | `Form2.cs:361-364` |
| Column names: 变量 / 位数 / 说明 / 取值 | `Form2.cs:350-353` |
| Auto `L_MESSAGE` for simple messages | `Form2.cs:279-296` |
| Generic sequential packer | `Form2.cs:2859-2890` |
| Bit primitive: MSB-first append | `DataProcess.cs:24-34` |
| Byte/word/dword/qword → bits | `DataProcess.cs:100-298` |
| M2 header + dispatch | `Form2.cs:4258-4338` |
| M28 header + P49 | `Form2.cs:4340-4411` |
| M3 header + dispatch | `Form2.cs:4413-4523` |
| M24 header + dispatch | `Form2.cs:4525-4636` |
| P44 dispatch / `NID_XUSER` | `Form2.cs:6454-6521` (send copy: `Form1.cs:8828-8895`) |
| CTCS 80/81/82/83/152 packers | `MessagePacker.cs:21-422` |
| P58 packer (no iteration) | `Form2.cs:5737-5803` |
| C80 `N_TRAINNUM` row expansion | `Form2.cs:3642-3680` |
| P72 text encoding / `L_TEXT` | `Form2.cs:6112-6258`, `Form2.cs:227-277` |
| Message-type routing from row 0 | `Form1.cs:1223-1279` |
| Project selection (TACN vs CN) | `Form1.cs:9737-9751`, used at `Form1.cs:8864-8874` |
