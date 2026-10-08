#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pp.py — paper-polisher-pro 统一命令入口（v4.9.0 新增）

多脚本入口导航成本高：一个入口路由全部子命令，
参数原样透传给对应脚本（用法 = 各脚本自己的 --help）。

用法：
  python3 scripts/pp.py <子命令> [参数...]
  python3 scripts/pp.py            # 列出全部子命令

示例：
  python3 scripts/pp.py detect draft.txt --format json
  python3 scripts/pp.py workflow draft.txt
  python3 scripts/pp.py doctor
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

COMMANDS = {
    "detect": ("ai_detector.py", "AI 率检测（单文件或 --batch 目录 + --recursive/--csv）"),
    "gate": ("deai_gate.py", "四层降AI门禁（词级/文体/翻译腔/术语 → 复合分）"),
    "workflow": ("pp_workflow.py", "端到端自查工作流（Markdown + JSON 报告）"),
    "term": ("term_check.py", "术语保护检查（--auto-fix 可自动修复）"),
    "smell": ("translation_smell_check.py", "翻译腔检查（--json）"),
    "style": ("style_distance.py", "文体距离/人类相似度（--json）"),
    "quality": ("quality_report.py", "综合质量报告"),
    "aigc": ("aigc_label_check.py", "AIGC 合规标识检查（docx/pdf/图片/文本）"),
    "paragraph": ("paragraph_report.py", "段落级归因（HTML 报告）"),
    "setup": ("pp_setup.py", "监督层一键装模（--model / --check）"),
    "doctor": ("pp_doctor.py", "环境自检（能跑吗/跑哪档）"),
}


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print("paper-polisher-pro 统一入口（v4.9.0）\n")
        width = max(len(k) for k in COMMANDS)
        for k, (_, desc) in COMMANDS.items():
            print("  %-{w}s  %s".format(w=width) % (k, desc) if False else
                  "  %-*s  %s" % (width, k, desc))
        print("\nPython SDK: import pp_api（无 CLI；编程接口见 SKILL.md § Python API）")
        print("提示：各子命令的参数同原脚本，例如 pp.py detect draft.txt --format json")
        return 0
    cmd = args[0]
    if cmd == "api":
        print("Python SDK 无 CLI：import pp_api（见 SKILL.md § Python API）")
        return 0
    if cmd not in COMMANDS:
        print("未知子命令: %s（可用：%s）" % (cmd, " ".join(COMMANDS)), file=sys.stderr)
        return 2
    script, _ = COMMANDS[cmd]
    p = subprocess.run([sys.executable, str(HERE / script)] + args[1:])
    return p.returncode


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
