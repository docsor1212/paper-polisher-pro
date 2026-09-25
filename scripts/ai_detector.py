#!/usr/bin/env python3
"""
AI Writing Detector — paper-polisher v1.2.0
Quantitative AI trace detection for academic text (Chinese + English).

v1.2.0 (2026-06-16): Added content_only_score field (excludes markdown_format false positives)
v1.1.0 (2026-05-02): Added Perplexity proxy (bigram/trigram diversity) + upgraded Burstiness

Usage:
    python3 ai_detector.py <input_file>
    python3 ai_detector.py <input_file> --lang zh|en|auto
    python3 ai_detector.py <input_file> --format json|text|summary
    python3 ai_detector.py <input_file> --output report.json
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# v1.1: Perplexity proxy module
try:
    from perplexity import compute_perplexity_metrics, score_perplexity as _score_ppl
    _PPL_AVAILABLE = True
except ImportError:
    _PPL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParagraphResult:
    index: int
    text: str
    lang: str  # "zh" | "en"
    ai_score: float  # 0-100, higher = more AI-like
    matched_patterns: list = field(default_factory=list)
    ttr: float = 0.0
    avg_sentence_len: float = 0.0
    sentence_len_variance: float = 0.0
    paragraph_len: int = 0
    # v1.1: Perplexity proxy metrics
    bigram_diversity: float = 0.0
    trigram_diversity: float = 0.0
    ppl_burstiness: float = 0.0
    perplexity_score: float = 0.0
    burstiness_score: float = 0.0  # sentence-level burstiness (upgraded uniformity)
    content_only_score: float = 0.0  # v1.2: score excluding markdown_format matches

@dataclass
class DetectionReport:
    file: str = ""
    overall_ai_score: float = 0.0
    overall_risk: str = "low"  # low | medium | high
    total_paragraphs: int = 0
    avg_ttr: float = 0.0
    avg_sentence_len: float = 0.0
    avg_sentence_len_variance: float = 0.0
    paragraph_scores: list = field(default_factory=list)
    top_patterns: list = field(default_factory=list)
    language: str = "auto"
    details: str = ""
    model_hints: list = field(default_factory=list)  # v4: 指纹归因(只用于报告,不参与打分)
    supervised: dict = field(default_factory=dict)   # v3.2: 本地监督层(ONNX)证据
    # v3.5: 降级模式披露——监督层缺席/被关/语言门控跳过时如实告知,并给出医学语域高估警示
    degraded_mode: bool = False
    degraded_notice: str = ""
    # v3.7.0: L12 篇章结构启发层——钩子/反转/口号/互动引导等篇章级 AI 腔(句层特征的盲区,
    # AgentOps LES-20260923-021: 此类文本句层分 21-32 未被察觉)
    discourse_hits: list = field(default_factory=list)
    discourse_bonus: float = 0.0
    # v3.6: 学术诚信护栏(SQP-2)——每份报告明示工具定位与披露义务
    integrity_notice: str = ""
    # v3.8: 混写预警——段落得分显著分化时提示文档级分数不可单独采信(混合文档 AUROC 0.38 的可操作化)
    mixed_signal: bool = False
    mixed_notice: str = ""
    # v3.8: 语域提示——口语/叙事语域超出学术校准域时如实告知(能力边界矩阵的引擎侧落地)
    register_hint: str = ""
    # v3.8: 编码警示——大量不可解码字节时提示结果可能失真
    encoding_warning: str = ""


def attribute_model(text: str, topn: int = 3) -> list:
    """v4 指纹归因：按 registry 中各家族模式加权命中数猜测来源模型。

    架构原则（2026-08-15 实测教训）：指纹注入检测层会使人类误报翻倍
    （AUROC 0.9187→0.8977），故指纹只做归因报告，不进分数。
    """
    try:
        rp = Path(__file__).parent.parent / "references" / "model_fingerprints.json"
        reg = json.load(open(rp, encoding="utf-8")).get("families", {})
    except Exception:
        return []
    scores = {}
    for fam, d in reg.items():
        s = 0.0
        for p in d.get("patterns", []):
            if p["p"] in text:
                s += p.get("w", 2)
        if s > 0:
            scores[fam] = round(s, 1)
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:topn]
    total = sum(v for _, v in ranked) or 1
    return [{"family": f, "hits": v, "confidence": round(v / total, 2)} for f, v in ranked]


# ---------------------------------------------------------------------------
# Language detection helpers
# ---------------------------------------------------------------------------

def detect_lang(text: str) -> str:
    """文档级语言判定: CJK占字母类字符比>30% → zh。
    v3.4.2修复: 旧版分母 alpha+cjk 重复计入CJK(alpha含CJK), 中文期刊PDF(英文摘要+参考文献)
    被误判en, 进而触发监督层语言门控跳过; 另加绝对量兜底(中文正文+英文附件的长文档)。"""
    cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf')
    latin = sum(1 for ch in text if ch.isalpha() and not (
        '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf'))
    total = max(cjk + latin, 1)
    r = cjk / total
    return "zh" if r > 0.3 or (cjk >= 1000 and r > 0.2) else "en"


# ---------------------------------------------------------------------------
# Text statistics
# ---------------------------------------------------------------------------

def split_sentences(text: str, lang: str) -> list:
    if lang == "zh":
        parts = re.split(r'[。！？；\n]+', text)
    else:
        parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [s.strip() for s in parts if s.strip()]


def tokenize(text: str, lang: str) -> list:
    """Tokenize text. For mixed content, extract both CJK chars and English words."""
    cjk = [ch for ch in text if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf']
    en = re.findall(r"[a-zA-Z]+(?:'[a-z]+)?", text.lower())
    if lang == "zh":
        return cjk if cjk else en  # fallback to en if no CJK
    else:
        return en if en else cjk  # fallback to CJK if no English


def calc_ttr(tokens: list) -> float:
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def calc_info_density(text: str, lang: str) -> float:
    """Calculate information density: ratio of content chars after removing stopwords.
    
    AI text has anomalously high info density (0.85-0.90) because it 
    compresses information densely. Human text has more filler/function 
    words (0.75-0.84). This is a powerful signal for newer models that 
    avoid cliché patterns.
    """
    if lang == "zh":
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        if not chars:
            return 0.0
        stopwords = set('的了是在有被人与和中为而从这那以可将对上但到又要就也都能很好很更还又再已其所如该本即或没得之于让把向吗吧呢啊呀嗯')
        content = [c for c in chars if c not in stopwords]
        return len(content) / len(chars)
    else:
        words = text.lower().split()
        if not words:
            return 0.0
        stopwords = {'the','a','an','is','are','was','were','be','been','being',
                     'in','on','at','to','for','of','with','by','from','as',
                     'it','its','this','that','these','those','and','or','but',
                     'not','no','do','does','did','has','have','had','will',
                     'would','could','should','can','may','might','shall'}
        content = [w for w in words if w not in stopwords]
        return len(content) / len(words)


def sentence_length_stats(sentences: list, lang: str) -> tuple:
    if not sentences:
        return 0.0, 0.0
    if lang == "zh":
        lengths = [len(s) for s in sentences]
    else:
        lengths = [len(s.split()) for s in sentences]
    avg = sum(lengths) / len(lengths)
    if len(lengths) > 1:
        var = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    else:
        var = 0.0
    return round(avg, 1), round(var, 1)


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def load_patterns(lang: str) -> dict:
    ref_dir = Path(__file__).parent.parent / "references"
    fname = f"ai_patterns_{lang}.json"
    fpath = ref_dir / fname
    if not fpath.exists():
        return {}
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f).get("categories", {})


_fusion_cfg_cache = None


def _load_fusion_config():
    """v3 融合配置（calibrate_v3.py 生成）。缺失返回 None，引擎回退旧行为。"""
    global _fusion_cfg_cache
    if _fusion_cfg_cache is None:
        try:
            p = Path(__file__).parent.parent / "references" / "fusion_config.json"
            if p.exists():
                _fusion_cfg_cache = json.load(open(p, encoding="utf-8"))
            else:
                _fusion_cfg_cache = {}
        except Exception:
            _fusion_cfg_cache = {}
    return _fusion_cfg_cache or None


def match_patterns(text: str, categories: dict) -> list:
    """Return list of {pattern, category, weight} matches."""
    results = []
    text_lower = text.lower()
    for cat_name, cat_data in categories.items():
        weight = cat_data.get("weight", 1)
        for pat in cat_data.get("patterns", []):
            if "." in pat or "[" in pat or "(" in pat or "{" in pat:
                # regex pattern
                try:
                    if re.search(pat, text, re.IGNORECASE):
                        results.append({"pattern": pat, "category": cat_name, "weight": weight})
                except re.error:
                    continue
            else:
                # literal match (case-insensitive)
                if pat.lower() in text_lower:
                    results.append({"pattern": pat, "category": cat_name, "weight": weight})
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def match_sentence_patterns(text: str, lang: str) -> list:
    """Match text against known AI sentence templates. Returns list of matched pattern IDs."""
    if lang != "zh":
        return []  # ZH patterns only for now
    
    ref_dir = Path(__file__).parent.parent / "references"
    fpath = ref_dir / "sentence_patterns_zh.json"
    if not fpath.exists():
        return []
    
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    
    matched = []
    text_clean = text.replace(" ", "").replace("\n", "")
    
    for pat in data.get("patterns", []):
        # Convert template pattern to regex
        # Replace {placeholder} with wildcard
        template = pat["pattern"].replace(" ", "")
        # Escape special regex chars except {}
        import re as _re
        regex_str = _re.escape(template)
        # Replace escaped {xxx} with wildcard
        regex_str = _re.sub(r'\\{[^}]+\\}', '.{1,20}', regex_str)
        try:
            if _re.search(regex_str, text_clean):
                matched.append({
                    "id": pat["id"],
                    "category": pat["category"],
                    "pattern": pat["pattern"],
                    "ai_frequency": pat.get("ai_frequency", "medium"),
                })
        except _re.error:
            continue
    
    return matched


def score_paragraph(text: str, lang: str, categories: dict) -> ParagraphResult:
    matches = match_patterns(text, categories)  # v3: 只调用一次（v2 在:237/:246 重复调用）
    tokens = tokenize(text, lang)
    sentences = split_sentences(text, lang)
    ttr = calc_ttr(tokens)
    avg_slen, slen_var = sentence_length_stats(sentences, lang)

    para_len = len(text)

    # --- Pattern match score (proportional, no hard cap) ---
    # v3: markdown_format 类贡献上限 2 分（v2 中一条 **加粗** = 8 分直加，误报机器）
    md_pts = sum(m["weight"] for m in matches if m["category"] == "markdown_format")
    md_cap = min(md_pts, 2)
    match_score = sum(m["weight"] for m in matches if m["category"] != "markdown_format") + md_cap
    pattern_points = min(match_score / 15.0, 1.0) * 50
    sentence_pat_matches = match_sentence_patterns(text, lang)

    # v1.2: content_only_score — pattern points excluding markdown_format (reduces 92%+ false positive rate)
    content_match_score = sum(m["weight"] for m in matches if m["category"] != "markdown_format")
    content_pattern_points = min(content_match_score / 15.0, 1.0) * 50
    
    # --- Sentence template match score (v1.1) ---
    # Each matched template adds points based on ai_frequency
    sent_tmpl_score = 0.0
    for sp in sentence_pat_matches:
        freq = sp.get("ai_frequency", "medium")
        if freq == "very_high":
            sent_tmpl_score += 3.0
        elif freq == "high":
            sent_tmpl_score += 2.0
        else:
            sent_tmpl_score += 1.0
    # Cap at 10 points
    sent_tmpl_score = min(sent_tmpl_score, 10.0)

    # --- TTR penalty: very uniform vocabulary → AI-like ---
    if lang == "zh":
        ttr_score = max(0, (0.5 - ttr) / 0.3) * 15
    else:
        ttr_score = max(0, (0.6 - ttr) / 0.3) * 15

    # --- Burstiness score (v1.1: upgraded from simple uniformity) ---
    # Combines: (1) sentence length CV, (2) adjacent sentence jumps,
    # (3) sentence length range ratio
    sentences_list = split_sentences(text, lang)
    if lang == "zh":
        slens = [len(s) for s in sentences_list]
    else:
        slens = [len(s.split()) for s in sentences_list]

    if len(slens) >= 3 and avg_slen > 0:
        # Component A: CV of sentence lengths (original metric, refined)
        cv = math.sqrt(slen_var) / avg_slen
        cv_score = max(0, (0.45 - cv) / 0.30) * 6  # 0-6 pts (v1.1.1: lowered from 8 to reduce FP)

        # Component B: Adjacent sentence jump consistency
        # AI: jumps are large but regular (systematic); Human: jumps vary more
        # Key insight: AI sentences tend to be uniformly LONG (avg 28-38 chars ZH)
        # Human sentences are shorter with more variation (avg 15-22 chars ZH)
        diffs = [abs(slens[i] - slens[i+1]) for i in range(len(slens)-1)]
        avg_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs)
        # The key signal is: high avg sentence length + low range ratio = AI
        # Jump score only matters when sentences are uniformly long
        if lang == "zh":
            if avg_slen > 30:  # AI tends to have avg sentence length > 30
                jump_score = max(0, (12 - avg_diff) / 12) * 6
            else:
                jump_score = max(0, (8 - avg_diff) / 8) * 3  # Lower weight for shorter text
        else:
            if avg_slen > 15:  # EN AI tends to have longer sentences
                jump_score = max(0, (5 - avg_diff) / 5) * 6
            else:
                jump_score = max(0, (3 - avg_diff) / 3) * 3

        # Component C: Sentence length range ratio (max/min)
        min_slen = min(slens)
        if min_slen > 0:
            range_ratio = max(slens) / min_slen
            # AI: ratio 1.0-1.3 (uniform), Human: ratio 1.5-5.0+ (varied)
            # v1.1.1 fix: lowered threshold from 1.5→1.3 to reduce false positives
            # on formal academic text with moderately uniform sentences
            if range_ratio < 1.2:
                range_score = 6.0
            elif range_ratio < 1.3:
                range_score = 4.0
            elif range_ratio < 1.8:
                range_score = 1.0
            else:
                range_score = 0.0
        else:
            range_score = 3.0

        burstiness_score = cv_score + jump_score + range_score  # 0-20 pts total
    elif len(slens) == 2 and avg_slen > 0:
        # Two sentences: only CV available
        cv = math.sqrt(slen_var) / avg_slen
        burstiness_score = max(0, (0.45 - cv) / 0.30) * 20
    else:
        burstiness_score = 10  # single sentence = can't assess = moderate default

    # --- Paragraph length bonus (AI likes medium-long paragraphs) ---
    if lang == "zh":
        ideal_range = (80, 300)
    else:
        ideal_range = (40, 200)
    length_score = 5 if ideal_range[0] <= para_len <= ideal_range[1] else 0

    # --- Information density penalty (catches evolved AI models) ---
    # AI text: 0.86-0.90 (anomalously dense), Human: 0.75-0.85
    # Use density as an AMPLIFIER when patterns are also present, not standalone
    info_density = calc_info_density(text, lang)
    if lang == "zh" and para_len >= 50:
        if info_density >= 0.86:
            # High density: amplify existing pattern signals by 1.5x
            density_score = min(pattern_points * 0.5, 15)
        elif info_density >= 0.84:
            density_score = min(pattern_points * 0.3, 8)
        else:
            density_score = 0
    elif lang == "en" and para_len >= 30:
        if info_density >= 0.65:
            density_score = 8
        elif info_density >= 0.58:
            density_score = 4
        else:
            density_score = 0
    else:
        density_score = 0

    # --- Sentence opener diversity (catches evolved AI models) ---
    # AI text frequently uses PREP/CONN sentence openers ("在...中", "然而", "综上")
    # Human text almost always starts with direct subject (0% PREP/CONN)
    # v3: 补英文连接词表（v2 英文段落此层恒 0 分）
    _EN_OPENERS = re.compile(
        r'^(however|moreover|furthermore|therefore|thus|additionally|in addition|'
        r'consequently|nevertheless|nonetheless|meanwhile|subsequently|firstly|'
        r'secondly|finally|in conclusion|overall|based on|according to|given that)\b', re.I)
    if len(sentences) >= 3:
        prep_conn_openers = 0
        for s in sentences:
            s = s.strip()
            if len(s) < 3:
                continue
            if lang == "zh":
                first3 = s[:3]
                if re.match(r'^(然而|尽管|此外|因此|不过|从而|进而|综上|基于|同时|鉴于|另外|其次|最后|关于|对于|通过|根据|由于|虽然)', first3):
                    prep_conn_openers += 1
                elif re.match(r'^在', first3) and re.search(r'[中上下面里]', s[:15]):
                    prep_conn_openers += 1
                elif re.match(r'^而', first3):
                    prep_conn_openers += 1
            else:
                if _EN_OPENERS.match(s):
                    prep_conn_openers += 1
        opener_ratio = prep_conn_openers / len(sentences)
        if opener_ratio >= 0.4:
            opener_score = 10  # very AI-like: 40%+ sentences start with connectors
        elif opener_ratio >= 0.25:
            opener_score = 5
        else:
            opener_score = 0
    else:
        opener_score = 0

    # --- Short text: scale down but don't zero out (B1/B2 fix) ---
    raw_score = pattern_points + sent_tmpl_score + ttr_score + burstiness_score + length_score + density_score + opener_score

    # --- v1.1: Perplexity proxy (n-gram diversity + burstiness) ---
    ppl_score = 0.0
    ppl_metrics = {}
    if _PPL_AVAILABLE:
        ppl_metrics = compute_perplexity_metrics(text, lang)
        ppl_score = _score_ppl(text, lang, para_len)
    raw_score += ppl_score

    if para_len < 30:
        # Scale proportionally instead of zeroing
        scale = max(para_len / 30.0, 0.2)
        ai_score = raw_score * scale
        content_only_score = (raw_score - pattern_points + content_pattern_points) * scale
    else:
        ai_score = min(100, raw_score)
        content_only_score = min(100, raw_score - pattern_points + content_pattern_points)

    return ParagraphResult(
        index=0,
        text=text[:200] + ("..." if len(text) > 200 else ""),
        lang=lang,
        ai_score=round(ai_score, 1),
        matched_patterns=matches,
        ttr=round(ttr, 3),
        avg_sentence_len=avg_slen,
        sentence_len_variance=slen_var,
        paragraph_len=para_len,
        bigram_diversity=ppl_metrics.get("bigram_diversity", 0.0),
        trigram_diversity=ppl_metrics.get("trigram_diversity", 0.0),
        ppl_burstiness=ppl_metrics.get("burstiness", 0.0),
        perplexity_score=ppl_score,
        burstiness_score=burstiness_score,
        content_only_score=round(content_only_score, 1),
    )


# ---------------------------------------------------------------------------
# Main detection
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> list:
    """Split text into paragraphs.
    v3.4.2: PDF抽取文本常见单行硬换行(实测61%行<25字)导致千级碎片段落, 段落统计全废;
    退化时先按句末标点聚合成~200字以上的伪段落再统计。"""
    paras = re.split(r'\n\s*\n|\n', text)
    paras = [p.strip() for p in paras if p.strip() and len(p.strip()) > 3]
    # v3.4.3: markdown表格分隔行(|----|)非正文, 参与段落评分产生假阳性(实测MD稿件8个标记段中6个是分隔行)
    paras = [p for p in paras if not re.fullmatch(r'[\s|:\-\u2014\u2013=]+', p)]
    if len(paras) < 40:
        return paras
    short = sum(1 for p in paras if len(p) < 25)
    if short / len(paras) < 0.5:
        return paras
    SENT_END = "。！？；"
    merged, buf = [], ""
    for p in paras:
        buf += p
        if buf[-1:] in SENT_END and len(buf) >= 200:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged if len(merged) >= 10 else paras


def detect(text: str, lang: str = "auto") -> DetectionReport:
    forced = lang in ("zh", "en")
    if lang == "auto":
        lang = detect_lang(text)  # 文档级语言(监督层门控/主模式集)

    categories = load_patterns(lang)
    # v3: 中英混排文档按段落级判语言（v2 全文单一判定，英文段落被按中文算）
    # v3.4.2: 入口即归一lang导致该路由从未生效(dead code), 改为仅显式指定语言时锁死
    categories_alt = load_patterns("en" if lang == "zh" else "zh")
    paragraphs = split_paragraphs(text)

    if not paragraphs:
        return DetectionReport(
            overall_risk="unknown",
            details="文本过短或无法分段，无法进行检测。"
        )

    results = []
    all_matches = []
    for i, para in enumerate(paragraphs):
        plang = detect_lang(para) if not forced else lang
        cats = categories if plang == lang else categories_alt
        r = score_paragraph(para, plang, cats)
        r.index = i
        results.append(r)
        all_matches.extend(r.matched_patterns)

    # Weighted overall score
    if results:
        # Weight by paragraph length
        total_len = sum(r.paragraph_len for r in results)
        if total_len > 0:
            overall = sum(r.ai_score * r.paragraph_len for r in results) / total_len
        else:
            overall = sum(r.ai_score for r in results) / len(results)
    else:
        overall = 0

    # --- Layer A: paragraph length uniformity (document-level stylometry) ---
    # AI text: paragraphs uniformly sized (low CV); Human: high variance (CV high).
    # Only applies when there are enough paragraphs to compare (>=4).
    uniformity_penalty = 0.0
    if len(results) >= 4:
        para_lens = [r.paragraph_len for r in results]
        mean_len = sum(para_lens) / len(para_lens)
        if mean_len > 0:
            std_len = (sum((x - mean_len) ** 2 for x in para_lens) / len(para_lens)) ** 0.5
            cv = std_len / mean_len  # coefficient of variation
            # CV < 0.25 = very uniform (strong AI signal), < 0.4 = somewhat uniform
            # Human academic writing typically CV 0.5-1.0
            if cv < 0.15:
                uniformity_penalty = 8.0   # extremely uniform → strong AI signal
            elif cv < 0.25:
                uniformity_penalty = 5.0
            elif cv < 0.35:
                uniformity_penalty = 2.0
            # cv >= 0.35: human-like variance, no penalty (避免误伤人类综述)
            # Record CV in details for transparency
            results_meta = {"paragraph_cv": round(cv, 3), "uniformity_penalty": uniformity_penalty}
        else:
            results_meta = {"paragraph_cv": None, "uniformity_penalty": 0.0}
    else:
        results_meta = {"paragraph_cv": None, "uniformity_penalty": 0.0,
                        "note": "too few paragraphs (<4) to assess uniformity"}

    # Apply document-level uniformity penalty to overall score
    overall = min(100.0, overall + uniformity_penalty)

    # --- v3: 表面层(L9/L10/L11) + 长度路由融合（EnsemJudge 策略）---
    # 权重与阈值由 calibrate_v3.py 在评测语料上网格搜索得出, 存 references/fusion_config.json
    surface_meta = None
    fc = _load_fusion_config()
    if fc:
        try:
            import layers_surface as _LS
            lay = _LS.all_surface_layers(text)
            total_chars = sum(len(p) for p in paragraphs)
            band = "short" if total_chars < 300 else ("mid" if total_chars < 800 else "long")
            w = (fc.get("bands", {}).get(band) or {}).get("weights") or \
                {"para": 0.8, "spectrum": 0.1, "surface": 0.05, "cot": 0.05}
            fused = (w.get("para", 0.8) * (overall / 100.0)
                     + w.get("spectrum", 0.1) * lay["spectrum"]["score"] / 10.0
                     + w.get("surface", 0.05) * lay["surface"]["score"] / 10.0
                     + w.get("cot", 0.05) * lay["cot"]["score"] / 10.0)
            # 混合人机文档防线: 文档级平均会被人类段落稀释(实测混合攻击AUROC 0.15),
            # 引入段落 p90 分量——只要存在高AI特征段落就顶起总分
            if results:
                ps = sorted(r.ai_score for r in results)
                p90 = ps[min(len(ps) - 1, int(0.9 * (len(ps) - 1)))] / 100.0
                fused = max(fused, 0.75 * fused + 0.25 * p90)
            overall = round(fused * 100.0, 1)
            surface_meta = {"band": band, "weights": w, "layers": lay}
        except Exception:
            pass

    # --- v3.2: 监督层融合 fusion v2 (本地 ONNX Qwen3-0.6B LoRA, 可选增强) ---
    # fused_v2 = v3.0_fused*(1-w) + p_ai_supervised*w; 无模型时自动跳过, 分数不变
    # v3.4.1: 语言门控——监督层只用中文语料训练, 英文文本会被OOD误判为AI(实测p=0.9996),
    # 非中文文本不融合, 回退纯规则评分
    sup_meta = None
    sup_skip = None  # v3.5: 监督层未参与融合的原因(降级披露)
    if os.environ.get("PP_NO_SUP") or lang == "en":  # 校准/对比用: 置PP_NO_SUP=1拿纯引擎分
        sup = None
        sup_skip = "PP_NO_SUP=1: supervised layer disabled by env" if os.environ.get("PP_NO_SUP") \
            else "language gating: non-Chinese text skips supervised layer (EN trained OOD)"
    else:
        try:
            import layers_lm as _LLM
            sup = _LLM.supervised_layer(text)
            if sup is None:
                sup_skip = "supervised layer not installed (optional enhancement)"
        except Exception:
            sup = None
            sup_skip = "supervised layer not installed (optional enhancement)"
    if sup:
        v2 = (fc or {}).get("v2") or {}
        wsup = float(v2.get("w_supervised", 0.9))
        overall = round(((1.0 - wsup) * (overall / 100.0) + wsup * sup["p_ai_any"]) * 100.0, 1)
        sup_meta = {"layer": "qwen3-0.6b-lora-onnx-int8",
                    "p_human": sup["p_human"], "p_ai": sup["p_ai"],
                    "p_ai_assisted": sup["p_ai_assisted"], "p_ai_any": sup["p_ai_any"],
                    "n_tokens": sup.get("n_tokens")}
        if "edit_extent" in sup:
            sup_meta["edit_extent"] = sup["edit_extent"]

    # v3.7.0: L12 篇章结构启发层——自媒体"钩子+反转+口号"三件套等篇章级 AI 腔。
    # 只在中文、≥2 组独立结构命中时给文档级加分(2 组+12, ≥3 组+20, 封顶 20)；
    # 学术语料几乎不命中(回归见 eval/results/v370_release.json)，主要修复自媒体/叙事语域盲区。
    discourse_hits = []
    discourse_bonus = 0.0
    if lang == "zh" and len(text.strip()) >= 100:
        for _gname, _rx in _DISCOURSE_ZH:
            _ms = _rx.findall(text)
            if _ms:
                discourse_hits.append({"group": _gname, "count": len(_ms),
                                       "samples": list(dict.fromkeys(_ms))[:2]})
        if len(discourse_hits) >= 2:
            _hits_total = sum(h["count"] for h in discourse_hits)
            discourse_bonus = float(min(30, 8 * len(discourse_hits) + min(_hits_total, 8)))
            overall = min(100.0, overall + discourse_bonus)

    # Top patterns
    pat_counter = Counter(m["pattern"] for m in all_matches)
    top = [{"pattern": p, "count": c} for p, c in pat_counter.most_common(10)]

    # Risk level (v3: 阈值来自校准配置——人类语料 p95/p99；无配置时回退旧值)
    thr_medium = (fc or {}).get("thresholds", {}).get("medium", 0.35)
    thr_high = (fc or {}).get("thresholds", {}).get("high", 0.60)
    if sup_meta:  # v3.2: 监督层激活时用 fusion v2 阈值(针对0.9监督权重的融合分布校准)
        v2thr = ((fc or {}).get("v2") or {}).get("thresholds") or {}
        thr_medium = v2thr.get("medium", thr_medium)
        thr_high = v2thr.get("high", thr_high)
    if isinstance(thr_medium, float) and thr_medium <= 1.0:
        thr_medium *= 100
        thr_high *= 100
    if overall >= thr_high:
        risk = "high"
    elif overall >= thr_medium:
        risk = "medium"
    else:
        risk = "low"

    # v3.5: 落实铁律2——<100字文本不输出风险判定(学界教训:短文本误报失控)
    short_text = len(text.strip()) < 100
    if short_text:
        risk = "unknown"

    # Detail summary
    details = _build_summary(results, lang, risk, overall)
    if sup_meta:
        _ln = (f"\n监督层(本地Qwen3 int8): p(人类)={sup_meta['p_human']:.3f} "
               f"p(AI)={sup_meta['p_ai']:.3f} p(AI辅助)={sup_meta['p_ai_assisted']:.3f} "
               f"融合分={overall:.1f}")
        if "edit_extent" in sup_meta:
            _ln += f" 编辑程度估计={sup_meta['edit_extent']:.2f}"
        details += _ln

    # v3.5: 降级模式披露(诚实原则:让用户知道当前跑的是哪档引擎、短板在哪)
    degraded_notice = ""
    if sup_skip:
        _zh = lang == "zh"
        if "language gating" in sup_skip:
            degraded_notice = (
                "⚠️ 英文模式(语言门控): 监督层仅用中文语料训练,英文文本按设计跳过监督融合,"
                "当前为纯规则英文骨架评分,结论仅供参考。" if _zh else
                "⚠️ English mode (language gating): supervised layer is Chinese-trained and is "
                "skipped by design; rules-only English skeleton scoring, treat verdicts as advisory."
            )
        else:
            degraded_notice = (
                f"⚠️ 降级模式({sup_skip}): 当前为纯规则+词频谱评分。"
                "医学/学术语域会被系统性高估(留出集实测纯规则 @medium 档误报: 医学人类文本约59%、普通人类文本约2%)，"
                "医学文本的 @medium 档结论不可单独采信——只采信 @high 档,或安装可选监督层获得校准融合"
                "(见 SKILL.md『可选监督层启用』)。" if _zh else
                f"⚠️ Degraded mode ({sup_skip}): rules+spectrum scoring only. The rule engine "
                "over-scores medical/academic register (held-out rules-only human FPR at @medium: "
                "~59% medical, ~2% general); do not trust @medium verdicts on medical text — use "
                "@high, or install the optional supervised layer for calibrated fusion (see SKILL.md)."
            )
        details += "\n" + degraded_notice

    # v3.9: L13 surprisal-variation 披露(报告元数据, 不进融合分——单层信噪比不足,
    # 留出集实测检出 66/146、误报 1/14, 按"只报可复现的数字"原则降级为透明披露)
    if surface_meta and surface_meta.get("layers", {}).get("surprisal", {}).get("verdict") not in (None, "insufficient"):
        _sp = surface_meta["layers"]["surprisal"]
        if _sp["verdict"] == "smooth":
            details += ("\nℹ️ 篇幅平滑度特征: 句间用词变化性偏低(平滑度 %.0f/10, 谱覆盖 %.0f%%)——"
                        "常见于模板化生成文本, 已作为辅助线索列出(不参与评分)。"
                        % (_sp["score"], _sp["coverage"] * 100))
        elif _sp["verdict"] == "human":
            details += ("\nℹ️ 篇幅平滑度特征: 句间用词变化性较高(平滑度 %.0f/10)——"
                        "更像人类写作的波动模式(辅助线索, 不参与评分)。" % _sp["score"])

    # v3.6: 学术诚信护栏行
    details += "\n" + (INTEG_ZH if lang == "zh" else INTEG_EN)

    # v3.7.0: 篇章结构层披露
    if discourse_hits:
        _gs = "/".join(h["group"] for h in discourse_hits)
        _line = f"篇章结构特征: {_gs}" + (f"（结构加分 {discourse_bonus:.0f}）" if discourse_bonus else "（单组命中，仅提示不加分）")
        details += "\nℹ️ " + _line
    # v3.8: 混写预警——段落得分显著分化(混合人机文档文档级口径 AUROC 仅 0.38, 必须如实引导)
    mixed_signal = False
    mixed_notice = ""
    if len(results) >= 2:
        _ps = [r.ai_score for r in results]
        if (max(_ps) - min(_ps) >= 40) and max(_ps) >= 60 and min(_ps) <= 35:
            mixed_signal = True
    if mixed_signal:
        if lang == "zh":
            mixed_notice = ("⚠️ 混写预警：段落得分显著分化（最高 %.0f / 最低 %.0f），文档疑似人机混写。"
                            "文档级分数会被人类段落稀释，不可单独采信——请运行 paragraph_report.py 逐段归因。"
                            % (max(_ps), min(_ps)))
        else:
            mixed_notice = ("⚠️ Mixed-register signal: paragraph scores diverge sharply (max %.0f / min %.0f); "
                            "the document may combine human and AI writing. Document-level scores are unreliable "
                            "here — run paragraph_report.py for per-paragraph attribution."
                            % (max(_ps), min(_ps)))
        details += "\n" + mixed_notice

    # v3.8: 语域提示——口语/叙事语域超出学术校准域（能力边界矩阵的引擎侧落地）
    register_hint = ""
    if lang == "zh" and _COLLOQ_ZH.search(text):
        register_hint = ("语域提示：检测到口语/叙事表达特征，文体与整体评分按学术语域校准，"
                         "本场景结论仅供参考（见能力边界矩阵）。")
        details += "\n" + ("ℹ️ " + register_hint)

    # v3.8: 编码警示——大量不可解码字节（GBK/二进制按 replace 解码后 U+FFFD 密集）
    encoding_warning = ""
    if text.count("\ufffd") > 5:
        if lang == "zh":
            encoding_warning = ("编码警示：输入含大量无法解码的字节（已按替换规则解码为占位符），"
                                "文件可能为 GBK 等非 UTF-8 编码或二进制文件，当前结果可能失真，建议先转换编码。")
        else:
            encoding_warning = ("Encoding warning: many undecodable bytes were replaced; the file may be "
                                "non-UTF-8 (e.g. GBK) or binary, and results may be distorted. "
                                "Convert the encoding first.")
        details += "\n" + ("⚠️ " + encoding_warning)

    if short_text:
        details += ("\n⚠️ 文本不足100字：按铁律2不输出风险判定(risk=unknown)，分数仅供参考。"
                    if lang == "zh" else
                    "\n⚠️ Text under 100 chars: no risk verdict per iron law #2 (risk=unknown); "
                    "the numeric score is reference only.")

    return DetectionReport(
        file="",
        overall_ai_score=round(overall, 1),
        overall_risk=risk,
        total_paragraphs=len(results),
        avg_ttr=round(sum(r.ttr for r in results) / max(len(results), 1), 3),
        avg_sentence_len=round(sum(r.avg_sentence_len for r in results) / max(len(results), 1), 1),
        avg_sentence_len_variance=round(sum(r.sentence_len_variance for r in results) / max(len(results), 1), 1),
        paragraph_scores=[asdict(r) for r in results],
        top_patterns=top,
        language=lang,
        details=details,
        model_hints=attribute_model(text) if lang == "zh" else [],
        supervised=sup_meta or {},
        degraded_mode=bool(sup_skip),
        degraded_notice=degraded_notice,
        integrity_notice=INTEG_ZH if lang == "zh" else INTEG_EN,
        discourse_hits=discourse_hits,
        discourse_bonus=discourse_bonus,
        mixed_signal=mixed_signal,
        mixed_notice=mixed_notice,
        register_hint=register_hint,
        encoding_warning=encoding_warning,
    )


INTEG_ZH = "学术诚信提示：本工具供作者自查与改进写作质量（句式、术语、文风），不用于规避机构的 AIGC 检测，不支持将 AI 生成内容伪装为人类写作；请遵循所在机构的 AI 使用与披露政策（标识合规可用 aigc_label_check.py 自查）。"
INTEG_EN = "Academic integrity: this tool is for author self-review and writing-quality improvement — not for evading institutional AI-detection and not for misrepresenting AI-generated work; follow your institution's AI-use disclosure policies (aigc_label_check.py helps you comply)."


_DISCOURSE_ZH = (
    ("钩子", re.compile(r"先看(?:一个|这样一个)(?:场景|例子|数据)|想象一下|假设(?:这样)?一个场景|先讲(?:个|一个)故事|场景是这样的|不妨(?:设想|想象)|我(?:们)?先说个真实的事")),
    ("反转", re.compile(r"不是[^。，；\n]{1,30}[，,]\s*(?:而是|是)|真正的(?:原因|问题|答案)(?:其实|往往)是")),
    ("口号", re.compile(r"把(?:这|那)句话?记住|记住这句话|记住这个结论|一句话[：:]|划重点|敲黑板|建议收藏|看到这[里儿]不妨")),
    ("互动引导", re.compile(r"评论区(?:聊聊|讨论|见)|欢迎评论区|你怎么看[?？]|点个(?:关注|赞)|关注我[，,]")),
    ("排比三连", re.compile(r"一方面[^。\n]{2,60}另一方面|一个是[^。]{2,16}，另一个是|先是[^。]{2,16}接着[^。]{2,16}最后|(?:首先|其次|再来)[，,][^。]{6,30}[。；]?(?:其次|再来|最后)[，,]")),
    ("设问自答", re.compile(r"为什么[？?][^。\n]{0,40}(?:因为|答案|其实)|你(?:可能|一定)?会问[：:]|答案很简单[：:,，]?|那么?问题来了[：:,，]?|这背后的(?:原因|逻辑)是")),
    ("口播收尾", re.compile(r"(?:总之|综合来看|总的来说)[，,][^。]{2,30}(?:记住|建议|别再|一定要)|最后(?:再)?(?:强调|提醒)(?:一次|一下)|就(?:聊|说|讲)到这[里儿]?|今天这[篇期个]?(?:文章|视频|内容)")),
    ("情绪渲染", re.compile(r"扎心(?:了)?|破防(?:了)?|泪目|太真实了|细思极恐|狠狠(?:共情|破防)|绷不住了|直呼(?:内行|太)|绝了[!！]|离大谱")),
)
_COLLOQ_ZH = re.compile(r"[嘛呗哇啦咯嘿耶哟]|说实话|讲真|搞定|挺好的|蛮好|咱们|整点|一堆|贼好|超赞|靠谱|翻车|踩坑")


def _build_summary(results: list, lang: str, risk: str, score: float) -> str:
    if lang == "zh":
        risk_map = {"high": "🔴 高风险", "medium": "🟡 中等风险", "low": "🟢 低风险",
                    "unknown": "⚪ 字数不足，不输出判定"}
    else:
        risk_map = {"high": "🔴 High Risk", "medium": "🟡 Medium Risk", "low": "🟢 Low Risk",
                    "unknown": "⚪ Insufficient text — no verdict"}

    total_patterns = sum(len(r.matched_patterns) for r in results)
    hot_paras = [r for r in results if r.ai_score >= 50]
    
    if lang == "zh":
        lines = [
            f"AI痕迹评分: {score:.1f}/100  {risk_map[risk]}",
            f"共 {len(results)} 段，命中 {total_patterns} 条AI模式",
        ]
        if hot_paras:
            lines.append(f"⚠️ 高风险段落: 第 {', '.join(str(r.index+1) for r in hot_paras)} 段")
        lines.append("\n段落明细:")
        for r in results:
            bar = "█" * int(r.ai_score / 5) + "░" * (20 - int(r.ai_score / 5))
            md_tag = f" [内容分={r.content_only_score:.0f}]" if r.content_only_score < r.ai_score - 10 else ""
            lines.append(f"  P{r.index+1:02d} [{bar}] {r.ai_score:5.1f}  (TTR={r.ttr:.2f} 句长方差={r.sentence_len_variance:.1f}){md_tag}")
    else:
        lines = [
            f"AI Trace Score: {score:.1f}/100  {risk_map[risk]}",
            f"Total {len(results)} paragraphs, {total_patterns} AI patterns matched",
        ]
        if hot_paras:
            lines.append(f"⚠️ High-risk paragraphs: {', '.join(str(r.index+1) for r in hot_paras)}")
        lines.append("\nParagraph breakdown:")
        for r in results:
            bar = "█" * int(r.ai_score / 5) + "░" * (20 - int(r.ai_score / 5))
            lines.append(f"  P{r.index+1:02d} [{bar}] {r.ai_score:5.1f}  (TTR={r.ttr:.2f} sent-var={r.sentence_len_variance:.1f})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def blended_paragraph_scores(text: str, report=None) -> list:
    """v3 段落归因专用：模式分 × 词频谱分 50/50 融合。

    实测教训：纯模式段落分对新一代模型段落偏低（GLM-5.3自采样段落全被
    判"倾向人类"而文档级谱层能识别），段落级必须叠加谱信号。
    近似口径：阈值沿用 fusion_config（文档级校准），报告中如实标注。
    """
    if report is None:
        report = detect(text)
    try:
        import layers_surface as _LS
        paras = split_paragraphs(text)
        out = []
        for p in report.paragraph_scores:
            idx = min(p.get("index", 0) if isinstance(p, dict) else p.index, len(paras) - 1)
            raw = paras[idx] if idx >= 0 else ""
            spec = _LS.spectrum_layer(raw)["score"] * 10.0
            base = p.get("ai_score", 0) if isinstance(p, dict) else p.ai_score
            out.append(round(0.5 * base + 0.5 * spec, 1))
        return out
    except Exception:
        return [p.get("ai_score", 0) if isinstance(p, dict) else p.ai_score
                for p in report.paragraph_scores]


def journal_profile(report, text=None) -> str:
    """v3 期刊口径预检：疑似AIGC段落比例（对标期刊 AIGC 检测的"疑似率"口径）。

    ⚠️ 诚实声明：本比例基于本 skill 评测语料校准的阈值（fusion_config p95/p99），
    与知网/万方官方检测器不可互换，仅作投稿前自查参考。期刊通行阈值约 20-25%。
    """
    fc = _load_fusion_config() or {}
    thr = fc.get("thresholds", {}).get("medium", 0.4914)
    tm = float(thr) * 100 if float(thr) <= 1.0 else float(thr)
    paras = report.paragraph_scores
    if not paras:
        return "无段落可评"
    texts = split_paragraphs(text) if text else [str(p.get("text", "")) for p in paras]
    scores = blended_paragraph_scores(text, report) if text else [p.get("ai_score", 0) for p in paras]
    flagged = sum(1 for s in scores if s >= tm)
    # 按长度加权（短段落权重低，避免列表项虚增）
    w_flagged = sum(len(texts[min(i, len(texts) - 1)]) for i, s in enumerate(scores) if s >= tm)
    w_total = sum(len(t) for t in texts) or 1
    pct, wpct = 100 * flagged / len(paras), 100 * w_flagged / w_total
    lines = [
        "── 期刊口径预检 ─────────────────",
        "疑似AIGC段落比例: %.0f%%  (按段落计, %d/%d)" % (pct, flagged, len(paras)),
        "疑似内容占比    : %.0f%%  (按字数加权)" % wpct,
        "参考线: 期刊通行阈值约 20-25%% → %s" % (
            "高于参考线，投稿前建议逐段处理" if wpct > 25 else
            ("处于参考线附近，建议人工复核存疑段落" if wpct > 15 else "低于参考线")),
        "⚠️ 本结果基于 paper-polisher 校准阈值, 与知网/万方官方检测不可互换, 仅供自查。",
        "────────────────────────────────",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AI Writing Detector")
    parser.add_argument("input", help="Input text file")
    parser.add_argument("--lang", choices=["zh", "en", "auto"], default="auto", help="Language")
    parser.add_argument("--format", choices=["json", "text", "summary"], default="summary", help="Output format")
    parser.add_argument("--profile", choices=["default", "journal"], default="default",
                        help="journal=期刊口径预检(疑似AIGC比例, 对标20-25%%参考线)")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    with open(args.input, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    report = detect(text, args.lang)
    if args.profile == "journal":
        print(journal_profile(report, text))

    # When writing to file, default to JSON unless format explicitly set
    use_json = args.format == "json" or (args.output and args.format == "summary")

    if use_json:
        output = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    else:
        output = report.details

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    import sys as _sys
    try:  # v3.5: 中文 Windows 默认 GBK 控制台会因 emoji/警示符崩溃 stdout——统一 UTF-8
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
