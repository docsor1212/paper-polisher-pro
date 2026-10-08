# -*- coding: utf-8 -*-
"""数据文件完整性：阈值/融合配置/模式库/术语库/评测数字锚点。"""
import json
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


class TestDataFiles(unittest.TestCase):
    def test_para_thresholds_loads(self):
        d = json.load(open(PKG / "references" / "para_thresholds.json", encoding="utf-8"))
        self.assertIn("recommended_high", d)
        self.assertIn("honest_conclusion", d)

    def test_fusion_config_loads(self):
        d = json.load(open(PKG / "references" / "fusion_config.json", encoding="utf-8"))
        self.assertIn("thresholds", d)

    def test_zh_patterns_nonempty(self):
        d = json.load(open(PKG / "references" / "ai_patterns_zh.json", encoding="utf-8"))
        cats = d.get("categories", {})
        self.assertGreaterEqual(len(cats), 15)
        for name in ("ai_cliches", "filler_phrases", "sentence_structure"):
            self.assertIn(name, cats)

    def test_terminology_loads(self):
        d = json.load(open(PKG / "data" / "terminology.json", encoding="utf-8"))
        n = len(d) if isinstance(d, list) else len(d.get("terms", d))
        self.assertGreater(n, 2000, f"术语库条目异常: {n}")


class TestVersionConsistency(unittest.TestCase):
    def test_skill_md_version_is_500(self):
        head = (PKG / "SKILL.md").read_text(encoding="utf-8")[:4000]
        self.assertIn("5.0.0", head)

    def test_changelog_has_500_entry(self):
        t = (PKG / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("5.0.0", t[:3000])


if __name__ == "__main__":
    unittest.main()
