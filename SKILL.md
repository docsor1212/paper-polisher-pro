---
name: paper-polisher
version: 5.8.0
author: DoctorQ Lab
description: >-
  AI-rate self-check and polish guidance for academic writing: sentence-level rewrite
  suggestions (locates and advises, never auto-rewrites), terminology and consistency
  checks, translation-smell, paragraph attribution, journal precheck with discipline
  context, style-norm conventions check, quality report, AIGC label check, plus
  `--batch DIR` with HTML summary. Reads .docx directly.
  Not for: document/PDF translation (doc-holmes), plagiarism checking (institutional
  systems), ghost-writing or executing rewrites (paper-rewriter); texts under 100
  chars get no verdict by design.
  100% local, zero upload; bundled tests + AST zero-network self-verification.
  Multi-layer rule engine + token spectrum + optional supervised Qwen3-0.6B ONNX
  layer + LLM fingerprint attribution + freshness pipeline. Base-engine numbers
  reproduce from bundled held-out evals; supervised columns are author-side
  (model not bundled).
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
- **Know the limits**: texts <100 chars get `risk=unknown` by design · medical text in degraded mode is over-scored · mixed human+AI docs: the document-level score is unreliable (paragraph attribution is the actionable signal) · authors' self-check only — never for evading institutional AI detection.
- **Where to look next**: capability boundary matrix below · end-to-end example in § Quick start · FAQ near the end · full history in `CHANGELOG.md`.

### 30-second task routing

| You want to… | Run | Deep doc |
|---|---|---|
| Check AI-rate of a draft | `pp.py detect draft.txt --format json` | § Measured performance + boundary matrix below |
| See which sentences read AI-like | `pp.py fix draft.txt` | `pp_fix_suggest.py --help` |
| Compare before/after your rewrite | `pp.py rewrite-check orig.txt rev.txt` | FAQ: rewrite suggestions |
| Translate a PDF keeping layout | `pp.py bundle` not this — use doc-holmes | Related tools |
| Check writing conventions | `pp.py norm draft.txt` | FAQ: style-norm |
| Batch a whole thesis folder | `ai_detector.py --batch DIR --csv s.csv --report r.html` | FAQ: batch CSV |
| Verify the zero-upload claim | `pp.py verify` + `pp.py test` | Safety statement |
| Journal precheck (discipline context) | `ai_detector.py draft.txt --profile journal` | § journal precheck |
| Environment trouble-shooting | `pp.py doctor` / `pp.py freshness --status` | FAQ: modes |
| One visual dashboard of all results | `pp.py html-report draft.workflow.json -o report.html` | Script cheat sheet: pp_report_html.py |
| Not sure which command fits? | `pp.py recommend "把这段的AI率降一降"` | `pp.py recommend --help` |

### The three limits that matter most (full detail in the matrix below)

1. **Medical register over-scoring in degraded mode** — rules-only human FPR @medium ≈59% medical vs ≈2% general; trust only `@high` verdicts on medical text, or install the supervised model.
2. **Mixed human+AI documents** — document-level AUROC 0.52-0.54 (inherent averaging limitation); use paragraph attribution as a human-review ranking, never as an automatic verdict.
3. **Data-coverage scope** — the term bank is 2,308 medical/academic terms (non-medical texts standardize low by design); style layers calibrate on academic prose (colloquial/narrative input = advisory only). Per-tool scope: sub-tool matrix below.

## Academic integrity

This tool is for **authors self-reviewing and improving their own writing quality** — clearer sentences, consistent terminology, natural style. It is not designed to evade institutional AI-detection systems, and it must not be used to misrepresent AI-generated work as human-written. Follow your institution's AI-use and disclosure policies; the bundled `aigc_label_check.py` exists to help you **comply** with disclosure and labeling rules (e.g., China's 2025-09 labeling measures) — to declare AI assistance properly, not to hide it. Every AI-risk report (`ai_detector.py` / `deai_gate.py`) carries an explicit `integrity_notice` to this effect.

## Measured performance (C-ReD + DetectRL-ZH, held-out test half, n=5,251)

> Corpus scope note (v4.8.0): the v3.0-era table below was measured on the **full** held-out test half (n=5,251). The **bundled** sample corpus is a subset — its test half is n=1,304; reproducible per-corpus numbers: rules-only (PP_NO_SUP) 0.8985 old-gen / 0.7149 current-gen, fused 0.9998 / 0.9400 (`eval/results/v480_rules_*.json`, `v35ctl_*.json`; cache keys bind model fingerprint AND engine mode).

| Metric | v2.0 baseline | v3.0 rules+spectrum | v3.1 +supervised | v3.4 supervised（版本时代记录，现行见下方重测行） |
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

### Sub-tool scope matrix (each sub-tool's calibrated domain)

| Sub-tool | Calibrated domain | Outside-domain behavior |
|---|---|---|
| ai_detector / deai_gate | Chinese academic prose (held-out calibrated) | Medical register over-scored in degraded mode; English advisory rules-only; narrative/colloquial input gets a register notice |
| paragraph_report / pp_rewrite_check | Same engine criteria as above, per paragraph | Same limitations; rewrite_check compares two drafts under identical criteria |
| pp_fix_suggest | Chinese AI-writing pattern library (academic register) | English text gets basic connective/rhythm checks only; findings are style observations, never detections |
| term_check | Chinese medical/academic terminology (2,308-term bank) | Non-medical text: the standardization rate reads low — that is bank scope, not an error; `--auto-fix` respects context |
| translation_smell_check | Chinese academic prose (translationese patterns) | English-style source text: output lists its blind-spot terms instead of pretending coverage |
| style_distance | Academic prose stylometry | Outside the academic register the style score is advisory only (stated in the output) |
| style_norm | Mechanical conventions — register-independent | No score by design; statistical checks (numbers/abbreviations) are weak on short samples and say so |
| aigc_label_check | File metadata / C2PA / explicit label statements | Not a content detector; verifies labeling compliance, not authorship |
| quality_report | Readability/quality dimensions for the manuscript | Not an AI-rate measure; scoring heuristics are generic, not journal-tuned |
| docx_text | .docx text extraction (paragraph-preserving) | Not a PDF converter — PDFs are rejected with conversion advice (zero-dep Chinese PDF extraction cannot be guaranteed) |
| batch mode (--batch) | .txt/.md/.docx <5 MB per file | >5 MB skipped by design; encrypted/image-only docx yield an explicit error, not silent empty output |

## Safety and behavior statement

- **100% local**: every feature runs on-device. The codebase makes zero network calls — no network client libraries, no network utilities. Verify structurally: `python3 scripts/pp_verify.py` (AST-level scan; exit 0 = zero network calls, all scripts compile). Legacy text grep `grep -rEin "urllib|requests|socket|import http" scripts/` may show a few URL *strings* in report footers — those are data in string constants, not network code; the AST verifier distinguishes the two.
- **No upload, no credentials**: reads and transmits no credentials, keys, or personal data; the only environment variable, `PP_NO_SUP`, is a local behavior toggle.
- **No persistence**: creates no scheduled tasks, autostart entries, or system config changes; temp files (inter-layer JSON, probe text) are deleted after use.
- **No remote code**: loads no remote models or scripts; the optional supervised model is placed by the user at a local path.
- **Data boundary**: reads/writes only user-specified files, the system temp dir, and its own package data directories (calibration/freshness artifacts); reports go only where the user points them.
- **Academic integrity**: see the section above — for author self-review and quality improvement with policy-compliant disclosure; not for evading detection.

### Exit-code contract (stable since v5.8.0)

| Exit | Meaning | Typical cases |
|---|---|---|
| 0 | Success | report produced · `verify` zero-network pass · `test` suite green |
| 1 | Ran but did not pass | engine runtime failure (recovery advice in the message) · `test` failures · `verify` drift · `freshness` baseline drift |
| 2 | Usage or input error | unknown subcommand · file missing · text under 100 chars · unparseable input file |
| 3 | Environment not ready | `pp_setup.py` model install/verification failure — run `pp.py doctor` first |

Programmatic mirror: `pp_api` raises `ValueError` for invalid input (↔ exit 2) and `RuntimeError` for runtime failure (↔ exit 1), both carrying recovery advice in the message. These codes are a stability promise — future releases will not repurpose them.

## Anti-patterns (each with the right way)

- **Don't feed <100 chars** and expect a verdict — `risk=unknown` is by design (short-text false positives are uncontrollable). ✅ Instead: submit 300+ chars, or use the style-norm check (`pp.py norm`) which has no verdict and works on short samples.
- **Don't trust degraded-mode scores on medical text** — rules-only over-scores medical register (~59% human FPR @medium). ✅ Instead: install the supervised model, or trust only `@high` verdicts and lean on paragraph attribution.
- **Don't treat scores as CNKI/Wanfang equivalents** — thresholds are calibrated on our own held-out corpus. ✅ Instead: use scores as relative triage and let the journal precheck give the distribution view.
- **Don't substitute or re-quantize the model file** — measured probability drift. ✅ Instead: only author-signed fingerprints pass `pp_setup.py`; if unavailable, stay in documented degraded mode.
- **Don't use it to evade institutional AI detection** — the integrity notice ships on every report. ✅ Instead: use findings to improve the writing itself and disclose per your institution's policy.
- **Don't run batch on >5 MB files** — skipped by design. ✅ Instead: split first, or point the batch at the exported text/docx versions.
- **Don't repeat the same analysis on unchanged input, or re-run a call that was already rejected** — it burns time without new information. ✅ Instead: change one input (text, engine mode, check scope) or resolve the blocker (missing model, encoding) before retrying.

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
pp_report_html.py         Single-document visual dashboard (workflow/detect/fix/norm JSON → one HTML; v5.8.0)
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
# Academic style-norm self-check (v5.2.0: fullwidth/numbers/abbreviations/units)
python scripts/pp_style_norm.py draft.txt
# Word documents: read directly (.docx into any entry point)
python scripts/ai_detector.py thesis.docx --format json
# Submission self-check bundle (v5.3.0: one command -> dated directory with all artifacts)
# Journal precheck with discipline context (v5.4.0; --discipline to override)
python scripts/ai_detector.py draft.txt --profile journal --format json
# Fingerprint freshness status (v5.4.0: baselines drift check + due indicator)
python scripts/pp.py freshness --status
python scripts/pp_report_bundle.py thesis.docx --outdir ~/selfcheck
# Rewrite-effect regression check (v5.1.0: original vs revised, engine-source comparison)
python scripts/pp_rewrite_check.py draft_original.txt draft_revised.txt
# Batch CSV -> self-contained HTML summary (v5.1.0)
python scripts/pp_batch_report.py scores.csv -o report.html
# Single-document visual dashboard: render workflow/detect/fix/norm JSON into one HTML (v5.8.0)
python scripts/pp.py html-report draft.workflow.json -o report.html
# Natural-language command router: describe the task, get the command (v5.8.0)
python scripts/pp.py recommend "把这段的AI率降一降"
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

Only author-signed fingerprints (`references/supervised_models.json`) are accepted; unknown weights are rejected before anything is touched. Nothing is downloaded — the model always comes from the authors' channel as a local file. Model acquisition: the author-signed files are not publicly downloadable — open an issue at the GitHub repo (docsor1212/paper-polisher-pro) to request the current signed build; until then the package runs in documented degraded mode with full functionality minus the accuracy uplift.

### End-to-end workflow (one command)

```bash
python3 scripts/pp_workflow.py draft.txt      # writes draft.workflow.md + draft.workflow.json
```

Runs the full self-check in one pass — AI-rate detection (fused engine), paragraph-level
attribution with hi/med/lo classification, the 4-layer gate, terminology, translation-smell,
style, quality report and AIGC label self-check — and produces a single readable Markdown
report plus machine-readable JSON. Programmatic: `from pp_api import workflow`.

## FAQ (grouped: verdicts → modes → output → safety → tools)

### Verdicts & boundaries

**Q: Why no risk verdict for texts under 100 characters?**
Short-text false positives are uncontrollable (a few sentences carry no style distribution). The tool returns `risk=unknown` by design; submit 100+ chars (300+ recommended).

**Q: Why is my medical text scored high?**
You are most likely in degraded mode (optional supervised model not installed). Rules-only scoring systematically over-scores medical register (held-out human FPR at @medium: ~59% medical vs ~2% general). For medical text trust only @high verdicts, or install the supervised layer (next question).

### Modes & install

**Q: How do I install the supervised model and confirm it works?**
one command: `python3 scripts/pp_setup.py --model <author-signed model.onnx>` — it verifies the md5 against the signed registry, installs, and runs an inference canary (GREEN = active; `degraded_mode=false` in reports confirms it). Manual placement of the two files at `~/.cache/paper-polisher/qwen3-detector/` still works and `python scripts/pp_doctor.py` remains the full check.

**Q: What do degraded_mode / degraded_notice mean?**
Engine-mode disclosure: true = rules+spectrum fallback, reason in the notice (model missing / PP_NO_SUP=1 / English language gating). See the capability boundary matrix.

**Q: Is this score interchangeable with CNKI/Wanfang official checks?**
No. Thresholds are calibrated on our own held-out corpus and are not interchangeable with any institutional detector; self-check only (stated in journal-profile output too).

### Output & interpretation

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

### Safety & verification

**Q: How can I verify the "100% local / zero upload" claim myself?**
Run `python3 scripts/pp_verify.py` — an AST-level structural scan of every script. It flags network imports/calls and curl/wget-style subprocess commands, while URL strings in report footers are correctly treated as data (the old grep advice could not tell the two apart). Exit 0 = zero network calls. For behavior-level checks, the bundled test suite (`python -m unittest discover -s tests -t .`) exercises the iron laws and report contracts on your own machine.

**Q: Does the style-norm check produce a score or a verdict?**
No. `pp_style_norm.py` is a mechanical convention check (full/half-width, number styles, abbreviation definitions, unit formats). It lists findings with concrete advice; nothing is scored and nothing feeds into the AI-rate engine. The short-text iron law does not apply because no verdict is produced — but statistical checks (numbers/abbreviations) are naturally weak on very short samples and the output says so.

**Q: Can several batch runs write to the same CSV safely?**
Yes — since v4.9.0 batch CSV writes are atomic (write to a temp file, then rename into place). Two concurrent batch runs pointing at the same CSV cannot interleave or clobber each other's rows; the file always contains one complete run's output.

**Q: How should I read `degraded_notice`?**
It tells you which full-mode ingredient was skipped and why: supervised model missing, `PP_NO_SUP=1`, or English language gating. Consequences differ — degraded rules-only mode systematically over-scores medical register (see the boundary matrix), while English gating only means the Chinese-trained supervised layer does not apply. The notice names the reason so you can decide whether to install the model, unset the toggle, or treat scores as advisory.

### Tools & workflow

**Q: What do the rewrite suggestions do — do they change my text?**
No. `pp_fix_suggest.py` (`pp.py fix`) only locates sentences carrying improvable features and explains the improvement strategy per feature type (e.g., replace an AI cliché with a concrete claim, split a template sentence). It never edits your file; the editing decision and execution stay with the author. `--demo` shows a built-in two-sample walkthrough.

### Script cheat sheet

| Script | Purpose | Key flags | Output |
|---|---|---|---|
| ai_detector.py | Main AI-writing detector | `--lang auto\|zh\|en` `--format json\|text\|summary` `--profile journal` `--batch DIR` | Score + paragraph detail + fingerprints (JSON incl. degraded_mode/integrity_notice) |
| pp_fix_suggest.py | Sentence-level rewrite suggestions (v5.0.0) | `--top N` `--json` `--demo` | Per-sentence features + rewrite strategies (locates and suggests, never auto-rewrites) |
| pp_doctor.py | Environment self-check | `--json` | Data/deps/model probes; exit 0 = green |
| docx_text.py | .docx → text extraction (v5.3.0) | `file` `--output` | Paragraph-preserving text; zip-bomb guarded |
| freshness_refresh.py | Monthly freshness pipeline / status (v5.4.0) | `--status` `--json` | Last run, latest eval record, baseline drift, due flag |
| pp_report_bundle.py | Submission self-check bundle (v5.3.0) | `file` `--outdir` | Dated directory: workflow + paragraph HTML + suggestions + norm + manifest |
| pp_style_norm.py | Academic style-norm self-check (v5.2.0; +consistency v5.5.0; +llm_jargon v5.6.0) | `--json` `--checks a,b` | Findings with advice (fullwidth/numbers/abbrev/units); no score |
| pp_rewrite_check.py | Rewrite-effect regression check (v5.1.0) | `original revised` `--json` `--demo` | Score/risk-band migration + paragraph deltas + feature-type clears/remaining |
| pp_batch_report.py | Batch CSV → HTML summary (v5.1.0) | `csv_file` `-o out.html` | Totals/mean/band cards + histogram + per-file table |
| pp_report_html.py | Single-document visual dashboard (v5.8.0) | `json...` `-o out.html` `--title` | Self-contained HTML: gauge + histogram + paragraph/finding/ledger tables; zero external resources |
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

- **v5.8.0 (2026-10-16)** — visual dashboard release: `pp_report_html.py` renders workflow/detect/fix/norm JSON into one self-contained HTML (gauge, histogram, paragraph/finding/ledger tables); `pp.py recommend` natural-language command router; exit-code contract documented and locked; top-3 limits surfaced next to the TL;DR; ZH version history slimmed to match EN.
- **v5.7.1 (2026-10-16)** — sample sanitation: an internal LAN link embedded in the bundled sample document text (`examples/outputs/detect_sample.json`) was redacted after the hygiene gate flagged it; no code or engine changes (bit-identical scoring to 5.7.0).
- **v5.7.0 (2026-10-16)** — release-integrity overhaul: version-scoped guards, post-packaging version assertion, sample outputs shipped, sentence-locating in the jargon check; CHANGELOG/SKILL.md dedup.
- **v5.6.0 (2026-10-14)** — llm-jargon release: three-tier AI-flavor self-check with case-library contrasts (cross-line port, credited); engine scoring of the signal tried and honestly reverted (negative result archived with retry conditions).
- Releases **v5.4.1 and earlier**: see `CHANGELOG.md` (single source of history).
