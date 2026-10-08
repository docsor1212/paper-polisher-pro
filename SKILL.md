---
name: paper-polisher
version: 5.0.0
author: DoctorQ Lab
description: >-
  AI-rate self-check for academic writing, polish guidance (style, terminology, translation-smell),
  metaphor audit, quality report, AIGC compliance label check (China 2025-09
  labeling rules), paragraph-level attribution, journal precheck, sentence-level
  rewrite suggestions (locates and advises, never auto-rewrites), plus `--batch DIR`
  for thesis-scale batch rewriting (per-file AI-rate scores directory-wide).
  Bilingual CN/EN, 100% local, zero upload, zero credentials; bundled unit-test suite
  + AST-based zero-network self-verification.
  v3 delivers a recalibrated multi-layer
  rule engine (11 core layers + discourse/smoothness heuristics) + token-spectrum layer + length-routed fusion + optional
  supervised Qwen3-0.6B ONNX layer (AUROC 1.0 on held-out test) + LLM
  fingerprint attribution (GLM/DeepSeek/Qwen/Kimi/MiniMax/GPT/Claude/Gemini) +
  freshness pipeline. Base-engine numbers reproduce from the bundled held-out
  evaluation; supervised columns are author-side measurements (model not bundled).
tags: [ai-detection, deai, academic-writing, paraphrase, paper-polish]
---

# Paper Polisher Pro v3

AI writing detection (AI-rate self-check for authors) · academic polishing guidance · terminology standardization · translation-smell check · quality report · AIGC compliance label check · paragraph-level attribution · journal precheck.
100% local, zero upload, zero credentials, pure standard library (optional onnxruntime enhancement layer).

> ## ⛔ Iron laws
> 1. **Only reproducible numbers.** Every metric comes from the held-out (test split) evaluation in `eval/run_eval.py`; unsupported claims like "100% detection rate / F1 98.3%" from older docs have been removed.
> 2. **No verdict on short text.** Texts under 100 characters get `risk=unknown` (community lesson: short-text false positives are uncontrollable).
> 3. **Fingerprints attribute, never score.** (Measured 2026-08-15: injecting fingerprints into the detector doubled human false positives.)
> 4. **Calibration/evaluation separation.** Spectrum, weights and thresholds are built on the calib half only; the test half is reserved for final evaluation (an in-sample AUROC of 0.9972 collapsed to a real 0.9187 once split).

## TL;DR

- **What**: 100% local AI-rate self-check + academic polishing toolkit for Chinese academic text (optional supervised model for best accuracy; English gets advisory rules-only scores).
- **30-second start**: `python3 scripts/pp.py quickstart` (zero-model, zero-file demo) · `python3 scripts/pp.py detect draft.txt --format json` · sentence-level rewrite suggestions: `python3 scripts/pp.py fix draft.txt` · full self-check report: `python3 scripts/pp.py workflow draft.txt` · environment: `python3 scripts/pp.py doctor` (one entry routes all subcommands)
- **Measured** (held-out, fingerprint-bound md5 2631df3d388b): AUROC 0.9998 pre-2026 / 0.9400 current-generation; human FPR@medium 2.3%.
- **Know the limits**: texts <100 chars get `risk=unknown` by design · medical text in degraded mode is over-scored · authors' self-check only — never for evading institutional AI detection.
- **Where to look next**: capability boundary matrix below · end-to-end example in § Quick start · FAQ near the end · full history in `CHANGELOG.md`.

## Academic integrity

This tool is for **authors self-reviewing and improving their own writing quality** — clearer sentences, consistent terminology, natural style. It is not designed to evade institutional AI-detection systems, and it must not be used to misrepresent AI-generated work as human-written. Follow your institution's AI-use and disclosure policies; the bundled `aigc_label_check.py` exists to help you **comply** with disclosure and labeling rules (e.g., China's 2025-09 labeling measures) — to declare AI assistance properly, not to hide it. Every AI-risk report (`ai_detector.py` / `deai_gate.py`) carries an explicit `integrity_notice` to this effect.

## Measured performance (C-ReD + DetectRL-ZH, held-out test half, n=5,251)

> Corpus scope note (v4.8.0): the v3.0-era table below was measured on the **full** held-out test half (n=5,251). The **bundled** sample corpus is a subset — its test half is n=1,304; reproducible per-corpus numbers: rules-only (PP_NO_SUP) 0.8985 old-gen / 0.7149 current-gen, fused 0.9998 / 0.9400 (`eval/results/v480_rules_*.json`, `v35ctl_*.json`; cache keys bind model fingerprint AND engine mode).

| Metric | v2.0 baseline | v3.0 rules+spectrum | v3.1 +supervised | **v3.4 supervised + edit-regression v2** |
|---|---|---|---|---|
| AUROC (test half) | 0.7046 | 0.9187 | 0.9997 | **1.0** |
| TPR@FPR5% | 30.4% | 49.0% | 99.95% | **100%** |
| TPR@FPR1% | 16.7% | 24.9% | 99.88% | **100%** |
| Human FPR @calibrated p99 | not measured | not measured | 3.56% (30/844) | **0.71% (6/844)** |
| Paraphrase/mixed-attack AUROC | 0.64 | 0.89 | 1.0 (in-corpus) | **1.0** |
| Attack "AI-assisted" recall | — | — | 71.1% | **86.6%** |
| OOD plain-narrative/film recall | — | — | 1/6 | **5/6 supervised-only · 6/6 local fusion** |

> **v4.4.0 fingerprint-bound re-measurement** of the shipping supervised model (md5 `2631df3d388b`): AUROC **0.9998** (test half, n_base=927), TPR@FPR1% 99.4%, human FPR@medium 2.3% — `eval/results/v35ctl_oldgen.json`. Columns above are preserved as version-era records (earlier model lineage; binaries were not fingerprinted before v4.4.0).

**Which column applies to you?** The base package runs the **v3.0 rules+spectrum engine** (0.9187 AUROC column, measured on the full held-out corpus; pre-4.4.0 archived baselines predate fingerprint binding — every eval result since v4.4.0 carries the deployed model's md5 as `model_fp`, current bound numbers in `eval/results/v35ctl_*.json`). The two right-hand columns require the optional local supervised model (see below). The engine tells you honestly which mode you are in: every report carries `degraded_mode` / `degraded_notice` when the supervised layer is absent or skipped.

### Capability boundary matrix (read before trusting any detector)

| Scenario | Behavior |
|---|---|
| Chinese academic prose, full stack | Best case (AUROC 0.9998 held-out, human FPR@medium 2.3% — v4.4.0 fingerprint-bound) |
| Base package without model | Rules+spectrum (0.9187); **medical register over-scored** (rules-only human FPR @medium: ~59% medical vs ~2% general) → trust only @high verdicts on medical text |
| English text | Language gating skips the Chinese-trained supervised layer by design; rules-only English skeleton, advisory only |
| Mixed human+AI documents | Document-level AUROC 0.52-0.54 (inherent averaging limitation); paragraph-level AUROC 0.69 with **calibrated best operating point P=0.60 at 63% coverage** (`references/para_thresholds.json`) — below the automatic-verdict bar; use `pp_workflow.py`/`paragraph_report.py` rankings for human review only |
| Edit-extent regression head | ρ=0.540 — reported as metadata, never used in verdicts |
| **Current-generation models (2026-09 sampling)** | **AUROC 0.9400** (v4.4.0 fingerprint-bound re-measurement, 443-doc current-gen eval set: 9 families incl. K3/K2.7/Qwen3.7-3.8/DS-V4/V4.1/GLM-5.3/M3) vs 0.9998 pre-2026 held-out — a modest verified gap. The earlier 0.6542-vs-0.9022 figure was a measurement artifact (stale score-cache replay + unverified model lineage); both classes are structurally prevented since v4.4.0 (`model_fp` in every result JSON)
| Colloquial / oral-register text | The style layer is calibrated on academic prose; treat style scores as advisory outside that register |

## Safety and behavior statement

- **100% local**: every feature runs on-device. The codebase makes zero network calls — no network client libraries, no network utilities. Verify structurally: `python3 scripts/pp_verify.py` (AST-level scan; exit 0 = zero network calls, all scripts compile). Legacy text grep `grep -rEin "urllib|requests|socket|import http" scripts/` may show a few URL *strings* in report footers — those are data in string constants, not network code; the AST verifier distinguishes the two.
- **No upload, no credentials**: reads and transmits no credentials, keys, or personal data; the only environment variable, `PP_NO_SUP`, is a local behavior toggle.
- **No persistence**: creates no scheduled tasks, autostart entries, or system config changes; temp files (inter-layer JSON, probe text) are deleted after use.
- **No remote code**: loads no remote models or scripts; the optional supervised model is placed by the user at a local path.
- **Data boundary**: reads/writes only user-specified files, the system temp dir, and its own package data directories (calibration/freshness artifacts); reports go only where the user points them.
- **Academic integrity**: see the section above — for author self-review and quality improvement with policy-compliant disclosure; not for evading detection.

## What's new in v5.0.0

- **Sentence-level rewrite suggestions (`scripts/pp_fix_suggest.py`, also `pp.py fix`)**: the natural next question after a score — *which sentences, why, and how to improve them*. Each flagged sentence lists its concrete features (AI clichés, filler phrases, template patterns, vague qualifiers, connective openers, dash/colon habits, uniform rhythm) with a per-type rewrite strategy. Guidance only: it locates and suggests, never auto-rewrites — the editing decision stays with the author. Ships with `--json` for programmatic use and a built-in two-sample demo (`--demo`).
- **Bundled unit-test suite (`tests/`, `pp.py test`)**: 44 stdlib-unittest cases covering the iron laws (short text/empty/GBK), report field contracts, JSON purity, the gate, the workflow Markdown layout, data files, and the new tools — runnable in seconds without the model, so anyone can verify behavior on their own machine.
- **Structured zero-network self-verification (`scripts/pp_verify.py`, also `pp.py verify`)**: replaces the old grep advice with an AST-level scan of every script — catches network imports/calls and curl/wget-style subprocess commands, while URL *strings* in report footers are correctly treated as data. Exit 0 = clean; `--json` for pipelines.
- **Register awareness 2.0**: literary-narrative texts (dialogue quotes + time progression + inner monologue cues) now get a dedicated register notice explaining that this register sits outside the academic calibration domain — measured literary classics can reach high band in this engine — so the result is not mistaken for AI evidence. Disclosure only; no scoring change.
- **`requirements.txt`** ships with the package: core = zero third-party dependencies; the two optional supervised-layer deps (onnxruntime/numpy) are declared and commented.
- **`pp.py quickstart`**: zero-model, zero-file one-command demo (detect → fix → doctor) on a built-in sample.
- **Freshness visible in `pp_doctor`**: the doctor now reports the latest held-out evaluation record alongside the fingerprint-registry coverage row.

## What's new in v4.9.0

- **Mixed-document calibration (closing the v4.7.0 backlog)**: paragraph-level hi/med/lo thresholds are now calibrated on the controlled mixed benchmark (333 paragraphs with ground truth; `eval/calibrate_mixed_para.py` → `references/para_thresholds.json`). Honest result: the best operating point (≥50) reaches precision 0.60 at 63% AI-paragraph coverage — below the automatic-verdict bar, so paragraph attribution remains a ranking aid for human review; the calibrated numbers and their scope ship in `references/para_thresholds.json` and surface in every `mixed_document` assessment.
- **Unified entry (`scripts/pp.py`)**: one command routes all eleven subcommands (detect/gate/workflow/term/smell/style/quality/aigc/paragraph/setup/doctor) — no more script-navigation cost.
- **Reliability**: batch CSV writes are now atomic (temp+rename — concurrent batch runs no longer clobber the same CSV); gate layers retry once on crash/timeout before falling back.

## Anti-patterns (avoid these)

- **Don't feed <100 chars** and expect a verdict — `risk=unknown` is by design (short-text false positives are uncontrollable); 300+ chars recommended.
- **Don't trust degraded-mode scores on medical text** — rules-only over-scores medical register (~59% human FPR @medium); install the supervised model or trust only `@high`.
- **Don't treat scores as CNKI/Wanfang equivalents** — thresholds are calibrated on our own held-out corpus; self-check only.
- **Don't substitute or re-quantize the model file** — measured probability drift; only author-signed fingerprints pass `pp_setup.py`.
- **Don't use it to evade institutional AI detection** — the integrity notice ships on every report; disclose per your institution's policy.
- **Don't run batch on >5 MB files** — skipped by design; split first.

## Architecture (v3)

```
ai_detector.py            Main engine: 8 rule layers (125 recalibrated patterns, markdown caps,
                          EN openers, paragraph-level language) + length-routed fusion
 + layers_surface.py      L9 surface stats L10 token-spectrum (9,955-token delta spectrum)
                          L11 chain-of-thought features
 + ai_detector L12        discourse-structure heuristics (v3.7.0: hook/reversal/slogan/engagement)
 + fusion_config.json     Weights & thresholds (calib-half grid search + human p95/p99)
 + model_fingerprints.json v4 fingerprint registry (13 families incl. GLM-5.3 & Kimi K-series self-sampled; attribution only)
 + layers_lm.py           Optional supervised layer (local ONNX + pure-Python Qwen tokenizer;
                          PP_NO_SUP=1 falls back to rules)
paragraph_report.py       Paragraph-level attribution HTML (pattern×spectrum 50/50 fusion)
aigc_label_check.py       AIGC compliance labels (China labeling rules 2025-09: metadata/C2PA/explicit)
fingerprint_miner.py      Fingerprint mining (new model drop → sample → mine → register)
pattern_recalibrator.py   Data-driven pattern recalibration (human-hit filtering)
build_spectrum.py / calibrate_v3.py   Spectrum build / weight calibration
freshness_refresh.py         Monthly freshness pipeline (sample → rebuild → calibrate → regression)
pp_doctor.py              Environment self-check (v3.5; v5.0.0 adds latest-eval-record row)
pp_verify.py              AST-level structured zero-network self-verification (v5.0.0)
pp_fix_suggest.py         Sentence-level rewrite suggestions (v5.0.0: locate + strategy, no auto-rewrite)
tests/                    Bundled unit-test suite, `python3 -m unittest discover -s tests -t .` (v5.0.0)
requirements.txt          Dependency declaration: core zero-dep; optional supervised-layer extras (v5.0.0)
eval/                     corpus_builder / attack_gen / run_eval (AUROC, TPR@FPR, per-model, attack decay)
```

## Quick start

```bash
# Zero-model, zero-file one-command demo (v5.0.0)
python scripts/pp.py quickstart
# AI writing detection (probability + layered evidence + fingerprint attribution)
python scripts/ai_detector.py draft.txt --format json
# Sentence-level rewrite suggestions (v5.0.0: which sentences, why, how to improve)
python scripts/pp_fix_suggest.py draft.txt --top 10
# Journal precheck (suspected-AIGC ratio vs the 20-25% reference line, non-interchangeable disclaimer)
python scripts/ai_detector.py draft.txt --profile journal
# Paragraph-level attribution (locate human/AI collaboration)
python scripts/paragraph_report.py draft.txt --output report.html
# AIGC compliance label check (docx/pdf/png/txt)
python scripts/aigc_label_check.py manuscript.docx figures/*.png
# Terminology / translation smell / 4-layer gate (same as v2)
python scripts/term_check.py draft.txt --auto-fix
python scripts/translation_smell_check.py draft.txt
python scripts/deai_gate.py draft.txt
# Environment self-check
python scripts/pp_doctor.py
# Structured zero-network self-verification + bundled unit tests (v5.0.0)
python scripts/pp_verify.py
python -m unittest discover -s tests -t .          # or: python scripts/pp.py test
# Held-out regression (mandatory after any engine change)
python eval/run_eval.py --split test --tag mytag
```

### Optional supervised layer (recommended, v3.2+)

```bash
pip install onnxruntime regex          # the two optional dependencies
# Place the two model files exactly as shipped by the authors:
#   ~/.cache/paper-polisher/qwen3-detector/model.int8.onnx
#   ~/.cache/paper-polisher/qwen3-detector/tokenizer.json
python scripts/layers_lm.py            # self-test: supervised_available: true
# ai_detector.py fuses automatically afterwards (0.9*supervised + 0.1*rules);
# PP_NO_SUP=1 temporarily falls back to rules-only.
# ⚠️ Do not substitute other exports or quantizations — measured probability drift; use exactly these files.
```

### Python API (programmatic use)

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from pp_api import detect_text, gate_text, doctor_summary
r = detect_text("中文学术文本，建议 300 字以上。" * 10, lang="zh")
print(r["overall_ai_score"], r["overall_risk"], r["degraded_mode"])
```

`detect_text` runs in-process (no subprocess) and returns the same JSON structure as the CLI. Every function returns JSON-able dicts and raises on bad input — no silent failures. Zero network, stdlib-only.

### One-command supervised setup

```bash
python3 scripts/pp_setup.py --model <author-signed model.onnx>   # verify md5 -> install -> inference canary
python3 scripts/pp_setup.py --check                              # current installation status
```

Only author-signed fingerprints (`references/supervised_models.json`) are accepted; unknown weights are rejected before anything is touched. Nothing is downloaded — the model always comes from the authors' channel as a local file.

### End-to-end workflow (one command)

```bash
python3 scripts/pp_workflow.py draft.txt      # writes draft.workflow.md + draft.workflow.json
```

Runs the full self-check in one pass — AI-rate detection (fused engine), paragraph-level
attribution with hi/med/lo classification, the 4-layer gate, terminology, translation-smell,
style, quality report and AIGC label self-check — and produces a single readable Markdown
report plus machine-readable JSON. Programmatic: `from pp_api import workflow`.

## FAQ

**Q: Why no risk verdict for texts under 100 characters?**
Short-text false positives are uncontrollable (a few sentences carry no style distribution). The tool returns `risk=unknown` by design; submit 100+ chars (300+ recommended).

**Q: Why is my medical text scored high?**
You are most likely in degraded mode (optional supervised model not installed). Rules-only scoring systematically over-scores medical register (held-out human FPR at @medium: ~59% medical vs ~2% general). For medical text trust only @high verdicts, or install the supervised layer (next question).

**Q: How do I install the supervised model and confirm it works?**
one command: `python3 scripts/pp_setup.py --model <author-signed model.onnx>` — it verifies the md5 against the signed registry, installs, and runs an inference canary (GREEN = active; `degraded_mode=false` in reports confirms it). Manual placement of the two files at `~/.cache/paper-polisher/qwen3-detector/` still works and `python scripts/pp_doctor.py` remains the full check.

**Q: What do degraded_mode / degraded_notice mean?**
Engine-mode disclosure: true = rules+spectrum fallback, reason in the notice (model missing / PP_NO_SUP=1 / English language gating). See the capability boundary matrix.

**Q: Is this score interchangeable with CNKI/Wanfang official checks?**
No. Thresholds are calibrated on our own held-out corpus and are not interchangeable with any institutional detector; self-check only (stated in journal-profile output too).

**Q: A deai_gate layer shows "解析失败" (parse failure) — what now?**
That layer falls back to a neutral 50; other layers and the verdict are unaffected. Usually a subprocess timeout or odd input encoding; retry once, then run `pp_doctor.py`.

**Q: What is the edit-extent estimate?**
A supervised-layer regression head estimating how much the text was AI-edited (0-1). Limited discriminative power (ρ=0.54) — report metadata only, never used in verdicts.

**Q: Is English supported?**
Partially: the supervised layer is Chinese-trained, so English skips fusion by design and gets rules-only skeleton scoring, advisory only (stated in the report).

**Q: What about documents that mix human and AI writing?**
Watch the mixed-register signal (`mixed_signal=true`): document-level scores are diluted by human paragraphs or pushed up by AI ones — unreliable either way. Run `paragraph_report.py` for per-paragraph attribution and work paragraph by paragraph.

**Q: Why does a real, human-written journal paper still score medium/high?**
Two measured reasons: distribution shift (our held-out corpus differs from real journal PDF→text, which carries layout noise) and register calibration. Paragraph attribution is the actionable signal — use it to locate suspect passages for human review; the document-level score is a triage hint, not a verdict. The journal precheck (distribution口径) offers a second view and may disagree with the main score by design.

**Q: The fingerprint attribution says GPT-4o but my text is from another model?**
Attribution is heuristic (top-n candidates, never scored) and may misattribute — known case: GLM-generated text has been attributed elsewhere. Treat family hints as weak evidence; the detection score and paragraph attribution are the substantive outputs.

**Q: How do I use the AIGC label check?**
`python scripts/aigc_label_check.py manuscript.docx figures/*.png` — checks metadata / C2PA watermark / explicit declaration (China 2025-09 labeling rules). Exit 0 = labeled, 1 = unlabeled; both are normal runs.

**Q: How can I verify the "100% local / zero upload" claim myself?**
Run `python3 scripts/pp_verify.py` — an AST-level structural scan of every script. It flags network imports/calls and curl/wget-style subprocess commands, while URL strings in report footers are correctly treated as data (the old grep advice could not tell the two apart). Exit 0 = zero network calls. For behavior-level checks, the bundled test suite (`python -m unittest discover -s tests -t .`) exercises the iron laws and report contracts on your own machine.

**Q: What do the rewrite suggestions do — do they change my text?**
No. `pp_fix_suggest.py` (`pp.py fix`) only locates sentences carrying improvable features and explains the improvement strategy per feature type (e.g., replace an AI cliché with a concrete claim, split a template sentence). It never edits your file; the editing decision and execution stay with the author. `--demo` shows a built-in two-sample walkthrough.

### Script cheat sheet

| Script | Purpose | Key flags | Output |
|---|---|---|---|
| ai_detector.py | Main AI-writing detector | `--lang auto\|zh\|en` `--format json\|text\|summary` `--profile journal` `--batch DIR` | Score + paragraph detail + fingerprints (JSON incl. degraded_mode/integrity_notice) |
| pp_fix_suggest.py | Sentence-level rewrite suggestions (v5.0.0) | `--top N` `--json` `--demo` | Per-sentence features + rewrite strategies (locates and suggests, never auto-rewrites) |
| pp_doctor.py | Environment self-check | `--json` | Data/deps/model probes; exit 0 = green |
| pp_verify.py | Structured zero-network self-verification (v5.0.0) | `--json` | AST-level scan verdict; exit 0 = zero network calls |
| quality_report.py | Overall quality report | `--json` | Readability/quality dimensions for the manuscript |
| deai_gate.py | 4-layer fused gate | `--json` | composite score + verdict band (<35 pass / 35-55 review / ≥55 suspect) |
| paragraph_report.py | Paragraph attribution | `--output report.html` | HTML report |
| term_check.py | Terminology (2,308 terms) | `--auto-fix` `--output` | Standardization rate + fixed file |
| translation_smell_check.py | Translation-smell scan | `--json` | Hits + blind-spot terms |
| style_distance.py | Stylometry (human-likeness) | `--json` | style_score + verdict (advisory outside academic register) |
| aigc_label_check.py | AIGC compliance labels | files: docx/pdf/png/txt | Per-file label verdict |

## Trigger words (Chinese)

`润色论文`查AI率` `论文AI率` `AIGC检测` `AIGC率` `GPT检测` `查AI写作` `论文润色` `改写论文` `AI论文检测` `学术写作助手` `AI写作检测` `毕业论文润色` `学位论文降重` `SCI论文编辑` `手稿润色` `AI写作评分` `AI改写检测` `文风对标顶刊` `这篇文章像不像AI`

## Related tools

- **cn-med-oa** — free Chinese medical literature (OA) download & citation metadata
- **pubmed-verifier** — verify PMID/DOI references before submission
- **cite-holmes** — deep research with machine-verified citations
- **academic-figures** — publication-ready scientific figures in one command
- **doc-holmes** — layout-preserving PDF translation
- **paper-rewriter** — same-source de-AI rewriting companion (full rewrite pipeline)

Docs & site: **docsor.cn**

## Fingerprint freshness (against "detectors lag one generation")

Coverage as of 2026-09-26: kimi-k3 & kimi-k2.7 registered (OpenCode Go fresh sampling, attribution-verified); qwen3.8 / deepseek-v4 / deepseek-v4.1 / minimax-m3 sampled — mining produced no family-distinctive low-FP patterns, honestly unregistered; glm-5.3 refreshed (no new patterns). Next: deepseek-v4.1 & minimax-m3 with larger corpora.

On a new-model release day: `python scripts/fingerprint_miner.py --corpus <new_samples.jsonl> --model <family> --apply`
Monthly full pass: `python scripts/freshness_refresh.py` (schedule it with your own system timer, e.g. monthly; the script never creates or modifies system schedules). Compare adjacent `eval/results/freshness_*.json`; investigate if AUROC drops by more than 3 percentage points.

## Version history (condensed)

- **v5.0.0 (2026-10-09)** — verification & rewrite-suggestions release: bundled unit-test suite (44 stdlib cases, `pp.py test`); AST-level zero-network self-verification (`pp_verify.py`); sentence-level rewrite suggestion engine (`pp_fix_suggest.py` — locate + strategy, never auto-rewrite, also wired into `pp_workflow` and `pp.py fix`); literary-narrative register notice (disclosure only, no scoring change); `requirements.txt`; `pp.py quickstart`; doctor freshness row.
- **v4.9.0 (2026-10-08)** — mixed-document calibration release: paragraph thresholds calibrated on the 333-paragraph benchmark (best operating point P=0.60/coverage 63% — honestly below auto-verdict bar; ranking aid only); unified `pp.py` entry; atomic batch CSV; gate layer retry.
- **v4.8.0 (2026-10-07)** — measurement & output-contract integrity (independent test round, 13 findings addressed): eval cache keys bind engine mode (rules-only reproducible: 0.8985/0.7149 bundled); journal+json purity; risk_bands surfaced; mixed_signal denoised; 5MB/batch CLI guards; real-world FPR & attribution limits disclosed in FAQ; corpus/terminology counting precision.
- **v4.7.0 (2026-10-06)** — mixed-document special: controlled per-paragraph benchmark quantifies paragraph-level AUROC 0.69 (document-level 0.52-0.54); pp_workflow gains mixed_document assessment + prominent mixed flagging; description Trigger-on routing words; README China mirror link.
- **v4.6.0 (2026-10-05)** — onboarding release: end-to-end workflow command (pp_workflow.py / pp_api.workflow); TL;DR layer; historical notes moved to CHANGELOG.md; consolidated anti-patterns section; eval archive cleanup; recovery hints in SDK errors.
- **v4.5.0 (2026-10-04)** — programmable-interface release: pp_api.py SDK (in-process detect + 8 helpers, zero network, JSON dicts) and pp_setup.py one-command model installation with the author-signed fingerprint registry; closing the two biggest usability friction points reported with the 4.4.x interface (programmatic integration and model setup).
- **v4.4.0 (2026-10-03)** — measurement-integrity release: verified re-baseline (held-out 0.9998 / current-gen 0.9400 / human FPR@med 2.3%, superseding 0.9022/0.6542 artifacts); eval cache keys bind model md5; contamination audit (eval/check_leak.py) halts the v36 retrain (285 eval-set samples had leaked into training); ONNX export self-test; PP_ORT_THREADS; pp_doctor fingerprint; smoke degradation checks made mode-aware.
- **v4.3.0 (2026-10-01)** — generation-split eval infrastructure; first quantified generation-gap numbers (0.9022 vs 0.6542); spectrum/L13 current-gen negative results recorded.
- **v4.2.0 (2026-09-30)** — batch recursion; GitHub README landing page; gate layer-3 distribution verification.
- **v4.1.0 (2026-09-29)** — smoothness layer fused into the score (A/B-verified zero regression); batch CSV; paragraph report disclosures.
- **v4.0.0 (2026-09-28)** — family referral loop; task-word-root coverage; family-section cleanup.
- **v3.12.0 (2026-09-28)** — translation-smell layer revived (schema fix); integrity notice on every report; paragraph-count consistency; spectrum-v2 & L13-mid negative results recorded.
- v3.11.0 (2026-09-27) — batch detection (`--batch DIR`); paragraph report integrity notice; tier-2 n-gram negative result recorded.
- v3.10.0 (2026-09-26) — fingerprint freshness phase 3: kimi-k2.7 registered (attribution-verified); contaminated candidates rolled back per quality gate.
- **v3.9.0 (2026-09-25)** — discourse smoothness disclosure (L13 surprisal-variation, standalone AUROC 0.8256 held-out; NOT fused per iron law); layer-evaluation mode in run_eval (`--layer`).
- v3.8.0 (2026-09-24) — mixed-register signal, register hint, encoding warning, gate layer-divergence disclosure; safety & behavior statement; qwen3.8/v4 fingerprint mining (honestly unregistered).
- v3.7.0 (2026-09-23) — discourse-structure heuristic layer L12 (8 groups, density-scaled cap 30; LES-20260923-021 blind-spot fix; AUROC 0.9022 unchanged); kimi-k3 fingerprint registered (OpenCode Go sampling); centralized FAQ; script cheat sheet; documentation wording cleanup.
- v3.6.0 (2026-09-21) — academic-integrity guardrails (integrity_notice + section); CH-side wording cleanup.
- **v3.5.0 (2026-09-20)** — degraded-mode disclosure (engine mode + medical-register warning with held-out numbers); iron law #2 enforced (<100 chars → risk=unknown, quality_report shows "cannot judge" instead of misleading green); `pp_doctor.py` self-check; `deai_gate.py` usage guard; honest dual-language docs rebuild.
- v3.4.3 — markdown table-separator rows filtered from paragraph scoring (6/8 flagged rows in real MD manuscripts were false positives).
- v3.4.2 — fixed CJK double-count in language detection (Chinese journal PDFs misrouted to EN rules); degenerate PDF hard-line-break paragraph rebuilding (747→19 segments); paragraph-level language routing dead code fixed.
- v3.4.1 — language gating: English text skips the Chinese-trained supervised layer (measured EN OOD p_ai=0.9996 → EN false positives 91.7→17.2). Rule-editor experiment: negative result, honestly abandoned.
- v3.4.0 — edit-extent regression v2 (1,620 pairs, token-level distance, two-stage training): human FPR@p99 1.66%→0.71%; attack "AI-assisted" recall 86.6%.
- v3.2/v3.3 — supervised layer v3.2 (4-dim head, local ONNX fp16, pure-Python Qwen tokenizer); OOD blind spots honestly recorded then closed (film-register recall 1/6→5/6, GLM-5.3 probe 9/9).
- v3.1 — Qwen3-0.6B LoRA supervised layer (AUROC 0.9997 held-out).
- v3.0 — eval-driven rebuild: recalibrated pattern library (693→125 patterns, 568 dead/inverted signals removed), token-spectrum layer, length-routed fusion, calib/test leak-proof split, fingerprint registry v4, paragraph attribution, AIGC label check, journal precheck, freshness pipeline, honest docs. AUROC 0.7046→0.9187.
- v2.0.x — 9-layer rule engine + terminology library (baseline column above; non-reproducible claims removed).
