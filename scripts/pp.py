#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pp.py — paper-polisher-pro 统一命令入口（v4.9.0 新增；v5.0.0 扩至 15 子命令）

多脚本入口导航成本高：一个入口路由全部子命令，
参数原样透传给对应脚本（用法 = 各脚本自己的 --help）。

用法：
  python3 scripts/pp.py <子命令> [参数...]
  python3 scripts/pp.py            # 列出全部子命令

示例：
  python3 scripts/pp.py detect draft.txt --format json
  python3 scripts/pp.py fix draft.txt --top 10   # 句子级改写建议（v5.0.0）
  python3 scripts/pp.py quickstart               # 零模型零文件一键体验（v5.0.0）
  python3 scripts/pp.py test                     # 包内单元测试（v5.0.0）
  python3 scripts/pp.py verify                   # 结构化零网络自证（v5.0.0）
  python3 scripts/pp.py workflow draft.txt
  python3 scripts/pp.py doctor
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

COMMANDS = {
    "detect": ("ai_detector.py", "AI 率检测（单文件或 --batch 目录 + --recursive/--csv）"),
    "gate": ("deai_gate.py", "四层降AI门禁（词级/文体/翻译腔/术语 → 复合分）"),
    "fix": ("pp_fix_suggest.py", "句子级改写建议（指位+策略，不代改；v5.0.0）"),
    "workflow": ("pp_workflow.py", "端到端自查工作流（Markdown + JSON 报告）"),
    "term": ("term_check.py", "术语保护检查（--auto-fix 可自动修复）"),
    "smell": ("translation_smell_check.py", "翻译腔检查（--json）"),
    "style": ("style_distance.py", "文体距离/人类相似度（--json）"),
    "quality": ("quality_report.py", "综合质量报告"),
    "aigc": ("aigc_label_check.py", "AIGC 合规标识检查（docx/pdf/图片/文本）"),
    "paragraph": ("paragraph_report.py", "段落级归因（HTML 报告）"),
    "setup": ("pp_setup.py", "监督层一键装模（--model / --check）"),
    "doctor": ("pp_doctor.py", "环境自检（能跑吗/跑哪档）"),
    "verify": ("pp_verify.py", "结构化零网络自证（AST 级；v5.0.0）"),
}

# 内建子命令（非透传，本文件内实现）
BUILTIN = ("quickstart", "test", "api")

_QUICKSTART_SAMPLE = (
    "值得注意的是，随着人工智能技术的快速发展，其在医疗领域的应用日益受到关注。"
    "具体而言，AI 不仅能够提高诊断效率，而且可以优化治疗方案的制定。"
    "然而，与此同时，我们在享受技术红利的同时也面临着诸多挑战。"
    "在一定程度上，数据安全问题的存在对行业发展产生了一定的制约。"
    "综上所述，本研究为该领域的进一步探索提供了一定的参考价值。"
)


def _run_quickstart():
    """零模型零文件一键体验：内嵌样例跑一遍核心链路（detect → fix → doctor）。"""
    print("paper-polisher-pro 一键体验（内嵌样例，无需模型/文件）\n")
    print("【第 1 步/3】AI 率检测（ai_detector）")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(_QUICKSTART_SAMPLE)
        demo = f.name
    subprocess.run([sys.executable, str(HERE / "ai_detector.py"), demo])
    print("\n【第 2 步/3】句子级改写建议（pp_fix_suggest，只指位+给策略，不代改）")
    subprocess.run([sys.executable, str(HERE / "pp_fix_suggest.py"), demo, "--top", "3"])
    print("\n【第 3 步/3】环境自检（pp_doctor——你当前跑的是哪一档）")
    subprocess.run([sys.executable, str(HERE / "pp_doctor.py")])
    Path(demo).unlink(missing_ok=True)
    print("\n下一步：把你的文稿存成 txt，运行 python3 scripts/pp.py detect 你的文件.txt"
          "；想看逐句改写建议加 pp.py fix 你的文件.txt。")
    return 0


def _run_tests():
    """包内单元测试（stdlib unittest，秒级、零网络、零模型）。"""
    pkg_root = HERE.parent
    tests_dir = pkg_root / "tests"
    if not tests_dir.exists():
        print("未找到 tests/ 目录（包内测试随 v5.0.0 发布）", file=sys.stderr)
        return 2
    import unittest
    suite = unittest.defaultTestLoader.discover(str(tests_dir), top_level_dir=str(pkg_root))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print("paper-polisher-pro 统一入口\n")
        entries = list(COMMANDS.items())
        width = max(len(k) for k, _ in entries)
        for k, (_, desc) in entries:
            print("  %-*s  %s" % (width, k, desc))
        print("  %-*s  %s" % (width, "quickstart", "零模型零文件一键体验（detect→fix→doctor）"))
        print("  %-*s  %s" % (width, "test", "包内单元测试（unittest，秒级）"))
        print("\nPython SDK: import pp_api（无 CLI；编程接口见 SKILL.md § Python API）")
        print("提示：各子命令的参数同原脚本，例如 pp.py detect draft.txt --format json")
        return 0
    cmd = args[0]
    if cmd == "api":
        print("Python SDK 无 CLI：import pp_api（见 SKILL.md § Python API）")
        return 0
    if cmd == "quickstart":
        return _run_quickstart()
    if cmd == "test":
        return _run_tests()
    if cmd not in COMMANDS:
        print("未知子命令: %s（可用：%s quickstart test）"
              % (cmd, " ".join(COMMANDS)), file=sys.stderr)
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
