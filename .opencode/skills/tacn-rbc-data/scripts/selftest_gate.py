#!/usr/bin/env python3
"""生成门禁（intent + provenance）的可执行回归。

验证的是“违规路径必须失败”，而不是生成结果：
  * 缺 intent / confirmed 不为 true / 包顺序不符 / target 不匹配 → exit 1；
  * 缺 provenance 段、来源非法、多余键、字段未标注 → exit 1；
  * 占位值未授权 → exit 1，加 --allow-placeholder → exit 0 且打印占位清单；
  * --set 覆盖的字段自动记为 user；
  * --describe 骨架直接复制 → exit 1；
  * dump_rbc_msg.py --values-out 导出的文件能直接回喂生成器。

用法：python <skill-dir>/scripts/selftest_gate.py
"""

import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dump_rbc_msg as D  # noqa: E402
import gen_rbc_msg as G  # noqa: E402
import gen_rbc_sim_xml as C  # noqa: E402
import rbc_spec as S  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print("ok    %s" % name)
    else:
        FAILS.append("%s%s" % (name, ("：" + detail) if detail else ""))
        print("FAIL  %s%s" % (name, ("：" + detail) if detail else ""))


def run(func, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = func(argv)
    return code, out.getvalue(), err.getvalue()


def base_doc():
    return {
        "M3": {
            "intent": {"message": "M3", "target": "both",
                       "packets": ["P15", "P21"], "confirmed": True},
            "provenance": {"header": "user", "P15": "user", "P21": "user"},
            "header": {"T_TRAIN": 34655, "M_ACK": 1, "NID_LRBG": 16681259},
            "packets": [
                {"packet": "P15", "fields": {
                    "Q_DIR": 1, "Q_SCALE": 1, "L_ENDSECTION": 3000,
                    "V_RELEASEDP": 127}},
                {"packet": "P21", "fields": {
                    "Q_DIR": 1, "Q_SCALE": 1, "N_ITER": 0}},
            ],
        },
    }


def write_doc(root, name, doc):
    path = os.path.join(root, name + ".json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return path


def expect_fail(root, name, doc, needle, extra=None, func=None):
    func = func or G.main
    path = write_doc(root, name, doc)
    argv = ["--values", path, "-o", os.path.join(root, name + "_out")]
    argv.extend(extra or [])
    code, _out, err = run(func, argv)
    check(name + " → exit 1", code == 1, "实际 exit %r" % code)
    check(name + " → 报错含 %r" % needle, needle in err,
          (err.strip().splitlines() or ["<无 stderr>"])[-1][:160])


def main():
    S.ensure_utf8_stdio()
    root = tempfile.mkdtemp(prefix="rbc-gate-")
    try:
        doc = base_doc()
        d = copy.deepcopy(doc)
        d["M3"] = _drop(d["M3"], "intent")
        expect_fail(root, "缺 intent", d, "缺少 intent")

        d = copy.deepcopy(doc)
        d["M3"]["intent"]["confirmed"] = False
        expect_fail(root, "未确认", d, "confirmed")

        d = copy.deepcopy(doc)
        d["M3"]["intent"]["packets"] = ["P15"]
        expect_fail(root, "包顺序不符", d, "intent.packets")

        d = copy.deepcopy(doc)
        d["M3"]["intent"]["target"] = "hex"
        expect_fail(root, "target 不匹配", d, "不能用来生成 sim-xml", func=C.main)

        d = copy.deepcopy(doc)
        d["M3"]["provenance"] = {}
        expect_fail(root, "缺 provenance 段", d, "provenance 缺少")

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P15"] = "example"
        expect_fail(root, "来源非法", d, "不合法")

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P21"] = {"*": "user", "G_A": "user"}
        expect_fail(root, "多余字段键", d, "不在该段取值里")

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P21"] = "placeholder"
        expect_fail(root, "占位未授权", d, "占位字段")

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P21"] = {"Q_SCALE": "placeholder"}
        expect_fail(root, "字段级漏标注", d, "没有给字段")

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P21"] = "placeholder"
        path = write_doc(root, "占位授权", d)
        out_dir = os.path.join(root, "占位授权_out")
        code, out, err = run(G.main, ["--values", path, "-o", out_dir,
                                      "--allow-placeholder"])
        check("占位授权 → exit 0", code == 0, err[-200:])
        check("占位授权 → 打印审计行", "审计:" in out and "占位 3" in out, out[-200:])
        check("占位授权 → 打印占位清单", "占位: P21.Q_SCALE" in out, out[-200:])
        check("占位授权 → 写出 M3.hex",
              os.path.isfile(os.path.join(out_dir, "M3.hex")))

        d = copy.deepcopy(doc)
        d["M3"]["provenance"]["P21"] = {"G_A#1": "placeholder", "*": "user"}
        path = write_doc(root, "set 覆盖", d)
        out_dir = os.path.join(root, "set 覆盖_out")
        code, out, err = run(G.main, ["--values", path, "-o", out_dir,
                                      "--set", "M3.P21.G_A#1=2"])
        check("--set 覆盖占位字段 → exit 0", code == 0, err[-200:])
        check("--set 覆盖后审计无占位", "占位 0" in out, out[-200:])

        skeleton = G._describe_skeleton(S.resolve_message("M3"))
        body = skeleton["M3"]
        check("--describe 骨架 confirmed=false", body["intent"]["confirmed"] is False)
        check("--describe 骨架值为 <待确认>",
              body["header"].get("T_TRAIN") == "<待确认>")
        path = write_doc(root, "骨架", skeleton)
        code, _out, err = run(G.main, ["--values", path, "-o",
                                       os.path.join(root, "骨架_out")])
        check("骨架直接生成 → exit 1", code == 1)
        check("骨架直接生成 → 报 confirmed", "confirmed" in err, err[-200:])

        hex_path = os.path.join(root, "占位授权_out", "M3.hex")
        exported = os.path.join(root, "captured.json")
        code, _out, err = run(D.main, [hex_path, "--values-out", exported])
        check("--values-out → exit 0", code == 0, err[-200:])
        captured = json.load(io.open(exported, encoding="utf-8"))
        check("--values-out 带 intent",
              captured.get("M3", {}).get("intent", {}).get("confirmed") is True)
        check("--values-out provenance 为 decoded",
              captured.get("M3", {}).get("provenance", {}).get("header") == "decoded")
        code, out, err = run(G.main, ["--values", exported, "-o",
                                      os.path.join(root, "回喂_out")])
        check("导出文件直接回喂 → exit 0", code == 0, err[-300:])
        check("回喂审计含解码来源", "解码" in out and "占位 0" in out, out[-200:])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("")
    if FAILS:
        print("失败 %d 项：" % len(FAILS))
        for text in FAILS:
            print("  - %s" % text)
        return 1
    print("全部通过")
    return 0


def _drop(mapping, key):
    out = copy.deepcopy(mapping)
    out.pop(key, None)
    return out


if __name__ == "__main__":
    sys.exit(main())
