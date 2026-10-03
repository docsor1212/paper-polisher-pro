#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pp_setup.py — 监督层模型一键装模（v4.5.0 新增）

官方评测 usability 项的正面回应：此前装模需手动放置文件到特定路径、多步操作无校验；
本命令把「校验指纹 → 安装 → 推理自检」收成一步，装错/装假当场拦截。

用法：
  python3 scripts/pp_setup.py --model <作者签发的 model.onnx> [--tokenizer <tokenizer.json>]
  python3 scripts/pp_setup.py --check          # 仅查看当前装模状态

行为：
  1. 计算模型文件 md5 前 12 位，与 references/supervised_models.json 注册表比对——
     未登记指纹一律拒绝安装（exit 2）：监督层是计分核心，不接受来历不明的权重
     （官方文档「Do not substitute other exports」的机器化）。
  2. tokenizer 校验：提供则比对注册表指纹；未提供且缓存已有同指纹 tokenizer 则沿用。
  3. 安装到 ~/.cache/paper-polisher/qwen3-detector/{model.int8.onnx, tokenizer.json}。
  4. 推理自检：变长金丝雀直接调 layers_lm（坏图/坏环境当场暴露，不做无验证交付）。
  5. 输出 GREEN/RED 摘要。exit 0=成功, 1=自检失败, 2=指纹/tokenizer 未登记或参数解析失败(argparse 约定), 3=参数/文件缺失。

零网络：本命令不下载任何文件——模型永远来自作者渠道的本地文件。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE.parent / "references" / "supervised_models.json"
CACHE = Path.home() / ".cache" / "paper-polisher" / "qwen3-detector"


def md5_12(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        return 0
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--model", default=None)
    ap.add_argument("--tokenizer", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.check:
        return status()

    if not a.model:
        print("ERROR: 需要 --model <作者签发的模型文件>（或 --check 查看当前状态）")
        return 3
    model_p = Path(a.model)
    if not model_p.is_file():
        print("ERROR: 模型文件不存在: %s" % model_p)
        return 3

    reg = json.load(open(REG, encoding="utf-8"))
    known = {m["md5_12"]: m for m in reg.get("models", [])}
    fp = md5_12(model_p)
    entry = known.get(fp)
    if entry is None:
        print("REJECTED: 模型指纹 %s 不在作者签发注册表中（仅接受 %s）" %
              (fp, ", ".join(known) or "空"))
        print("  监督层是计分核心——不接受来历不明的权重；请从作者渠道重新获取。")
        return 2
    print("[1/4] 指纹校验 PASS: %s (模型 %s, %s)" %
          (fp, entry.get("id"), entry.get("note", "")[:60]))

    cache_tok = CACHE / "tokenizer.json"
    if a.tokenizer:
        tok_p = Path(a.tokenizer)
        if not tok_p.is_file():
            print("ERROR: tokenizer 文件不存在: %s" % tok_p)
            return 3
        want = entry.get("tokenizer_md5_12")
        got = md5_12(tok_p)
        if want and got != want:
            print("REJECTED: tokenizer 指纹 %s != 注册表 %s（与模型 %s 不配对）" %
                  (got, want, entry.get("id")))
            return 2
    elif cache_tok.is_file() and (not entry.get("tokenizer_md5_12")
                                  or md5_12(cache_tok) == entry["tokenizer_md5_12"]):
        tok_p = cache_tok  # 指纹匹配, 沿用
    else:
        print("ERROR: 需要 --tokenizer <tokenizer.json>（缓存无配对 tokenizer）")
        return 3
    print("[2/4] tokenizer 校验 PASS: %s" % md5_12(tok_p))

    CACHE.mkdir(parents=True, exist_ok=True)
    for src, dst in ((model_p, CACHE / "model.int8.onnx"), (tok_p, CACHE / "tokenizer.json")):
        if not (dst.exists() and os.path.samefile(src, dst)):
            shutil.copy2(src, dst)
    print("[3/4] 安装完成: %s" % CACHE)

    sys.path.insert(0, str(HERE))
    import layers_lm
    canary = layers_lm.supervised_layer("装模自检金丝雀文本。" * 20)
    if canary is None:
        print("RED: 推理自检失败（supervised_layer 返回 None）——"
              "模型文件与运行环境不兼容，引擎将回退纯规则档。")
        return 1
    print("[4/4] 推理自检 PASS: n_tokens=%d p_ai_any=%.3f" %
          (canary["n_tokens"], canary["p_ai_any"]))
    print("GREEN: 监督层 %s（md5 %s）已就位, 引擎完整档生效。"
          "可运行 python3 pp_doctor.py 做全量自检。" % (entry.get("id"), fp))
    return 0


def status():
    onnx_p = CACHE / "model.int8.onnx"
    tok_p = CACHE / "tokenizer.json"
    if not onnx_p.is_file():
        print("降级档：未安装监督模型（纯规则+词频谱）。"
          "安装：python3 scripts/pp_setup.py --model <作者签发的模型文件>")
        return 0
    fp = md5_12(onnx_p)
    reg = json.load(open(REG, encoding="utf-8"))
    entry = {m["md5_12"]: m for m in reg.get("models", [])}.get(fp)
    print("已安装: md5_12=%s | 注册表=%s | tokenizer=%s" %
          (fp, entry.get("id") if entry else "未知指纹（非作者签发？）",
           "在位" if tok_p.is_file() else "缺失"))
    sys.path.insert(0, str(HERE))
    import layers_lm
    canary = layers_lm.supervised_layer("状态自检金丝雀文本。" * 20)
    print("推理自检: %s" % ("PASS" if canary else "FAIL（None——模型图或环境异常）"))
    return 0 if canary else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
