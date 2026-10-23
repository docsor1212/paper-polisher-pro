#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pp_mcp_server.py — paper-polisher-pro MCP server（v6.5.0 新增；pp.py mcp）

零依赖 Model Context Protocol (MCP) stdio server：纯标准库实现 JSON-RPC 2.0
（newline-delimited），不引入任何第三方包——与引擎的零依赖立场一致。任何
MCP 客户端（Claude Code / Cursor / 其它 agent）把本文件注册为 stdio server
即可直接调用八个工具，全部本地运行、零网络：

    python3 scripts/pp_mcp_server.py        # stdio（默认）
    python3 scripts/pp.py mcp               # 等价入口

工具面（全部只读自查，不代改文稿；与 CLI 同一引擎、同一退出码语义）：
  pp_detect      文本 → AI 率 + 风险带 + 分层证据（<100 字按铁律返回 unknown）
  pp_fix_suggest 文本 → 句子级改写建议（指位+策略，不代改）
  pp_style_norm  文本 → 学术规范自查（全半角/数字/缩写/单位/LLM 腔，不评分）
  pp_term_check  文本 → 术语保护检查（同概念异写一致性）
  pp_workflow    文本 → 端到端完整自查报告 JSON
  pp_explain     workflow 报告 JSON → 人话三段（结论/证据/行动清单）
  pp_faq         关键词 → FAQ 检索
  pp_doctor      无参 → 环境自检（能跑吗/跑哪档）

诚实边界：分数为引擎口径相对参考，不用于规避机构 AIGC 检测；每个工具描述
里如实声明。输出统一截断（默认 12000 字符）防止撑爆客户端会话。
"""
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER_VERSION = "6.5.0"
PROTOCOL_VERSION = "2024-11-05"   # 与主流客户端兼容的稳定基线
MAX_OUTPUT = 12000                # 单工具返回上限（字符）
MAX_TEXT = 2_000_000              # 输入文本上限（字符，约 2MB）——防撑爆

_INTEGRITY = ("学术诚信：工具供作者自查与改进写作质量，不用于规避机构 AIGC 检测；"
              "分数为引擎口径的相对参考。")


# ── 工具实现层（subprocess 调包内脚本；与 CLI 完全同源） ─────────────────

def _run_script(args, timeout=300, stdin_text=None):
    """跑包内脚本，返回 (rc, stdout, stderr)。UTF-8 强制。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + args, capture_output=True,
                       timeout=timeout, env=env, input=stdin_text, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def _tmp_input(text, suffix=".txt"):
    """入参文本落临时文件（utf-8），返回路径；with 块外由调用方清理。"""
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False,
                                    encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def _clip(s, limit=MAX_OUTPUT):
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n…[truncated +{len(s) - limit} chars]"


def _wrap_json(rc, out, note=""):
    """JSON 工具统一包装：引擎 JSON 原样透传，附退出码语义注。

    超限的合法 JSON 不能硬截断（半截 JSON 坑消费者）——改为返回合法的
    摘要 JSON（顶层键+体量+建议），文本输出才走字符截断。
    """
    if rc == 0 and out.strip():
        body = out
        if len(body) > MAX_OUTPUT:
            try:
                parsed = json.loads(body)
                body = json.dumps({
                    "truncated_for_mcp": True,
                    "size_chars": len(body),
                    "top_level_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
                    "aggregate": parsed.get("aggregate") or parsed.get("detect", {}).get("aggregate")
                    if isinstance(parsed, dict) else None,
                    "note": ("报告超出 MCP 单工具输出上限，此处仅摘要；"
                             "完整报告请用 CLI（python3 scripts/pp.py workflow <文稿>）落盘后阅读，"
                             "或直接调 pp_explain 工具拿人话三段。"),
                }, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                body = _clip(body)
    else:
        body = json.dumps({"mcp_error": f"engine exit {rc}",
                           "stderr": (out + "\n" + "─" * 0 + "").strip() or None,
                           "exit_code_meaning": {0: "成功", 1: "运行完成但未通过",
                                                 2: "用法/输入错误", 3: "环境不满足"}.get(rc, "见 SKILL.md")},
                          ensure_ascii=False)
    tail = f"\n\n({note})" if note else ""
    return _clip(body) + tail


def tool_detect(text):
    path = _tmp_input(text)
    try:
        rc, out, err = _run_script([str(HERE / "ai_detector.py"), path, "--format", "json"])
        return _wrap_json(rc, out, _INTEGRITY)
    finally:
        os.unlink(path)


def tool_fix(text, top=10):
    top = max(1, min(int(top), 50))
    path = _tmp_input(text)
    try:
        rc, out, err = _run_script([str(HERE / "pp_fix_suggest.py"), path,
                                    "--top", str(top), "--json"])
        return _wrap_json(rc, out, "只指位+策略，不代改；改不改由作者决定")
    finally:
        os.unlink(path)


def tool_norm(text, checks=None):
    path = _tmp_input(text)
    try:
        args = [str(HERE / "pp_style_norm.py"), path, "--json"]
        if checks:
            args += ["--checks", str(checks)]
        rc, out, err = _run_script(args)
        return _wrap_json(rc, out, "机械体例核对，不评分")
    finally:
        os.unlink(path)


def tool_term(text):
    path = _tmp_input(text)
    out_path = path + ".term.json"
    try:
        rc, out, err = _run_script([str(HERE / "term_check.py"), path,
                                    "--output", out_path])
        if Path(out_path).is_file():
            return _wrap_json(rc, Path(out_path).read_text(encoding="utf-8"),
                              "术语保护检查；--auto-fix 自动修复仅在 CLI 提供")
        return _wrap_json(rc, out)
    finally:
        os.unlink(path)
        Path(out_path).unlink(missing_ok=True)


def tool_workflow(text):
    path = _tmp_input(text)
    outdir = tempfile.mkdtemp(prefix="ppp_mcp_wf_")
    try:
        rc, out, err = _run_script([str(HERE / "pp_workflow.py"), path,
                                    "--outdir", outdir], timeout=600)
        wf = Path(outdir) / (Path(path).stem + ".workflow.json")
        if wf.is_file():
            raw = wf.read_text(encoding="utf-8")
            if len(raw) <= MAX_OUTPUT:
                return _wrap_json(rc, raw, "端到端完整报告；解读可再调 pp_explain")
            # 超限：客户端拿不回完整 JSON——直接内置 explain，返回合法摘要+人话三段
            rc2, exp, err2 = _run_script([str(HERE / "pp_explain.py"), str(wf)])
            parsed = json.loads(raw)
            summary = {
                "truncated_for_mcp": True,
                "size_chars": len(raw),
                "top_level_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
                "aggregate": parsed.get("detect", {}).get("aggregate")
                if isinstance(parsed, dict) else None,
                "plain_reading": exp,
                "note": ("完整报告超出 MCP 单工具输出上限；以上为人话三段全文与聚合摘要，"
                         "逐段落明细请用 CLI 落盘阅读（python3 scripts/pp.py workflow <文稿>）。"),
            }
            return _wrap_json(rc, json.dumps(summary, ensure_ascii=False))
        return _wrap_json(rc, out)
    finally:
        os.unlink(path)


def tool_explain(report_json):
    path = _tmp_input(report_json, suffix=".json")
    try:
        rc, out, err = _run_script([str(HERE / "pp_explain.py"), path])
        return _wrap_json(rc, out)
    finally:
        os.unlink(path)


def tool_faq(query):
    rc, out, err = _run_script([str(HERE / "pp.py"), "faq", str(query)])
    return _clip(out if out.strip() else err)


def tool_doctor():
    rc, out, err = _run_script([str(HERE / "pp_doctor.py")])
    return _clip(out if out.strip() else err)


# ── 工具声明（MCP tools/list） ──────────────────────────────────────────

_TEXT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string",
                            "description": "待自查的中文文稿全文"}},
    "required": ["text"],
}

TOOLS = [
    {"name": "pp_detect",
     "description": ("AI 率检测：返回总分(0-100)、风险带、分层证据与可选的模型指纹归因。"
                     "少于 100 字按设计返回 unknown（短文本铁律）。本地运行，零网络。"),
     "inputSchema": _TEXT_SCHEMA},
    {"name": "pp_fix_suggest",
     "description": ("句子级改写建议：标出哪些句子带 AI 写作特征、为什么、怎么改（指位+策略，"
                     "绝不代改）。本地运行，零网络。"),
     "inputSchema": {"type": "object",
                     "properties": {"text": {"type": "string"},
                                    "top": {"type": "integer", "default": 10,
                                            "description": "返回问题最多的前 N 句（1-50）"}},
                     "required": ["text"]}},
    {"name": "pp_style_norm",
     "description": ("学术写作规范自查：全半角/数字用法/缩写定义/单位格式/LLM 腔。机械核对，"
                     "不评分。本地运行，零网络。"),
     "inputSchema": {"type": "object",
                     "properties": {"text": {"type": "string"},
                                    "checks": {"type": "string",
                                               "description": "逗号分隔子集：fullwidth,numbers,abbrev,units,consistency,llm_jargon（缺省=全查）"}},
                     "required": ["text"]}},
    {"name": "pp_term_check",
     "description": "术语保护检查：同概念异写一致性、非规范缩写提示。本地运行，零网络。",
     "inputSchema": _TEXT_SCHEMA},
    {"name": "pp_workflow",
     "description": ("端到端完整自查：一次产出检测+段落分级+规范+术语+门禁+台账的完整 JSON 报告"
                     "（篇幅大，建议配合 pp_explain 使用）。本地运行，零网络。"),
     "inputSchema": _TEXT_SCHEMA},
    {"name": "pp_explain",
     "description": ("报告解读器：把 pp_workflow 返回的 JSON 报告翻成人话三段（结论/证据/行动清单）。"),
     "inputSchema": {"type": "object",
                     "properties": {"report_json": {"type": "string",
                                                    "description": "pp_workflow 返回的完整 JSON 字符串"}},
                     "required": ["report_json"]}},
    {"name": "pp_faq",
     "description": ("FAQ 关键词检索：医学/短文本/PDF/英文/退出码/装模/分数漂移等高频问题。"),
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string",
                                              "description": "关键词，如：医学、PDF、退出码"}},
                     "required": ["query"]}},
    {"name": "pp_doctor",
     "description": "环境自检：能跑吗/跑哪一档/缺什么（无参数）。本地运行，零网络。",
     "inputSchema": {"type": "object", "properties": {}}},
]

_TOOL_FN = {
    "pp_detect": lambda a: tool_detect(a["text"]),
    "pp_fix_suggest": lambda a: tool_fix(a["text"], a.get("top", 10)),
    "pp_style_norm": lambda a: tool_norm(a["text"], a.get("checks")),
    "pp_term_check": lambda a: tool_term(a["text"]),
    "pp_workflow": lambda a: tool_workflow(a["text"]),
    "pp_explain": lambda a: tool_explain(a["report_json"]),
    "pp_faq": lambda a: tool_faq(a["query"]),
    "pp_doctor": lambda a: tool_doctor(),
}


# ── JSON-RPC 2.0 over stdio（newline-delimited） ────────────────────────

def _reply(msg_id, result):
    return json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result},
                      ensure_ascii=False)


def _error(msg_id, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": msg_id,
                       "error": {"code": code, "message": message}},
                      ensure_ascii=False)


def handle(req):
    """处理一条请求对象，返回回复字符串或 None（通知不回复）。"""
    method = req.get("method", "")
    msg_id = req.get("id")
    if method == "initialize":
        return _reply(msg_id, {
            "protocolVersion": req.get("params", {}).get("protocolVersion",
                                                         PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "paper-polisher-pro",
                           "version": SERVER_VERSION},
        })
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _reply(msg_id, {})
    if method == "tools/list":
        return _reply(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name not in _TOOL_FN:
            return _error(msg_id, -32602, f"unknown tool: {name}")
        text = None
        for v in args.values():
            if isinstance(v, str):
                text = v if text is None else text
        if isinstance(text, str) and len(text) > MAX_TEXT:
            return _error(msg_id, -32602,
                          f"input too large ({len(text)} chars > {MAX_TEXT})")
        try:
            out = _TOOL_FN[name](args)
        except subprocess.TimeoutExpired:
            out = "引擎超时（>600s）。文稿过长时建议分段自查。"
        except KeyError as e:
            return _error(msg_id, -32602, f"missing argument: {e}")
        except Exception as e:  # 引擎异常如实回传，不伪装成功
            out = json.dumps({"mcp_error": repr(e)[:200]}, ensure_ascii=False)
        return _reply(msg_id, {"content": [{"type": "text", "text": out}]})
    if msg_id is None:
        return None  # 未知通知：静默
    return _error(msg_id, -32601, f"method not found: {method}")


def main():
    # 行缓冲读 stdin；每行一条 JSON。stdout 只写协议消息（引擎输出全部被捕获）。
    instream = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8",
                                errors="replace")
    for line in instream:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(_error(None, -32700, "parse error") + "\n")
            sys.stdout.flush()
            continue
        try:
            resp = handle(req)
        except Exception as e:  # 协议层兜底：绝不因单条消息崩溃整个 server
            resp = _error(req.get("id"), -32603, repr(e)[:200])
        if resp is not None:
            sys.stdout.write(resp + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
