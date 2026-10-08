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
desc_md = " ".join(x.strip() for x in re.search(r"description: >-?\n((?:  .+\n)+)", skill_md).group(1).splitlines())
chk("EN description ≤1024 字符", len(desc_md) <= 1024, f"{len(desc_md)}")
chk("ZH description ≤1024 字符",
    len(" ".join(x.strip() for x in re.search(r"description: >-?\n((?:  .+\n)+)", skill_zh).group(1).splitlines())) <= 1024)
# v4.6.0: ZH frontmatter 增 metadata.displayName（10-05 全家族搜索审计任务要求, SH 页面一致性同步点）——EN 仍 ≤5
_k_en = len(re.findall(r"^(\w+):", fm_md, re.M))
_k_zh = len(re.findall(r"^(\w+):", fm_zh, re.M))
chk("frontmatter 键数（EN ≤5; ZH 含 metadata.displayName ≤6）", _k_en <= 5 and _k_zh <= 6,
    f"EN={_k_en} ZH={_k_zh}")
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
chk("相关工具节在位(双语)", "## Related tools" in skill_md and "## 相关工具" in skill_zh)
_ADTALK = ["全家桶", "搜招牌名直达", "五件套", "论文工具家族", "Paper Toolbox family"]
_adtalk_hits = [w for w in _ADTALK if w in skill_md or w in skill_zh]
chk("导流叫卖词零残留(家族/全家桶/搜招牌名/五件套)", not _adtalk_hits, "; ".join(_adtalk_hits))
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

# v3.11: --batch 批处理模式探针
import shutil as _shutil
_bdir = Path(tempfile.mkdtemp())
(_bdir / "a.txt").write_text(ZH_HUMAN, encoding="utf-8")
(_bdir / "b.txt").write_text(ZH_SHORT, encoding="utf-8")
try:
    _rcb, sob, seb = run_py("ai_detector.py", ["--batch", str(_bdir), "--format", "json"])
    _okb = _rcb == 0
    if _okb:
        _jb = json.loads(sob)
        _okb = ("aggregate" in _jb and _jb["aggregate"]["files"] == 2
                and "integrity_notice" in _jb)
    chk("batch 模式(聚合+诚信字段)", _okb, f"rc={_rcb}")
finally:
    _shutil.rmtree(_bdir, ignore_errors=True)

rcn, rn, _ = detect_json(ZH_HUMAN)
# v4.1: batch CSV 探针
_cdir = Path(tempfile.mkdtemp())
(_cdir / "x.txt").write_text(ZH_HUMAN, encoding="utf-8")
_csvp = _cdir / "out.csv"
try:
    _rcc, soc, _ = run_py("ai_detector.py", ["--batch", str(_cdir), "--format", "json", "--csv", str(_csvp)])
    _okc = _rcc == 0 and _csvp.exists() and "ai_score" in _csvp.read_text(encoding="utf-8-sig")
    chk("batch CSV 输出", _okc, f"rc={_rcc}")
finally:
    _shutil.rmtree(_cdir, ignore_errors=True)

rcn, rn, _ = detect_json(ZH_HUMAN)
# v4.2: batch recursive 探针
_rdir = Path(tempfile.mkdtemp()) / "deep"
_rdir.mkdir(parents=True)
(_rdir / "nested.txt").write_text(ZH_HUMAN, encoding="utf-8")
try:
    _rcr, sor, _ = run_py("ai_detector.py", ["--batch", str(_rdir.parent), "--recursive", "--format", "json"])
    _okr = _rcr == 0 and "nested.txt" in sor and sor.count('"file"') >= 1
    chk("batch recursive 子目录遍历", _okr, f"rc={_rcr}")
finally:
    _shutil.rmtree(_rdir.parent, ignore_errors=True)

rcn, rn, _ = detect_json(ZH_HUMAN)
chk("学术样本篇章层零扰动", rcn == 0 and rn and not rn.get("discourse_hits") and rn.get("discourse_bonus", 0) == 0)

# v3.12: 层3复活+诚信覆盖探针
_TS = ("这部作品被给予了一个深刻的印象。作出了一个全面的分析。进行了认真的研究。"
       "一个优秀的方案被制定了出来，并且被实施了一个详细的计划。"
       "而在整个过程中，一个重要的角色被扮演了。本研究具有重要的理论意义。")
_fts = Path(tempfile.mkdtemp())
(_fts / "t.txt").write_text(_TS, encoding="utf-8")
try:
    _rg, gog, _ = run_py("deai_gate.py", [str(_fts / "t.txt"), "--json"])
    _ok3 = _rg == 0
    if _ok3:
        _gj = json.loads(gog)
        _n3 = _gj["layers"]["L3_translation_smell"]["note"]
        _ok3 = ("解析失败" not in _n3) and ("翻译腔命中" in _n3)
    chk("层3复活(翻译腔真实参与)", _ok3, f"note={_n3 if _ok3 else '解析失败'}")
finally:
    _shutil.rmtree(_fts, ignore_errors=True)
_int_scripts = ["style_distance.py", "translation_smell_check.py", "term_check.py", "quality_report.py"]
_int_hits = 0
_fti = tmpfile(ZH_HUMAN)
try:
    for _s in _int_scripts:
        _rci, _so, _se = run_py(_s, [_fti])
        if NOTICE_MARK := ("学术写作自查" in _so or "学术诚信" in _so):
            _int_hits += 1
    chk("诚信提示全报告覆盖(4脚本)", _int_hits == 4, f"命中 {_int_hits}/4")
finally:
    Path(_fti).unlink(missing_ok=True)

# v3.7.0: L12 篇章结构启发层探针（LES-20260923-021 回归防护）
_DISC = ("先看一个场景。小林昨天拿到检测报告，数字比上个月低了不少。他盯着屏幕看了半天，心里直犯嘀咕："
         "这系统是不是换了比对库？同一段文字，前后两次测，一个说高一个说低。所以你看，不是谁退步了，是规则变了。"
         "把这句话记住：数字只是参考，别被一个报告定死。后来他调整了写法，第二天再测，数字果然回来了。")
rcd, rd, _ = detect_json(_DISC)
_disc_groups = sorted(h.get("group") for h in (rd or {}).get("discourse_hits", [])) if rd else []
chk("篇章三件套检出+加分(LES-021)", rcd == 0 and rd and rd.get("discourse_bonus", 0) >= 12
    and set(_disc_groups) >= {"钩子", "反转", "口号"}, f"groups={_disc_groups} bonus={rd and rd.get('discourse_bonus')}")
rcn, rn, _ = detect_json(ZH_HUMAN)
# v3.8: YAML 冒烟自检（doc-holmes 大忌: 行内值含"冒号+空格"致平台判"无有效 skill"）
for _nm, _fm in (("EN", fm_md), ("ZH", fm_zh)):
    _bad = [ln for ln in _fm.splitlines()
            if re.match(r"^\w+: .+", ln) and re.search(r":\s", ln.split(":", 1)[1])]
    chk(f"YAML 冒烟: {_nm} frontmatter 无行内冒号+空格", not _bad, "; ".join(_bad[:2]))
try:
    import yaml as _yaml
    for _nm, _fm in (("EN", fm_md), ("ZH", fm_zh)):
        try:
            _parsed = _yaml.safe_load(_fm)
            _ok = isinstance(_parsed, dict) and isinstance(_parsed.get("description"), str) and len(_parsed["description"]) > 20
            chk(f"YAML 解析: {_nm} frontmatter 可解析且 description 有效", _ok)
        except Exception as _e:
            chk(f"YAML 解析: {_nm} frontmatter 可解析且 description 有效", False, str(_e)[:80])
except ImportError:
    chk("YAML 解析(pyyaml 未装, 跳过)", True)
chk("安全与行为声明节在位(双语)", "安全与行为声明" in skill_zh and "Safety and behavior statement" in skill_md)


rc1, r1, _ = detect_json(ZH_HUMAN)
rc2, r2, _ = detect_json(ZH_HUMAN)
chk("长文本 JSON 可解析", rc1 == 0 and r1 and isinstance(r1.get("overall_ai_score"), (int, float)))
chk("确定性(两次同分)", rc1 == rc2 == 0 and r1["overall_ai_score"] == r2["overall_ai_score"],
    f"{r1 and r1.get('overall_ai_score')} vs {r2 and r2.get('overall_ai_score')}")
# v4.4.0: 模式感知——模型在位时默认态=完整模式(坏图时代的全绿恰恰因为模型死了, smoke 自己失明)
_sup_full = bool(r1 and r1.get("supervised"))
chk("降级披露一致性(模式与监督层在位互洽)", r1 and isinstance(r1.get("degraded_mode"), bool)
    and bool(r1.get("degraded_notice")) == r1["degraded_mode"]
    and r1["degraded_mode"] == (not _sup_full),
    f"degraded_mode={r1 and r1.get('degraded_mode')} supervised={'有' if _sup_full else '无'}")
# 降级警示文本: 用 PP_NO_SUP=1 强制降级态验证(与模型是否在位无关)
rc1d, r1d, _ = detect_json(ZH_HUMAN, env_extra={"PP_NO_SUP": "1"})
chk("降级警示含医学语域数字", rc1d == 0 and r1d and r1d.get("degraded_mode") is True
    and "59" in (r1d.get("degraded_notice") or ""),
    f"notice={r1d and (r1d.get('degraded_notice') or '')[:60]}")
chk("学术诚信护栏(integrity_notice)", bool(r1.get("integrity_notice")) and "披露" in r1["integrity_notice"] + r1.get("details", ""))

# v3.8: 混写预警/语域提示/编码警示探针
_MIXED = ("值得注意的是，本研究具有重要的理论意义与实践价值。首先，我们系统性地梳理了相关领域的研究脉络；"
          "其次，我们提出了一个创新性的分析框架；最后，我们的研究结论为后续研究奠定了坚实的基础。综上所述，"
          "这项研究不仅拓展了学科边界，也为实际应用提供了有力支撑。与此同时，方法的严谨性与数据的可靠性"
          "进一步增强了结论的说服力。\n\n"
          "说实话这个方案我们组里吵了三天。老张觉得采样太少，我倒觉得先跑起来再说，"
          "反正数据在那儿摆着，不行再改呗。昨天跑完第一版，效果一般般吧，但至少能看。")
rcm, rm, _ = detect_json(_MIXED)
chk("混写预警触发(mixed_signal)", rcm == 0 and rm and rm.get("mixed_signal") is True and "混写" in (rm.get("mixed_notice") or ""))
_COLLOQ = ("今天这事儿整得挺离谱的哈。早上跟老王说了这事儿，他说你咋不早讲呢，嘛呀这是。"
           "中午吃饭的时候大家又开始聊，说实话搞了半天就这么点事，挺好的结果算是落地了呗。")
rcg, rg, _ = detect_json(_COLLOQ)
chk("语域提示触发(register_hint)", rcg == 0 and rg and "口语" in (rg.get("register_hint") or ""))
rcn, rn, _ = detect_json(ZH_HUMAN)
chk("正常学术样本无误报", rcn == 0 and rn and not rn.get("mixed_signal") and not rn.get("register_hint") and not rn.get("encoding_warning"))
_gbk2 = Path(tempfile.gettempdir()) / f"pp_gbk_warn_{os.getpid()}.txt"
_gbk2.write_bytes(ZH_HUMAN.encode("utf-8", errors="replace").decode("utf-8", errors="ignore").encode("utf-8"))
try:
    _raw = (ZH_HUMAN[:40] + "\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd") * 6
    _f2 = tmpfile(_raw)
    try:
        rcw, rw, _ = detect_json(_raw)
        chk("编码警示触发(encoding_warning)", rcw == 0 and rw and bool(rw.get("encoding_warning")))
    finally:
        Path(_f2).unlink(missing_ok=True)
finally:
    _gbk2.unlink(missing_ok=True)
rcg8, rg8, _ = detect_json(ZH_HUMAN)
_g8 = tmpfile(ZH_HUMAN)
try:
    rcgj, sog, _ = run_py("deai_gate.py", [_g8, "--json"])
    okg = rcgj == 0
    if okg:
        gj = json.loads(sog)
        okg = "layer_divergence" in gj
    chk("门禁层间分歧字段在位", okg, f"rc={rcgj}")
finally:
    Path(_g8).unlink(missing_ok=True)

# v3.6 补: CH 读取面(EN SKILL.md + skill.json)平台政策禁词表——campaign 教训固化为机器检查
# (negated integrity statements 中的 evade/evasion 属声明性用法, 刻意不在禁词表——见 SKILL.md Academic integrity 节)
_BAN = ["朱雀", "gptzero", "turnitin", "过检测", "过ai检测", "降检测率", "去ai痕迹", "humanize",
        "remove ai traces", "reduce ai detection", "过朱雀", "bypass"]
_ch_surface = (skill_md + json.dumps(skill_json, ensure_ascii=False)).lower()
_hits = [w for w in _BAN if w in _ch_surface]
chk("CH 面禁词表(朱雀/GPTZero/Turnitin/humanize/evade短语)", not _hits, "命中: " + ",".join(_hits))
chk("接口兼容: overall_ai_score 字段(管线依赖)", r1 and "overall_ai_score" in r1 and "supervised" in r1)

rc3, r3, _ = detect_json(ZH_HUMAN, env_extra={"PP_NO_SUP": "1"})
chk("PP_NO_SUP 矩阵: rc=0 且与强制降级态同分(可复现)", rc3 == 0 and r3 and r1d and
    r3["overall_ai_score"] == r1d["overall_ai_score"],
    f"no_sup={r3 and r3.get('overall_ai_score')} vs forced={r1d and r1d.get('overall_ai_score')}")

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

# ───────────────────────── F. 可编程接口（v4.5.0） ─────────────────────────
import shutil as _shutil_f
try:
    sys.path.insert(0, str(SCRIPTS))
    import pp_api as _API
    _d = _API.detect_text(ZH_HUMAN, lang="zh")
    chk("SDK import + detect_text 出分", isinstance(_d.get("overall_ai_score"), (int, float)),
        f"score={_d.get('overall_ai_score')}")
    # 与 CLI 位级同源（同一 detect 代码路径）
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as _f:
        _f.write(ZH_HUMAN); _cli_f = _f.name
    _rc, _so, _se = run_py("ai_detector.py", [_cli_f, "--format", "json"])
    Path(_cli_f).unlink(missing_ok=True)
    _cli_score = json.loads(_so).get("overall_ai_score") if _rc == 0 else None
    chk("SDK detect_text 与 CLI 同分（同源校验）",
        _cli_score is not None and _cli_score == _d.get("overall_ai_score"),
        f"sdk={_d.get('overall_ai_score')} cli={_cli_score}")
    _g = _API.gate_text(ZH_HUMAN)
    chk("SDK gate_text 出复合分", isinstance(_g.get("composite_ai_risk"), (int, float))
        and _g.get("verdict") in ("pass", "review", "ai_suspect"),
        f"composite={_g.get('composite_ai_risk')}")
    _doc = _API.doctor_summary()
    chk("SDK doctor_summary 档位+版本", _doc.get("engine_mode") in ("full", "degraded")
        and isinstance(_doc.get("version"), str),
        f"mode={_doc.get('engine_mode')} v={_doc.get('version')}")
    # 终审 NO-GO 修复回归: doctor_summary 的 data_files_ok 在健康机器上必须 True
    chk("SDK doctor_summary data_files_ok", _doc.get("data_files_ok") is True,
        f"data_files_ok={_doc.get('data_files_ok')} missing={_doc.get('data_missing')}")
    # 终审 NO-GO 修复回归: smell_report 有命中时必须 JSON 可序列化
    import json as _json_f
    _hit_text = "这个问题的结果被进行了详细的分析和讨论。"
    _sr = _API.smell_report(_hit_text)
    _json_f.dumps(_sr)  # 不序列化即抛
    chk("SDK smell_report JSON 可序列化（含命中）", _sr.get("total_hits", 0) >= 1
        and isinstance(_sr["hits"][0], dict),
        f"total_hits={_sr.get('total_hits')}")
    # v4.6.0: 端到端 workflow
    _wf = _API.workflow(ZH_HUMAN, lang="zh")
    _json_f.dumps(_wf)
    _need = ("detect", "paragraphs", "gate", "terms", "smell", "style", "quality", "aigc_label")
    chk("SDK workflow 全键+JSON 可序列化", all(k in _wf for k in _need)
        and _wf["detect"].get("overall_ai_score") is not None
        and _wf["paragraphs"].get("total", 0) >= 1,
        f"keys={sorted(_wf)}")
    # 终审 NO-GO 修复回归: MD 报告质量报告节必须非空（键名错配曾致恒空）
    import pp_workflow as _PWf
    _md = _PWf.to_markdown(_wf)
    _sec6 = _md.split("## 6. 质量报告")[-1].split("##")[0].strip()
    chk("workflow MD 质量报告节非空", len(_sec6) > 20, f"sec6len={len(_sec6)}")
    # v4.7.0: 混写文档评估块（人写段夹 AI 段 → mixed_document.detected 必须 True）
    _hu = ("本研究采用前瞻性队列设计，共纳入2024年1月至2025年6月期间就诊的312例患儿。"
           "所有纳入对象均由两名副主任医师及以上职称者独立诊断，诊断符合率Kappa值为0.87。"
           "随访终点为首次复发，中位随访时间18.4个月，四分位距12.1至24.6。"
           "统计学分析使用Python完成，组间比较采用Mann-Whitney U检验，分类资料采用卡方检验。")
    _ai = ("值得注意的是，本研究具有重要的理论意义与实践价值。首先，我们系统性地梳理了相关领域的研究脉络，"
           "为后续研究奠定了坚实的基础。其次，本研究采用了多元化的研究方法，确保了结论的可靠性和普适性。"
           "总而言之，这项研究不仅填补了学术空白，更为实践应用提供了强有力的支撑和指导。")
    _wm = _API.workflow(_hu + "\n\n" + _ai + "\n\n" + _hu.replace("312", "286"), lang="zh")
    _json_f.dumps(_wm)
    chk("workflow 混写评估块（夹心文档 detected=True+校准字段在位）",
        _wm.get("mixed_document", {}).get("detected") is True
        and _wm["mixed_document"].get("measured", {}).get("paragraph_level_auroc") == 0.6883
        and _wm["mixed_document"].get("measured", {}).get("calibrated_high_threshold") is not None,
        f"detected={_wm.get('mixed_document', {}).get('detected')} "
        f"calibrated={_wm.get('mixed_document', {}).get('measured', {}).get('calibrated_high_threshold')}")
    # v4.7.0 求星合规铺设: MD 交付物页脚恰好一次（同一产物仅一次纪律）
    _foot = "觉得有用欢迎 Star / 收藏"
    chk("workflow MD 页脚恰好一次（求星合规）", _md.count(_foot) == 1,
        f"count={_md.count(_foot)}")
    # v4.8.0: journal+json 纯度（第三方测试 Bug#8 回归）与 risk_bands 透出（发现#4）
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as _hf:
        _hf.write(ZH_HUMAN); _hu_file_hold = _hf.name
    _p = subprocess.run([sys.executable, str(SCRIPTS / "ai_detector.py"), _hu_file_hold,
                         "--profile", "journal", "--format", "json"],
                        capture_output=True, text=True, encoding="utf-8", timeout=180,
                        env={**os.environ, "PP_ORT_THREADS": "8"})
    try:
        _jd = json.loads(_p.stdout)
        _ok_j = _jd.get("journal_precheck") is not None and _jd.get("risk_bands") is not None
    except Exception:
        _ok_j = False
    chk("journal+json 纯度且 risk_bands 透出", _ok_j,
        f"rc={_p.returncode} parse={'ok' if _ok_j else 'FAIL'}")
    Path(_hu_file_hold).unlink(missing_ok=True)
    # v4.9.0: pp.py 统一入口路由
    _pp = subprocess.run([sys.executable, str(SCRIPTS / "pp.py")],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    _pp_bad = subprocess.run([sys.executable, str(SCRIPTS / "pp.py"), "no-such-cmd"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    chk("pp.py 统一入口（列表+未知命令 rc=2）",
        _pp.returncode == 0 and "detect" in _pp.stdout and _pp_bad.returncode == 2,
        f"rc={_pp.returncode}/{_pp_bad.returncode}")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as _rf:
        _rf.write(ZH_HUMAN); _route_f = _rf.name
    _pp_d = subprocess.run([sys.executable, str(SCRIPTS / "pp.py"), "detect", _route_f,
                            "--format", "json"], capture_output=True, text=True,
                           encoding="utf-8", timeout=180,
                           env={**os.environ, "PP_ORT_THREADS": "8"})
    Path(_route_f).unlink(missing_ok=True)
    try:
        _route_ok = _pp_d.returncode == 0 and isinstance(json.loads(_pp_d.stdout).get("overall_ai_score"), (int, float))
    except Exception:
        _route_ok = False
    chk("pp.py detect 路由可达引擎", _route_ok,
        f"rc={_pp_d.returncode}")
except Exception as _e:
    chk("SDK import + detect_text 出分", False, f"exception: {_e}")

# pp_setup: --check 与未知指纹拒绝
try:
    _p = subprocess.run([sys.executable, str(SCRIPTS / "pp_setup.py"), "--check"],
                        capture_output=True, text=True, encoding="utf-8", timeout=180,
                        env={**os.environ, "PP_ORT_THREADS": "8"})
    chk("pp_setup --check 可跑", _p.returncode in (0, 1), f"rc={_p.returncode}")
    _fake = Path(tempfile.mkdtemp()) / "fake.onnx"
    _fake.write_bytes(b"not a model")
    _p2 = subprocess.run([sys.executable, str(SCRIPTS / "pp_setup.py"), "--model", str(_fake)],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    chk("pp_setup 未知指纹拒绝(exit 2)", _p2.returncode == 2, f"rc={_p2.returncode}")
    _shutil_f.rmtree(_fake.parent, ignore_errors=True)
except Exception as _e:
    chk("pp_setup --check 可跑", False, f"exception: {_e}")

# 零网络契约在新增接口上依然成立（SKILL.md 的 grep 零命中承诺）
import re as _re
_bad_net = []
for _n in ("pp_api.py", "pp_setup.py"):
    _src = (SCRIPTS / _n).read_text(encoding="utf-8")
    if _re.search(r"import\s+(socket|http|urllib|requests)|from\s+(socket|http|urllib|requests)", _src):
        _bad_net.append(_n)
chk("SDK/装模零网络导入", not _bad_net, "; ".join(_bad_net))

# ───────────────────────── 汇总 ─────────────────────────
failed = [r for r in results if not r[1]]
print("────────────────────────────────")
print(f"[汇总] total={len(results)} pass={len(results)-len(failed)} fail={len(failed)} "
      f"-> {'GREEN' if not failed else 'RED'}")
sys.exit(0 if not failed else 1)
