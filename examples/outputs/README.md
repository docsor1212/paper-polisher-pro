# 输出样例（真实引擎产物，非手写）

由 v5.6.0+ 引擎对真实医学文档片段生成，供集成前了解各 JSON 的结构与字段。

- `detect_sample.json` — ai_detector / pp_api.detect_text 的完整响应（概率、分层证据、risk_bands、指纹）
- `style_norm_llm_jargon_sample.json` — 规范自查第 7 查（llm_jargon 三层）的 findings 结构
- `fix_suggest_sample.json` — 句子级改写建议的结构（stats + top 建议）
- `workflow_sample.json` — pp_workflow 端到端报告的完整 JSON（全部检查小节；段落文本已截断）
- `report_html_sample.html` — 上述样例经 pp_report_html.py 渲染的单文件仪表盘（可直接浏览器打开）

编程接口见 SKILL.md § Python API；任何字段变更都会在 CHANGELOG 声明。
