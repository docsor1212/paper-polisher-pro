#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_integrity_manifest.py — 生成 data/INTEGRITY_MANIFEST.json（v7.6.0）。

data/ 与 references/ 全部 JSON 的 SHA256+字节数清单。文件内容变更后必须重跑本工具，
否则 pp_doctor --deep 判 FAIL（完整性自证的单一事实源）。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    files = sorted(
        [f"data/{p.name}" for p in (ROOT / "data").glob("*.json")
         if p.name != "INTEGRITY_MANIFEST.json"] +
        [f"references/{p.name}" for p in (ROOT / "references").glob("*.json")]
    )
    manifest = {"_meta": "安装完整性清单（v7.6.0）：data/ 与 references/ 全部 JSON 的 SHA256 与字节数。"
                         "pp_doctor --deep 逐文件核对（哈希+解析双重验证）；发布链打包后对打包副本再核对一次。",
                "generated": "7.6.0",
                "files": {}}
    for rel in files:
        b = (ROOT / rel).read_bytes()
        manifest["files"][rel] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    out = ROOT / "data" / "INTEGRITY_MANIFEST.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"manifest: {len(files)} files -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
