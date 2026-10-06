#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pp_workflow.py — 一条命令的端到端自查工作流（v4.6.0 新增）

回应官方评测 docQuality 项：把分散的六个检查收成一次调用，产出单一综合报告。
串联：AI率检测（融合引擎）→ 段落级归因 → 四层降AI门禁 → 术语保护 → 翻译腔 →
文体距离 → 质量报告 → AIGC 合规标识自查，输出 JSON + Markdown 双格式。

用法：
  python3 scripts/pp_workflow.py draft.txt [--outdir 报告目录] [--lang auto]
  # 产物: draft.workflow.json + draft.workflow.md（同目录）

编程接口:
  from pp_api import workflow            # 返回综合 JSON dict（不落盘）
  r = workflow("文本" * 200)
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
GITHUB_URL = "https://github.com/docsor1212/paper-polisher-pro"
SH_URL = "https://skillhub.cn/skills/indiv-sorsor/paper-polisher-pro"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def workflow(text: str, lang: str = "auto") -> dict:
    """端到端自查：一次调用返回全部检查结果（JSON 兼容 dict）。

    键: detect / paragraphs / gate / terms / smell / style / quality /
        aigc_label / integrity_notice / engine_version / generated_at
    异常语义与 pp_api 一致：输入不合法 ValueError，运行失败 RuntimeError。
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text 必须是非空字符串")
    import ai_detector
    import pp_api

    result = {"engine_version": pp_api.engine_version(),
              "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "length_chars": len(text)}

    # 1) 融合检测（含监督层/降级披露/混写预警）
    rep = ai_detector.detect(text, lang=lang)
    result["detect"] = pp_api._asdict(rep)

    # 2) 段落级归因（与 paragraph_report.py 同口径：混合段落分+融合阈值分级）
    fc = ai_detector._load_fusion_config() or {}
    thr = fc.get("thresholds", {"medium": 0.35, "high": 0.60})
    tm, th = float(thr["medium"]) * 100, float(thr["high"]) * 100
    paras = ai_detector.split_paragraphs(text)
    blend = ai_detector.blended_paragraph_scores(text, rep)
    rows, n_hi, n_med = [], 0, 0
    for j, p in enumerate(rep.paragraph_scores):
        idx = min(p.get("index", 0), max(len(paras) - 1, 0))
        raw = paras[idx] if idx < len(paras) else p.get("text", "")
        s = blend[j] if j < len(blend) else p.get("ai_score", 0)
        cls = "hi" if s >= th else ("med" if s >= tm else "lo")
        n_hi += cls == "hi"
        n_med += cls == "med"
        rows.append({"index": j + 1, "score": round(float(s), 1), "class": cls,
                     "excerpt": raw.strip().replace("\n", " ")[:60]})
    result["paragraphs"] = {"thresholds": {"medium": round(tm, 1), "high": round(th, 1)},
                            "total": len(rows), "high": n_hi, "medium": n_med,
                            "items": rows}

    # 2b) 混写文档评估（v4.7.0）：段落双峰或引擎混写预警 → 给出段落级定位结论
    n_lo = len(rows) - n_hi - n_med
    mixed_detected = bool(getattr(rep, "mixed_signal", False)) or (len(rows) >= 3 and n_hi > 0 and n_lo > 0)
    result["mixed_document"] = {
        "detected": mixed_detected,
        "hi": n_hi, "medium": n_med, "low": n_lo,
        "ai_paragraph_fraction_est": round((n_hi + 0.5 * n_med) / max(len(rows), 1), 2),
        "measured": {"document_level_auroc": "0.52-0.54",
                     "paragraph_level_auroc": 0.6883,
                     "source": "eval/results/mixed_para_20261005.json (n=54 docs/333 paras, model_fp 2631df3d388b)"},
        "guidance": ("文档级分数不可单独采信（混写会稀释/顶起文档级均分，实测文档级 AUROC 0.52-0.54）；"
                     "上方段落级排序可用于人工复核定位（实测段落级 AUROC 0.69，triage 质量而非自动判定）。")
        if mixed_detected else "",
    }

    # 3) 四层门禁
    result["gate"] = pp_api.gate_text(text)
    # 4-6) 术语 / 翻译腔 / 文体
    result["terms"] = pp_api.term_report(text)
    result["smell"] = pp_api.smell_report(text)
    result["style"] = pp_api.style_report(text)
    # 7) 质量报告 / 8) AIGC 合规标识（文件口径，临时文件中转）
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        import quality_report
        result["quality"] = pp_api._asdict(quality_report.generate_report(tmp))
        import aigc_label_check
        result["aigc_label"] = {"evidence": aigc_label_check.check_text(tmp),
                                "note": "显式标识自查；元数据/C2PA 检查用 aigc_label_check.py 对成品文件运行"}
    except Exception as e:
        raise RuntimeError("workflow 质量检查失败: %s" % e) from e
    finally:
        Path(tmp).unlink(missing_ok=True)

    result["integrity_notice"] = ("本工作流供作者自查与改进写作质量，不用于规避机构 AIGC 检测；"
                                  "请遵循所在机构 AI 使用与披露政策。")
    return result


def to_markdown(r: dict) -> str:
    """综合 JSON → Markdown 报告（人工可读版）。"""
    d = r["detect"]
    p = r["paragraphs"]
    lines = [
        "# 端到端自查报告",
        "",
        "- 引擎版本: %s ｜ 生成时间: %s ｜ 长度: %d 字" % (
            r["engine_version"], r["generated_at"], r["length_chars"]),
        "- **AI 率: %s / 风险档: %s** ｜ 引擎档位: %s" % (
            d.get("overall_ai_score"), d.get("overall_risk"),
            "完整（监督层融合）" if d.get("degraded_mode") is False else "降级（纯规则+词频谱）"),
        "- 诚信声明: %s" % r["integrity_notice"],
        "",
        "## 1. 段落级归因",
        "",
        "阈值 @medium %.0f / @high %.0f ｜ 高风险段 %d / 中风险段 %d / 共 %d 段" % (
            p["thresholds"]["medium"], p["thresholds"]["high"], p["high"], p["medium"], p["total"]),
        "",
    ]
    mx = r.get("mixed_document") or {}
    if mx.get("detected"):
        lines += [
            "> ⚠️ **混写文档**（疑似人机混写：高/低分段并存或引擎混写预警）",
            "> 估计 AI 段占比 ≈ %s ｜ 文档级 AUROC 0.52-0.54（原理性弱）｜ 段落级 AUROC 0.69（可用于定位，非自动判定）" % mx.get("ai_paragraph_fraction_est"),
            "> 以下为高分/中风险段，建议逐段人工复核：",
            "",
        ]
    for it in p["items"]:
        if it["class"] != "lo":
            lines.append("- 段%d [%s %.0f] %s…" % (it["index"], it["class"], it["score"], it["excerpt"]))
    lines += [
        "",
        "## 2. 四层降AI门禁",
        "",
        "- 复合风险: %s ｜ 判定: %s" % (r["gate"].get("composite_ai_risk"), r["gate"].get("verdict")),
        "",
        "## 3. 术语保护",
        "",
        "- 标准率: %s%% ｜ 待处理: %s 处" % (r["terms"].get("standardization_rate"), r["terms"].get("total_issues")),
        "",
        "## 4. 翻译腔",
        "",
        "- 命中: %s 处" % r["smell"].get("total_hits"),
        "",
        "## 5. 文体距离",
        "",
        "- 文体分: %s（%s）" % (r["style"].get("style_score"), r["style"].get("verdict")),
        "",
        "## 6. 质量报告",
        "",
    ]
    q = r.get("quality") or {}
    q_labels = (("total_chars", "总字数"), ("total_paragraphs", "总段数"),
                ("readability_score", "可读性"), ("overall_quality", "总体质量"))
    for k, lab in q_labels:
        if k in q:
            lines.append("- %s: %s" % (lab, q[k]))
    lines += [
        "",
        "## 7. AIGC 合规标识自查",
        "",
        "- 显式标识证据: %d 条" % len((r.get("aigc_label") or {}).get("evidence", [])),
        "",
        "---",
        "逐项完整数据见同名 .workflow.json。",
        "",
        "> 本文档由 Paper Polisher Pro 生成（[GitHub](https://github.com/docsor1212/paper-polisher-pro) · "
        "[SkillHub](https://skillhub.cn/skills/indiv-sorsor/paper-polisher-pro)）· 觉得有用欢迎 Star / 收藏",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("--outdir", default=None, help="报告输出目录（默认与输入同目录）")
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en"])
    a = ap.parse_args()
    p = Path(a.file)
    if not p.is_file():
        print("ERROR: 文件不存在: %s" % p, file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text.strip()) < 100:
        print("ERROR: 文本不足 100 字（铁律 2：短文本不出判定）——请提交 100 字以上（建议 300+）", file=sys.stderr)
        return 2
    try:
        r = workflow(text, lang=a.lang)
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    outdir = Path(a.outdir) if a.outdir else p.parent
    outdir.mkdir(parents=True, exist_ok=True)
    jf = outdir / (p.stem + ".workflow.json")
    mf = outdir / (p.stem + ".workflow.md")
    jf.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    mf.write_text(to_markdown(r), encoding="utf-8")
    d = r["detect"]
    print("AI率 %s / %s ｜ 段落 hi/med/total = %d/%d/%d ｜ 门禁 %s(%s)" % (
        d.get("overall_ai_score"), d.get("overall_risk"),
        r["paragraphs"]["high"], r["paragraphs"]["medium"], r["paragraphs"]["total"],
        r["gate"].get("verdict"), r["gate"].get("composite_ai_risk")))
    print("报告: %s" % mf)
    print("数据: %s" % jf)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
