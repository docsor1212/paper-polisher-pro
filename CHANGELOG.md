# Changelog

> Historical release notes (moved out of SKILL.md in v4.6.0 so new users reach the workflow faster). Newest first. Condensed per-version summaries also live in SKILL.md § Version history.

## What's new in v4.5.0

- **Python API (`scripts/pp_api.py`)**: the engine is now importable. `detect_text(text)` runs the full detector in-process (same code path as the CLI — parity-checked) and returns a plain JSON-able dict; helpers cover the rest of the toolkit: `gate_text`, `term_report`, `smell_report`, `style_report`, `quality_report_file`, `attribution`, `model_fingerprint`, `doctor_summary`. Zero network, zero third-party dependencies, exceptions instead of silent failures. Programmatic integration no longer requires wrapping subprocess calls.
- **One-command supervised setup (`scripts/pp_setup.py`)**: `--model <file>` replaces manual multi-step model placement. The file's md5 is checked against the author-signed fingerprint registry (`references/supervised_models.json`) — unknown weights are rejected (exit 2) — then the model is installed, inference-canaried, and confirmed GREEN; `--check` shows current status. The model still never ships inside the package and nothing is ever downloaded (the 100%-local contract is intact).

## What's new in v4.4.0

- **Headline numbers re-measured under verified conditions — they changed**: pre-2026 held-out AUROC **0.9998** (was believed 0.9022) and current-generation AUROC **0.9400** (was believed 0.6542), human FPR@medium **2.3%** (was believed ~20%). The old figures were measurement artifacts: eval score-cache keys did not bind the model (stale scores replayed across releases) and the deployed model binary was never fingerprinted. Both failure modes are structurally impossible since v4.4.0: cache keys carry the model md5 (`model_fp` in every result JSON) and `pp_doctor` prints the model fingerprint for audit.
- **Model rollout halted by the new data-hygiene audit (negative result, data-closed)**: the planned supervised-layer retrain (v36: 7187 prior rows + 285 fresh current-generation samples) was deployed and initially evaluated at near-perfect separation (old-gen 0.9994) — then rejected by our own new contamination audit: those 285 "fresh" samples had been drawn from the current-generation eval set itself (64.6% of gen2026 eval docs entered training, 154 of them from the held-out half). All v36 numbers are void; the shipped supervised model remains **v35** (fingerprint `2631df3d388b`, re-export verified; the contamination audit shows v35's training data shares only 1 held-out doc with the eval corpora, so its numbers are clean). An honest retrain needs a fresh sampling round (currently frozen); `eval/check_leak.py` now gates every future training run.
- **Evaluation score cache binds the deployed model fingerprint**: `run_eval.py` cache keys now include the model md5 — swapping models can no longer silently replay stale scores (a 10-02 v36 eval reading "bit-identical 0.9022" was exactly this failure; the true v36 numbers surfaced only after the fix). Result JSONs carry `model_fp`.
- **ONNX export self-test + ONNX thread budget**: export now runs variable-length inference assertions before a binary ships (a transformers 4.57.6 regression baked the dynamic axes into a static seq=150 graph — it now dies at export, not in production); `PP_ORT_THREADS` caps the ONNX thread pool (default auto) — on 56-vCPU hosts the unrestricted pool thrashed (24.9 s/doc → ~1 s/doc at 8 threads); `pp_doctor` prints the model md5 fingerprint for audit.

## What's new in v4.3.0

- **Generation-split evaluation (infrastructure + first numbers)**: a 443-doc current-generation eval set (312 fresh AI samples from 9 families + 131 held-out human docs) now ships in `eval/corpora_small/eval_gen2026.jsonl`; `run_eval.py --layer` fixed. First quantified generational breakdown: pre-2026 corpus AUROC 0.9022 vs current-gen 0.6542 — the generation gap is now measured, not assumed.
- **Negative results ×2, data-closed**: spectrum v2 blend and the L13 surprisal signal both show no current-gen gains (bit-identical and 0.32 respectively) — the remaining remedy is supervised-layer retraining on fresh samples (planned).

## What's new in v4.2.0

- **Batch recursion**: `--batch DIR --recursive` walks subdirectories; per-file paths are reported relative to the root.
- **GitHub README**: the repository landing page now carries the tool description, quick start, family table, and compliance statement (agents discovering via `skills add` see the full picture).
- **Gate layer-3 distribution check**: post-revival verdict distribution verified on 40 held-out documents — zero parse failures, no systematic band shift (data archived).

## What's new in v4.1.0

- **Smoothness layer fused into the score (A/B-verified)**: the L13 surprisal-variation signal (0.06 weight in all length bands) is now part of the fusion. Held-out A/B: **AUROC bit-identical to baseline (0.9022), human FP unchanged** — the signal has real influence on current-generation text where it fires, at zero measured cost on the evaluation corpus.
- **Batch CSV output**: `--batch DIR --csv PATH` writes per-file results as CSV (Excel-friendly UTF-8 BOM).
- **Paragraph report disclosures**: the HTML attribution report now carries mixed-register warnings, register hints, and encoding warnings — consistent with the JSON report.

## What's new in v4.0.0

- **Cross-references**: reports and docs now include next-step pointers to adjacent tools (citation verification, deep research, figures) with the arXiv hallucinated-citation policy note.
- **Word-root coverage**: description now carries the full task-language root set (academic writing / polish / batch rewriting guidance / terminology) for search discoverability.
- **Family section cleanup**: docsor.cn placed after the member list; list continuity fixed (EN/ZH).

## What's new in v3.12.0

- **Translation-smell layer revived in the gate (substantive fix)**: deai_gate's layer-3 parser expected a `hits[]` array while `translation_smell_check --json` emitted only `total_hits` — the layer had been silently neutral (fallback 50) since the schema drifted. Schema aligned; the layer now genuinely contributes to the fused score.
- **Integrity notice on every report**: term_check / quality_report / style_distance / translation_smell outputs now carry the same academic-integrity notice as ai_detector/deai_gate — the "every report" claim is now literally true.
- **Paragraph-count consistency**: quality_report now counts paragraphs with the same whitespace/short-segment filtering as ai_detector (trailing-newline mismatch fixed).
- Negative results recorded: spectrum v2 blend (fresh-generation 0.15 mix) produced a bit-identical held-out AUROC — not adopted; L13 mid-length (300-800 chars) extension evaluated and declined (human-side evaluable sample too small, FPR 2/10 at threshold).
## What's new in v3.11.0

- **Batch detection (`--batch DIR`)**: score every `.txt`/`.md` file in a directory in one run — per-file scores, aggregate stats (mean/max/high-risk count), deterministic, files >5 MB skipped. Built for thesis-scale self-review.
- **Paragraph report consistency**: the HTML attribution report now carries the same academic-integrity notice as the CLI reports.
- **Negative result, honestly recorded**: cross-family tier-2 n-gram mining over 285 fresh samples yielded nothing beyond topic-word noise after guards (the two real markers were already registered) — pattern-recall expansion via n-grams has hit its ceiling, consistent with the v3.0 recalibration. Fingerprint registrations this cycle: none qualified (quality gate held).


## What's new in v3.10.0

- **Fingerprint freshness phase 3 (current-generation coverage)**: 135 fresh samples across four model families (kimi-k2.7 / minimax-m3 / deepseek-v4.1 / glm-5.3) via the OpenCode Go channel; **kimi-k2.7 registered** (zero-FP pattern, Kimi-family attribution verified), contaminated candidates (topic words, cross-family markers) rolled back per quality gate, glm-5.3 refreshed with no new patterns. Registry: 13 families. Quality over quantity — every registration is attribution-verified.

## What's new in v3.9.0

- **Discourse smoothness disclosure (L13, DivEye-inspired)**: a new surprisal-variation layer measures how uniformly word choice varies across sliding windows — AI generation tends to be smooth, human writing uneven. Held-out long-document stats: AUROC 0.8256 as a standalone signal, detection 66/146 at threshold 6, human false-positive 1/14. **By the reproducible-numbers iron law it is NOT fused into the score** (single-layer SNR insufficient); it appears as an evidence line in reports (`layers_surface.surprisal_variation_layer`, with a spectrum-coverage guard at 0.35 and an evidence discount for low-coverage text).
- **Layer evaluation mode**: `python eval/run_eval.py --layer surprisal --split test` gives any report layer a reproducible AUROC/detection/FPR card (results saved to `eval/results/layer_*.json`) — the framework that let us measure L13 honestly instead of shipping it fused on faith.

## What's new in v3.8.0

- **Mixed-register signal (`mixed_signal`)**: when paragraph scores diverge sharply, reports now say so explicitly ("document may combine human and AI writing; document-level score unreliable") and point to `paragraph_report.py` — turning the documented mixed-document limitation (AUROC 0.38 document-level) into an in-engine guardrail (aligned with the field's move to three-class human/AI/mixed evaluation and bidirectional paraphrase benchmarks).
- **Register hint (`register_hint`)**: colloquial/narrative features in Chinese text trigger an advisory that scores are calibrated on academic prose.
- **Encoding warning (`encoding_warning`)**: many undecodable bytes (GBK/binary) trigger a distortion warning.
- **Gate layer-divergence disclosure**: deai_gate reports when the word layer and style layer disagree sharply (≥30), a pattern seen in deliberate style-imitation rewrites and register mixing.
- **Safety and behavior statement**: self-verifiable local-only / no-upload / no-credential / no-persistence commitments (aligned with platform review trends).
- **Fingerprint freshness second pass**: qwen3.8 balanced sampling (35 docs) yielded no low-FP patterns — honestly not registered (same as deepseek-v4); kimi-k3 registration stands.

## What's new in v3.7.0

- **Discourse-structure heuristic layer (L12)**: detects social-media-style document-level AI patterns — hook ("先看一个场景"/"imagine…") + reversal ("不是X，是Y") + slogan ("把这句话记住"/"划重点") + engagement bait / parallelism / self-Q&A / spoken-word closing / emotional intensifiers — eight pattern groups; ≥2 distinct groups add a density-scaled bump (8×groups + hits capped at 8, total cap 30); single-group hits are recorded without scoring (zero false-positive impact on academic prose). Fixes a sentence-layer blind spot: pure discourse-pattern text previously scored 21-32/low (AgentOps LES-20260923-021); held-out academic regression bit-identical (AUROC 0.9022, zero false positives).
- **FAQ section (evaluation-driven: C dimension "lacks a centralized FAQ")**: ten high-frequency questions — short-text policy, medical-register over-scoring, supervised-layer install/verification, degraded_mode semantics, non-interchangeability with CNKI/Wanfang, layer-failure fallback, edit_extent scope, English support boundary, label-check usage.
- **Script cheat sheet (C: "per-script usage could be more detailed")**: purpose/flags/output for all eight entry points in one table.
- **Clearer edge-case errors (R)**: style_distance now explains *why* no style score was produced (no sentence boundaries / no body paragraphs) instead of a generic "too short".

## What's new in v3.6.0

- **Academic-integrity guardrails**: every report now carries an explicit `integrity_notice` field/line; new "Academic integrity" section; positioning stated plainly — author self-review and writing quality, compliance with disclosure rules, not detector evasion.
- **Positioning clarified**: documentation wording aligned to the quality-framed scope (detection and revision guidance stay; no detector-evasion framing).

## What's new in v3.5.0

- **Degraded-mode disclosure**: `ai_detector.py` now reports `degraded_mode` + `degraded_notice` (JSON and text) whenever the supervised layer is absent, disabled (`PP_NO_SUP=1`), or skipped by language gating — including the medical-register over-score warning with the actual held-out numbers.
- **Iron law #2 enforced**: texts under 100 characters now return `risk=unknown` with an explicit no-verdict notice (previously documented but not implemented; short texts also show as "cannot judge" in `quality_report.py` instead of a misleading green).
- **`scripts/pp_doctor.py`**: one-command environment self-check — data integrity, script compilation, optional deps, model presence, supervised-layer loadability, short-text/long-text/determinism probes, deai_gate guard. Exit 0 = green.
- **`deai_gate.py` usage guard + closed fallback loop**: `--help` / missing file no longer run the gate on a bogus filename; layer timeouts are caught (neutral 50); a failed smell layer now falls back to a neutral 50 instead of 0, and a failed terminology layer no longer dumps tracebacks into notes.
- **Chinese-Windows encoding hardening**: every entry point forces UTF-8 stdout/stderr and tolerates non-UTF-8 (e.g. GBK) input files — no more crashes on default zh-CN consoles (found by adversarial multi-expert testing).
- Docs rebuilt in honest dual-language form (this file + SKILL_ZH.md); trigger words expanded (AI率 / 查AI率 / AIGC 检测 …).


## What's new in v4.6.0

- **End-to-end workflow (`scripts/pp_workflow.py` / `pp_api.workflow()`)**: one command runs the full self-check — AI-rate detection, paragraph-level attribution, 4-layer gate, terminology, translation-smell, style, quality report, AIGC label self-check — and writes a single Markdown report plus the full JSON. Worked example in § Quick start.
- **TL;DR layer & docs restructure**: a 30-second orientation section now sits at the top; historical release notes moved to `CHANGELOG.md`; anti-pattern guidance is consolidated in one section; the English FAQ is now on par with the Chinese one.
- **Cleaner eval archive & actionable errors**: superseded eval artifacts moved to `eval/results/archive/`; pp_api/pp_setup errors now carry recovery hints.

---

# 更新日志（中文）

> v4.6.0 起历史更新说明移出 SKILL_ZH.md（新用户更快触达工作流）。最新在前。各版本摘要亦见 SKILL_ZH.md § 版本历史。

## v4.5.0 更新内容

- **Python API（`scripts/pp_api.py`）**：引擎可直接 import。`detect_text(text)` 进程内跑完整检测（与 CLI 同一代码路径——已做同源校验），返回纯 JSON 兼容 dict；配套 `gate_text`、`term_report`、`smell_report`、`style_report`、`quality_report_file`、`attribution`、`model_fingerprint`、`doctor_summary`。零网络、零第三方依赖、非法输入抛异常不静默。程序化集成从此不必包装 subprocess。
- **一键装模（`scripts/pp_setup.py`）**：`--model <文件>` 取代多步手动放置。先按作者签发指纹注册表（`references/supervised_models.json`）校验 md5——未登记权重一律拒绝（exit 2）——再安装、推理金丝雀自检、GREEN 确认；`--check` 查看现状。模型依旧不随包、绝不联网下载（100% 本地契约不变）。

## v4.4.0 更新内容

- **头条数字在可信测量下重测——变了**：老代留出 AUROC **0.9998**（原以为 0.9022）、当打代 AUROC **0.9400**（原以为 0.6542）、人类误报@medium **2.3%**（原以为约 20%）。旧数字是测量伪象：评测分数缓存键不绑定模型（陈旧分跨版本复放）、部署模型二进制从未指纹化。两类故障自 v4.4.0 起结构性不可能：缓存键携带模型 md5（结果 JSON 带 `model_fp`）、pp_doctor 打印模型指纹供对账。
- **数据卫生审计叫停监督层再训练（负结果，数据闭环）**：原计划的 v36 再训练（7187 行旧数据+285 篇当打代新鲜样本）已部署、并一度测出近乎完美的分离度（老代 0.9994）——随即被本版新增的污染审计否决：**那 285 篇「新鲜样本」直接取自当打代评测集本身**（gen2026 评测集 64.6% 文档进入训练集、其中 154 篇属于留出半）。v36 全部数字作废；线上监督模型维持 **v35**（指纹 `2631df3d388b`，重导出已验证；污染审计显示 v35 训练数据与评测语料仅 1 篇留出集交集，其数字干净）。诚实的再训练需要新一轮采样（当前冻结）；`eval/check_leak.py` 从此把守每一次训练。
- **评测分数缓存绑定部署模型指纹**：`run_eval.py` 缓存键纳入模型 md5——换模型不再可能静默复用陈旧分（10-02 那份「位级 0.9022」的 v36 评测正是此故障；修复后 v36 的真实数字才浮出水面）。结果 JSON 携带 `model_fp`。
- **ONNX 导出自检 + 线程预算**：导出脚本在产出二进制前强制变长推理断言（transformers 4.57.6 回归会把动态轴烘焙成静态 seq=150——现在坏图在导出当场爆掉，不会流进生产）；`PP_ORT_THREADS` 限制 ONNX 线程池（默认自动）——56 vCPU 机器上不限线程会互踩（24.9 秒/篇 → 8 线程约 1 秒/篇）；`pp_doctor` 现打印模型 md5 指纹供对账。

## v4.3.0 更新内容

- **分代评测基础设施（首批数字）**：新增当打代评测集 `eval/corpora_small/eval_gen2026.jsonl`（312 篇当打代 AI×9 家族+131 篇人类留出=443 篇）；`run_eval.py --layer` 修复。**首批分代数字：老代语料 0.9022 vs 当打代 0.6542——代际退化首次量化**（此前 AUROC 混合老代样本，当打代检测力不可见）。
- **负结果×2 数据闭环**：谱 v2 混合与 L13 平滑度信号在当打代均无增益（逐位相同/方向不支持）——当打代补救唯一路径=监督层再训练（285 篇当打代样本已在手，规划中）。

## v4.2.0 更新内容

- **批处理递归**：`--batch 目录 --recursive` 遍历子目录，文件路径相对根目录呈现。
- **GitHub README**：仓库落地页现包含工具说明、快速开始、家族工具表与合规声明（skills add 发现渠道可见全貌）。
- **门禁层3 分布复核**：复活后 40 篇留出文档判定分布验证——零解析失败、无系统性偏移（数据入档）。

## v4.1.0 更新内容

- **平滑度层正式入融合（A/B 验证）**：L13 surprisal-variation 信号（各长度带 0.06 权重）纳入融合计分。留出集 A/B：**AUROC 与基线逐位相同（0.9022）、人类误报不变**——信号在当打代文本上触发时有真实影响力，评测语料零代价。
- **批处理 CSV 输出**：`--batch DIR --csv 路径` 逐文件结果落 CSV（UTF-8 BOM，Excel 友好）。
- **段落报告披露一致化**：HTML 归因报告现携带混写预警/语域提示/编码警示——与 JSON 报告一致。

## v4.0.0 更新内容

- **相关工具互引**：报告与文档在相邻环节出口处加入下一步工具提示（引用核验、深度调研、配图），并附 arXiv 幻觉引用禁投政策提醒。
- **任务词根全覆盖**：description 融入完整任务词根集（academic writing / polish / batch rewriting guidance / terminology），搜索可发现性对齐 cite-holmes 口径。
- **家族段整理**：docsor.cn 移至成员列表后；列表连续性修复（EN/ZH）。

## v3.12.0 更新内容

- **翻译腔层复活（实质性修复）**：deai_gate 层3 解析器期望 hits[] 数组，而 translation_smell --json 只输出 total_hits——schema 漂移以来该层一直静默走中性 50 兜底。已对齐 schema，翻译腔层首次真正参与融合计分。
- **诚信提示全报告覆盖**：term_check / quality_report / style_distance / translation_smell 输出现携带与 ai_detector/deai_gate 相同的学术诚信提示——"每份报告"的表述字面为真。
- **段落计数一致性**：quality_report 改用与 ai_detector 相同的空白/过短段过滤口径（尾随空行计数不一致修复）。
- 负结果入档：谱 v2 混合（新鲜代 0.15 配比）留出集逐位相同——不采纳；L13 中篇（300-800字）扩展经评估否决（人类可评样本过少、阈值下误报 2/10）。

## v3.11.0 更新内容

- **批处理检测（--batch 目录）**：一条命令打分目录内全部 .txt/.md 文件——逐文件分数+聚合统计（均分/最高/高风险文件数），确定性输出，>5MB 自动跳过。为论文级批量自查而生。
- **段落报告一致性**：HTML 归因报告头部加入与命令行报告相同的学术诚信提示。
- **负结果如实记录**：285 篇新鲜语料的跨家族 tier-2 n-gram 挖掘，守卫后只剩主题词噪声与两条已知标记——n-gram 召回扩展已到天花板（与 v3.0 重校准结论一致）。本轮指纹入册：无（质量门坚守）。

## v3.10.0 更新内容

- **指纹新鲜度第三期（当打模型覆盖）**：OpenCode Go 通道四家族新鲜采样 135 篇（kimi-k2.7 / minimax-m3 / deepseek-v4.1 / glm-5.3）；**kimi-k2.7 入册**（零误报模式，Kimi 族归因验证通过），主题词/跨家族污染候选按质量门回滚，glm-5.3 刷新无新模式。指纹库：13 家族。宁缺毋滥——每一笔入册都经归因验证。

## v3.9.0 更新内容

- **篇幅平滑度披露（L13，DivEye 思路本地化）**：新增 surprisal-variation 层——滑窗用词变化性刻画"AI 平滑、人类起伏"。留出集长文统计：独立信号 AUROC 0.8256、阈值 6 下检出 66/146、人类误报 1/14。**按"只报可复现的数字"铁律不进融合分**（单层信噪比不足）；以证据行形式出现在报告中（谱覆盖守卫 0.35 + 低覆盖证据折扣）。
- **报告层评测模式**：`python eval/run_eval.py --layer surprisal --split test`——给任何报告层一张可复现的 AUROC/检出/误报卡片（结果存 `eval/results/layer_*.json`）；正是这个框架让我们能诚实量化 L13，而不是凭信心把它融进分数。

## v3.8.0 更新内容

- **混写预警（mixed_signal）**：段落得分显著分化时如实提示"疑似人机混写、文档级分数不可单独采信"，并引导 `paragraph_report.py` 逐段归因——把能力边界矩阵中"混合文档 AUROC 0.38"的原理性局限变成引擎侧可操作指引（对齐学界混写检测方向：三分类人写/生成/润色与双向改写基准）。
- **语域提示（register_hint）**：检测到口语/叙事表达特征时提示"评分按学术语域校准、本场景仅供参考"——能力边界矩阵的引擎侧落地。
- **编码警示（encoding_warning）**：输入含大量不可解码字节（GBK/二进制）时提示结果可能失真。
- **门禁层间分歧披露**：deai_gate 在词级层与文体层方向显著矛盾（差 ≥30）时输出分歧说明（改写稿/语域混合常见）。
- **安全与行为声明节**：主动声明并可自主复核的本地运行/零上传/零凭证/无持久化承诺（平台审核趋势对齐）。
- **指纹新鲜度二轮**：qwen3.8 补齐均衡采样（35 篇）后无低误报模式过门槛——如实不入册（与 deepseek-v4 同处置）；kimi-k3 维持入册。

## v3.7.0 更新内容

- **篇章结构启发层（L12）**：新增自媒体式篇章级 AI 腔检测——八组模式（钩子/反转/口号/互动引导/排比三连/设问自答/口播收尾/情绪渲染）；≥2 组独立命中时按密度计分（8×组数+命中数，封顶 8，总封顶 30），单组命中仅记录不加分（学术零误伤），命中明细进报告。修复句层特征盲区：纯篇章结构文本此前仅得 21-32/低风险（AgentOps LES-20260923-021），现进入复核带；学术语料回归 AUROC 0.9022 逐位不变、零误伤。
- **FAQ 专节（评测驱动：C 维"缺少集中的常见问题解答章节"）**：10 条高频问题集中化——短文本为何不判定、医学文本为何偏高、监督层安装与确认、degraded_mode 含义、与知网/万方不可互换、层解析失败兜底、edit_extent 定位、英文支持边界、标识合规用法。
- **各脚本速查表（C 维"脚本用法说明可以更详细"）**：8 个入口的作用/关键参数/输出一表通览。
- **极端情况报错清晰化（R 维）**：style_distance 对无句边界/无正文段落场景给出具体原因与建议，替代原"文本过短"笼统提示。

## v3.6.0 更新内容

- **学术诚信护栏**：每份报告新增 `integrity_notice` 字段/提示行；新增「学术诚信」专节；定位明示——作者自查与写作质量改进、按规披露，不用于规避检测。
- **文档按平台政策加固**：英文文档（ClawHub 读取面）以质量口径措辞替换规避式表述；中文文档口径一致。

## v3.5.0 更新内容

- **降级模式披露（诚实工程）**：`ai_detector.py` 在监督层缺席/被 `PP_NO_SUP=1` 关闭/语言门控跳过时，JSON 与文本输出均带 `degraded_mode` + `degraded_notice`，并附医学语域高估警示（含留出集真实数字）。
- **铁律 2 落地**：不足 100 字的文本不再输出风险判定（`risk=unknown` + 提示）；此前只写在文档里、代码未实现——本版修复。`quality_report.py` 对短文本显示"无法判定"而非误导性的绿色。
- **`scripts/pp_doctor.py` 环境自检**：数据完整性、脚本可编译、可选依赖、模型在位与可加载、短文本/长文本/确定性探针、deai_gate 守卫，一条命令回答"能不能跑、跑的哪档"。
- **`deai_gate.py` 用法守卫与兜底闭环**：`--help`/缺失文件不再被当成文件名误跑门禁；层超时被捕获（中性 50）；翻译腔层解析失败改走中性 50 分而非 0 分（不再把垃圾输入推向 pass 带）；术语层失败不再把 Traceback 塞进 note。
- **中文 Windows 编码加固**：全部入口强制 UTF-8 输出并容错非 UTF-8（如 GBK）输入文件——zh-CN 默认控制台不再崩溃（多专家对抗测试发现）。
- 双语文档按诚实口径重建；触发词扩容（AI率/降AI/查AI率/论文AI率/降低AI率…）。


## v4.6.0 更新内容

- **端到端工作流（`scripts/pp_workflow.py` / `pp_api.workflow()`）**：一条命令跑完全部自查——AI 率检测、段落级归因、四层门禁、术语保护、翻译腔、文体、质量报告、AIGC 标识自查——产出单一 Markdown 报告+完整 JSON。示例见 § 快速开始。
- **TL;DR 层与文档重构**：顶部新增 30 秒上手层；历史更新说明迁至 `CHANGELOG.md`；反模式集中成节；英文 FAQ 对齐中文版。
- **评测存档整理与错误可行动化**：过时评测产物移入 `eval/results/archive/`；pp_api/pp_setup 错误信息附带恢复建议。


