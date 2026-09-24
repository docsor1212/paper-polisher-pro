#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freshness_refresh — 指纹保鲜流水线（月度执行，防"检测器永远慢一代"）。

由使用者在本地按月执行（或新模型发布当天手动触发）:
  1. 活体采样   各模型通道生成新语料（通道配置 freshness_channels.json, 缺通道则跳过）
  2. 频谱重建   build_spectrum.py (calib 半)
  3. 权重校准   calibrate_v3.py  (calib 半)
  4. 模式重校   pattern_recalibrator.py --apply (calib 半)
  5. 指纹挖掘   fingerprint_miner.py 各家族 (calib 半)
  6. 回归评测   run_eval.py --split test → 与上次结果对比, AUROC 掉 >3pt 告警

部署: 由使用者自行配置系统月度定时任务，本脚本不创建、不修改任何系统调度项。
  新模型当天: python3 freshness_refresh.py --model <family> --corpus <新采样jsonl>

本脚本只做编排, 各步骤独立可重跑; 每步输出记入 freshness_log/<date>.md。
"""
import os, sys, subprocess, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "..", "eval", "freshness_log")


def run_step(name, cmd, log):
    log.write("\n## %s\n$ %s\n" % (name, " ".join(cmd)))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                       cwd=HERE, timeout=1800)
    out = (r.stdout or "") + (r.stderr or "")
    log.write(out[-3000:] + "\n[exit=%d]\n" % r.returncode)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(
        "pp_corpus", "eval_zh.jsonl"),
        help="基础语料(大语料jsonl)")
    ap.add_argument("--model", default=None, help="新模型名(触发单家族挖掘)")
    ap.add_argument("--skip-miner", action="store_true")
    a = ap.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    today = time.strftime("%Y%m%d")
    log = open(os.path.join(LOG_DIR, today + ".md"), "w", encoding="utf-8")
    log.write("# 指纹保鲜运行 %s\n" % time.strftime("%Y-%m-%d %H:%M"))
    py = sys.executable
    ok = True
    ok &= run_step("频谱重建", [py, "build_spectrum.py", "--corpus", a.corpus, "--apply"], log)
    ok &= run_step("权重校准", [py, "calibrate_v3.py", "--corpus", a.corpus, "--apply"], log)
    ok &= run_step("模式重校", [py, "pattern_recalibrator.py", "--corpus", a.corpus, "--apply"], log)
    if a.model:
        ok &= run_step("指纹挖掘:" + a.model,
                       [py, "fingerprint_miner.py", "--corpus", a.corpus,
                        "--model", a.model, "--apply"], log)
    elif not a.skip_miner:
        import json
        reg_p = os.path.join(HERE, "..", "references", "model_fingerprints.json")
        try:
            fams = list(json.load(open(reg_p, encoding="utf-8"))["families"].keys())
        except Exception:
            fams = []
        for fam in fams:
            run_step("指纹挖掘:" + fam,
                     [py, "fingerprint_miner.py", "--corpus", a.corpus,
                      "--model", fam, "--apply"], log)
    # 回归(留出半)
    ev = os.path.join(HERE, "..", "eval", "run_eval.py")
    r = subprocess.run([py, ev, "--corpus", a.corpus, "--split", "test",
                        "--tag", "freshness_" + today],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    log.write("\n## 回归评测\n" + (r.stdout or "")[-3000:])
    log.write("\n---\n状态: %s\n" % ("✅ 全部成功" if ok else "⚠️ 有步骤失败, 见上文"))
    log.close()
    print("日志: %s" % os.path.join(LOG_DIR, today + ".md"))
    print("提醒: 对比 eval/results/ 下最新两次 freshness_*.json 的 AUROC, 掉幅>3pt 需人工介入。")


if __name__ == "__main__":
    main()
