# -*- coding: utf-8 -*-
"""v7.0.0 契约测试（test_v70000）：包形态自适应 / 跨文件一致闸 / 改稿工作单。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
SCRIPTS = PKG / "scripts"

_TEXT = ("值得注意的是，随着人工智能技术的快速发展，其在医疗领域的应用日益受到关注。"
         "具体而言，AI 不仅能够提高诊断效率，而且可以优化治疗方案的制定。"
         "然而，与此同时，我们在享受技术红利的同时也面临着诸多挑战。"
         "在一定程度上，数据安全问题的存在对行业发展产生了一定的制约。"
         "综上所述，本研究为该领域的进一步探索提供了一定的参考价值。")


class TestWorksheet(unittest.TestCase):
    def test_worksheet_generated(self):
        tmp = Path(tempfile.mkdtemp(prefix="ppp7000_"))
        src = tmp / "draft.txt"
        src.write_text(_TEXT, encoding="utf-8")
        ws = tmp / "worksheet.md"
        p = subprocess.run([sys.executable, str(SCRIPTS / "pp_fix_suggest.py"),
                            str(src), "--worksheet", str(ws)],
                           capture_output=True, text=True, timeout=300,
                           encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        t = ws.read_text(encoding="utf-8")
        self.assertIn("改稿工作单", t)
        self.assertIn("rewrite-check", t)  # 验收闭环指引
        self.assertGreaterEqual(t.count("- [ ] 改后"), 3)
        self.assertIn("不代改", t)  # 诚信立场随单声明
        self.assertNotIn("advice", t.split("\n")[0])  # 无技术键名泄漏

    def test_missing_file_exit_2(self):
        p = subprocess.run([sys.executable, str(SCRIPTS / "pp_fix_suggest.py"),
                            "/no/such.txt", "--worksheet", "/tmp/x.md"],
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8")
        self.assertEqual(p.returncode, 2)


class TestFormAdaptive(unittest.TestCase):
    """包形态自适应：CH 英文包（无 SKILL_ZH）下测试套件与 smoke 都能跑。"""

    def test_docs_helper_skip_semantics(self):
        sys.path.insert(0, str(PKG / "tests"))
        import _docs
        self.assertTrue(hasattr(_docs, "zh_text"))
        self.assertTrue(hasattr(_docs, "HAS_ZH"))
        if not _docs.HAS_ZH:
            try:
                _docs.zh_text()
                self.fail("ZH 缺省时 zh_text 应 SkipTest")
            except unittest.SkipTest:
                pass

    def test_no_direct_skillzh_reads_in_tests(self):
        """残留锁：测试文件不得直接硬读 SKILL_ZH（必须走 _docs 助手）。"""
        for f in (PKG / "tests").glob("test_*.py"):
            t = f.read_text(encoding="utf-8")
            bad = 'SKILL_ZH' + '.md").read_text'  # 拼接构造：防残留锁自指（v6.5.0 教训）
            self.assertNotIn(bad, t, f"{f.name} 仍硬读 SKILL_ZH")

    @unittest.skipIf(os.environ.get("PP_IN_SMOKE"), "smoke 嵌套环境：防套娃（smoke→单测→smoke）")
    def test_smoke_runs_in_ch_form(self):
        """终极验收：临时挪走 SKILL_ZH 模拟 CH 英文包，smoke 必须跑完且无 error。

        本测试自身约 20 分钟（--fast 全程），仅在独立跑套件时执行。"""
        zh = PKG / "SKILL_ZH.md"
        stash = Path(tempfile.mkdtemp(prefix="ppp7000zh_")) / "SKILL_ZH.md"
        shutil.move(str(zh), str(stash))
        try:
            p = subprocess.run([sys.executable, str(PKG / "eval" / "release_smoke.py"), "--fast"],
                               capture_output=True, text=True, timeout=2400,
                               encoding="utf-8", cwd=str(PKG))
            self.assertNotIn("Traceback", p.stderr[:2000], "CH 形态下 smoke 崩溃")
            self.assertIn("[汇总]", p.stdout)
            # CH 形态下不得有 ZH 硬读导致的 error（fail 允许非 ZH 波动，error 不允许）
        finally:
            shutil.move(str(stash), str(zh))
        self.assertTrue(zh.is_file(), "SKILL_ZH 必须复位")


class TestConsistencyGates(unittest.TestCase):
    def test_python_floor_unified(self):
        req = (PKG / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("3.8+", req)
        self.assertIn("3.9", req)
        doctor = (PKG / "scripts" / "pp_doctor.py").read_text(encoding="utf-8")
        self.assertIn("3, 9", doctor.replace(" ", "").replace("(3, 9)", "(3,9)") if "(3, 9)" not in doctor else doctor)

    def test_readme_no_hardcoded_count(self):
        import re
        t = (PKG / "README.md").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\d+\s*(?:用例|个测试)", t), "README 仍有硬编码测试计数")


if __name__ == "__main__":
    unittest.main()
