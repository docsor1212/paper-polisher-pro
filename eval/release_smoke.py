#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""release_smoke.py — paper-polisher-pro 发布验收冒气电池（v3.5 起，随包发布）

设计原则（cite-holmes 五连发教训）：机器能查的必须变成机器查；断言读运行时真值，
绝不硬编码版本号。用法：
  python eval/release_smoke.py            # 全量
  python eval/release_smoke.py --fast     # 跳过重复次数多的探针

覆盖：
  A. 文档一致性     版本三处一致(SKILL.md/skill.json/发布)、frontmatter 语言断言、
                    旧营销宣称已清、文档引用的脚本都存在、触发词含 AI率
  B. 引擎行为       短文本铁律2(risk=unknown)、空文件优雅处理、确定性(两次同分)、
                    降级披露(degraded_mode/notice)、PP_NO_SUP 矩阵、英文语言门控
  C. 全脚本入口     term_check/translation_smell/quality_report/paragraph_report/
                    aigc_label_check/style_distance/deai_gate(--json)/pp_doctor
  D. CLI 纪律       --help 全部可用、缺文件报错不抛栈、deai_gate 无参数给用法
  E. 打包白名单预检  无扩展名文件/_meta.json/gif 不存在

输出: 逐项 [PASS]/[FAIL]，末行 "[汇总] ... -> GREEN/RED"；exit 0/1。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FAST = "--fast" in sys.argv

ZH_HUMAN = ("本研究采用前瞻性队列设计，共纳入2024年1月至2025年6月期间就诊的312例患儿。"
            "所有纳入对象均由两名副主任医师及以上职称者独立诊断，诊断符合率Kappa值为0.87。"
            "随访终点为首次复发，中位随访时间18.4个月，四分位距12.1至24.6。"
            "统计学分析使用Python完成，组间比较采用Mann-Whitney U检验，分类资料采用卡方检验。"
            "此外，我们还对亚组分析进行了敏感性检验，主要结论在不同模型设定下保持稳健，"
            "研究方案经医院伦理委员会审查批准，所有监护人签署知情同意书。")
ZH_SHORT = "这是一段很短的文本。"
EN_TEXT = ("This cohort study enrolled 312 consecutive patients between January 2024 and June 2025. "
           "Two senior physicians independently confirmed each diagnosis, with an inter-rater kappa of 0.87. "
           "The primary endpoint was first relapse, and the median follow-up was 18.4 months.")

results = []


def chk(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)[:180]))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" | {detail}" if (detail and not ok) else ""))


def run_py(script, args, env_extra=None, timeout=180):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, str(SCRIPTS / script)] + args,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=env)
    return p.returncode, p.stdout or "", p.stderr or ""


def tmpfile(content):
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


def detect_json(text, env_extra=None):
    path = tmpfile(text)
    try:
        rc, so, se = run_py("ai_detector.py", [path, "--format", "json"], env_extra=env_extra)
        return rc, (json.loads(so) if rc == 0 and so.strip() else None), se
    finally:
        Path(path).unlink(missing_ok=True)


# ───────────────────────── A. 文档一致性 ─────────────────────────
skill_md = (ROOT / "SKILL.md").read_text(encoding="utf-8")
skill_zh = (ROOT / "SKILL_ZH.md").read_text(encoding="utf-8")
skill_json = json.load(open(ROOT / "skill.json", encoding="utf-8"))

fm_md = re.match(r"^---\n(.*?)\n---\n", skill_md, re.S).group(1)
fm_zh = re.match(r"^---\n(.*?)\n---\n", skill_zh, re.S).group(1)
ver_md = re.search(r"^version:\s*(\S+)", fm_md, re.M).group(1)


def has_cjk(s):
    return any("\u4e00" <= c <= "\u9fff" for c in s)


chk("版本三处一致(SKILL.md=SKILL_ZH=skill.json)",
    ver_md == re.search(r"^version:\s*(\S+)", fm_zh, re.M).group(1) == skill_json["version"],
    f"md={ver_md} json={skill_json['version']}")
chk("英文 frontmatter 无 CJK", not has_cjk(fm_md))
chk("中文 frontmatter 含 CJK", has_cjk(fm_zh))
desc_md = " ".join(x.strip() for x in re.search(r"description: >\n((?:  .+\n)+)", skill_md).group(1).splitlines())
chk("EN description ≤1024 字符", len(desc_md) <= 1024, f"{len(desc_md)}")
chk("ZH description ≤1024 字符",
    len(" ".join(x.strip() for x in re.search(r"description: >\n((?:  .+\n)+)", skill_zh).group(1).splitlines())) <= 1024)
chk("frontmatter 键数 ≤5", all(len(re.findall(r"^(\w+):", fm, re.M)) <= 5 for fm in (fm_md, fm_zh)))
_BANNED = ["全部100%检出", "10个模型测试", "100% detection rate", "detection rate: 100"]
def _banned_outside_quote(doc):
    # 旧宣称允许出现在"已删除/removed"引述行(铁律原文), 除此之外零容忍
    for line in doc.splitlines():
        if any(b in line for b in _BANNED) and not ("删" in line or "removed" in line):
            return line.strip()[:80]
    return None
chk("旧营销宣称已清(铁律引述行除外)",
    _banned_outside_quote(skill_zh) is None and _banned_outside_quote(skill_md) is None,
    f"zh={_banned_outside_quote(skill_zh)} en={_banned_outside_quote(skill_md)}")
chk("ZH 中 F1 98.3 仅出现在铁律引述(≤1处)", skill_zh.count("98.3") <= 1, f"count={skill_zh.count('98.3')}")
chk("触发词含 AI率 词位", "查AI率" in skill_zh and "AI率" in skill_zh)
chk("家族导流段在位(双语)", "Related skills" in skill_md and "Related skills" in skill_zh)
chk("FAQ 专节在位(评测C维驱动,双语)", "## 常见问题（FAQ）" in skill_zh and "## FAQ" in skill_md)
chk("脚本速查表在位(评测C维驱动,双语)", "各脚本速查" in skill_zh and "Script cheat sheet" in skill_md)
chk("FAQ 覆盖高频问法", "知网" in skill_zh and "degraded_mode" in skill_zh and "100 字" in skill_zh)
for ref in set(re.findall(r"`?(\w+\.(?:py|json))`?", skill_md)):
    if ref.endswith(".py"):
        chk(f"文档引用脚本存在 {ref}", (SCRIPTS / ref).exists() or (ROOT / "eval" / ref).exists())

# ───────────────────────── B. 引擎行为 ─────────────────────────
rc, r, se = detect_json(ZH_SHORT)
chk("短文本铁律2: risk=unknown", rc == 0 and r and r["overall_risk"] == "unknown", f"rc={rc} risk={r and r.get('overall_risk')}")
chk("短文本含不判定提示", r and "100" in r.get("degraded_notice", "") + r.get("details", ""))

# v3.7.0: L12 篇章结构启发层探针（LES-20260923-021 回归防护）
_DISC = ("先看一个场景。小林昨天拿到检测报告，数字比上个月低了不少。他盯着屏幕看了半天，心里直犯嘀咕："
         "这系统是不是换了比对库？同一段文字，前后两次测，一个说高一个说低。所以你看，不是谁退步了，是规则变了。"
         "把这句话记住：数字只是参考，别被一个报告定死。后来他调整了写法，第二天再测，数字果然回来了。")
rcd, rd, _ = detect_json(_DISC)
_disc_groups = sorted(h.get("group") for h in (rd or {}).get("discourse_hits", [])) if rd else []
chk("篇章三件套检出+加分(LES-021)", rcd == 0 and rd and rd.get("discourse_bonus", 0) >= 12
    and set(_disc_groups) >= {"钩子", "反转", "口号"}, f"groups={_disc_groups} bonus={rd and rd.get('discourse_bonus')}")
rcn, rn, _ = detect_json(ZH_HUMAN)
chk("学术样本篇章层零扰动", rcn == 0 and rn and not rn.get("discourse_hits") and rn.get("discourse_bonus", 0) == 0)

rc1, r1, _ = detect_json(ZH_HUMAN)
rc2, r2, _ = detect_json(ZH_HUMAN)
chk("长文本 JSON 可解析", rc1 == 0 and r1 and isinstance(r1.get("overall_ai_score"), (int, float)))
chk("确定性(两次同分)", rc1 == rc2 == 0 and r1["overall_ai_score"] == r2["overall_ai_score"],
    f"{r1 and r1.get('overall_ai_score')} vs {r2 and r2.get('overall_ai_score')}")
chk("降级披露字段在位", r1 and r1.get("degraded_mode") is True and bool(r1.get("degraded_notice")))
chk("降级警示含医学语域数字", r1 and "59" in r1["degraded_notice"])
chk("学术诚信护栏(integrity_notice)", bool(r1.get("integrity_notice")) and "披露" in r1["integrity_notice"] + r1.get("details", ""))

# v3.6 补: CH 读取面(EN SKILL.md + skill.json)平台政策禁词表——campaign 教训固化为机器检查
# (negated integrity statements 中的 evade/evasion 属声明性用法, 刻意不在禁词表——见 SKILL.md Academic integrity 节)
_BAN = ["朱雀", "gptzero", "turnitin", "过检测", "过ai检测", "降检测率", "humanize",
        "remove ai traces", "reduce ai detection", "过朱雀", "bypass"]
_ch_surface = (skill_md + json.dumps(skill_json, ensure_ascii=False)).lower()
_hits = [w for w in _BAN if w in _ch_surface]
chk("CH 面禁词表(朱雀/GPTZero/Turnitin/humanize/evade短语)", not _hits, "命中: " + ",".join(_hits))
chk("接口兼容: overall_ai_score 字段(管线依赖)", r1 and "overall_ai_score" in r1 and "supervised" in r1)

rc3, r3, _ = detect_json(ZH_HUMAN, env_extra={"PP_NO_SUP": "1"})
chk("PP_NO_SUP 矩阵: rc=0 且分数可复现", rc3 == 0 and r3 and r3["overall_ai_score"] == r1["overall_ai_score"],
    f"no_sup={r3 and r3.get('overall_ai_score')} vs default={r1 and r1.get('overall_ai_score')}")

# v3.5 补: 中文 Windows GBK 环境矩阵(默认 zh-CN 控制台, 多专家对抗测试发现的 P0 回归防护)
_gbk_f = tmpfile(ZH_HUMAN)
try:
    rc, so, se = run_py("ai_detector.py", [_gbk_f, "--format", "summary"], env_extra={"PYTHONIOENCODING": "gbk"})
    chk("GBK stdout 矩阵: summary 不崩", rc == 0, f"rc={rc} {se[:80]}")
    rc, so, se = run_py("ai_detector.py", [_gbk_f, "--format", "json"], env_extra={"PYTHONIOENCODING": "gbk"})
    chk("GBK stdout 矩阵: json 不崩", rc == 0 and so.strip().startswith("{"), f"rc={rc} {se[:80]}")
    rc, so, se = run_py("deai_gate.py", [_gbk_f], env_extra={"PYTHONIOENCODING": "gbk"})
    chk("GBK stdout 矩阵: deai_gate 不崩", rc == 0, f"rc={rc} {se[:80]}")
finally:
    Path(_gbk_f).unlink(missing_ok=True)
_gbk_in = Path(tempfile.gettempdir()) / f"pp_gbk_in_{os.getpid()}.txt"
_gbk_in.write_bytes((ZH_HUMAN + "补充一句长度。") .encode("gbk"))
try:
    rc, so, se = run_py("ai_detector.py", [str(_gbk_in), "--format", "json"])
    chk("GBK 编码输入容错(rc=0)", rc == 0, f"rc={rc} {se[:80]}")
finally:
    _gbk_in.unlink(missing_ok=True)

rc4, r4, _ = detect_json(EN_TEXT)
chk("英文文本 rc=0 且语言门控披露", rc4 == 0 and r4 and "language gating" in (r4.get("degraded_notice") or ""),
    f"notice={r4 and (r4.get('degraded_notice') or '')[:60]}")

empty_f = tmpfile("")
try:
    p = subprocess.run([sys.executable, str(SCRIPTS / "ai_detector.py"), empty_f, "--format", "json"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    chk("空文件优雅处理", p.returncode == 0 and "unknown" in (p.stdout or ""))
finally:
    Path(empty_f).unlink(missing_ok=True)

# ───────────────────────── C. 全脚本入口 ─────────────────────────
zh_f = tmpfile(ZH_HUMAN)
try:
    rc, so, se = run_py("term_check.py", [zh_f])
    chk("term_check rc=0", rc == 0, f"rc={rc} {se[:80]}")
    rc, so, se = run_py("term_check.py", [zh_f, "--auto-fix"])
    chk("term_check --auto-fix rc=0", rc == 0, f"rc={rc}")
    rc, so, se = run_py("translation_smell_check.py", [zh_f, "--json"])
    ok = rc == 0
    if ok:
        try:
            json.loads(so)
        except Exception:
            ok = False
    chk("translation_smell --json 可解析", ok, f"rc={rc} out={so[:60]}")
    rc, so, se = run_py("quality_report.py", [zh_f, "--format", "json"])
    ok = rc == 0
    if ok:
        try:
            json.loads(so)
        except Exception:
            ok = False
    chk("quality_report --format json 可解析", ok, f"rc={rc}")
    rc, so, se = run_py("quality_report.py", [zh_f])
    chk("quality_report text 含 AI 痕迹行", rc == 0 and "AI痕迹" in so)
    rc, so, se = run_py("style_distance.py", [zh_f, "--json"])
    chk("style_distance --json rc=0", rc == 0, f"rc={rc} {se[:60]}")
    out_html = Path(tempfile.gettempdir()) / f"pp_smoke_{os.getpid()}.html"
    rc, so, se = run_py("paragraph_report.py", [zh_f, "--output", str(out_html)])
    chk("paragraph_report 产出 HTML", rc == 0 and out_html.exists() and out_html.stat().st_size > 500,
        f"rc={rc} exists={out_html.exists()}")
    out_html.unlink(missing_ok=True)
    rc, so, se = run_py("aigc_label_check.py", [zh_f])
    # rc 语义: 0=有合规标识; 1=无标识(检查结果,非错误); 2+=真错误
    chk("aigc_label_check 正常执行(rc∈{0,1})", rc in (0, 1), f"rc={rc} {se[:60]}")
    rc, so, se = run_py("deai_gate.py", [zh_f, "--json"])
    ok = rc == 0
    if ok:
        try:
            g = json.loads(so)
            ok = "composite_ai_risk" in g and "verdict" in g
        except Exception:
            ok = False
    chk("deai_gate --json 四层融合可解析", ok, f"rc={rc} out={so[:80]}")
    rc, so, se = run_py("pp_doctor.py", [])
    chk("pp_doctor 全量自检 GREEN", rc == 0 and "-> GREEN" in so, f"rc={rc}")
finally:
    Path(zh_f).unlink(missing_ok=True)

# ───────────────────────── D. CLI 纪律 ─────────────────────────
for script in ["ai_detector.py", "term_check.py", "quality_report.py", "style_distance.py",
               "translation_smell_check.py", "paragraph_report.py", "aigc_label_check.py", "pp_doctor.py"]:
    rc, so, se = run_py(script, ["--help"])
    chk(f"--help 正常 {script}", rc == 0 and ("usage" in (so + se).lower() or "用法" in (so + se)), f"rc={rc}")
rc, so, se = run_py("deai_gate.py", ["--help"])
chk("--help 正常 deai_gate.py(v3.5 守卫)", rc == 0 and "用法" in so, f"rc={rc}")
rc, so, se = run_py("deai_gate.py", [])
chk("deai_gate 无参数给用法(rc=2)", rc == 2 and "用法" in (so + se), f"rc={rc}")
rc, so, se = run_py("ai_detector.py", ["no_such_file.txt"])
chk("缺文件报错不抛栈", rc != 0 and "Traceback" not in se, f"rc={rc}")

# ───────────────────────── E. 打包白名单预检 ─────────────────────────
bad = []
for f in ROOT.rglob("*"):
    if f.is_file():
        rel = f.relative_to(ROOT).as_posix()
        if "__pycache__" in rel or ".bak" in rel or rel.startswith(".git/") or rel == ".gitignore":
            continue
        if not f.suffix:
            bad.append(f"无扩展名: {rel}")
        if f.name == "_meta.json":
            bad.append(f"_meta.json: {rel}")
        if f.suffix.lower() == ".gif":
            bad.append(f"gif: {rel}")
chk("SH 白名单预检(无扩展名/_meta.json/gif)", not bad, "; ".join(bad[:3]))

# ───────────────────────── 汇总 ─────────────────────────
failed = [r for r in results if not r[1]]
print("────────────────────────────────")
print(f"[汇总] total={len(results)} pass={len(results)-len(failed)} fail={len(failed)} "
      f"-> {'GREEN' if not failed else 'RED'}")
sys.exit(0 if not failed else 1)
