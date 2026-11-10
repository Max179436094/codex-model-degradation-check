#!/usr/bin/env python3
"""生成三次同任务抽样包。

用法:
    python3 scripts/make_probe_pack.py --out ~/probe-1110
    python3 scripts/make_probe_pack.py --out ~/probe-1110 --task reasoning

产出:
    <out>/probe-1.txt ~ probe-3.txt   三条完全相同的任务 prompt
    <out>/responses/r1.md ~ r3.md     回填模板
    <out>/meta.json                   本次抽测的元信息（模式、时间）
"""
import argparse
import json
import os
from datetime import datetime

TASKS = {
    "code": (
        "把一个目录下 40 个 CSV 文件（每个约 3 万行，列结构不完全一致）\n"
        "合并成一张总表，并去掉重复行。请按下面四部分作答，不要省略任何一部分：\n\n"
        "1. 先用三句话说明这件事最容易出错的地方在哪\n"
        "2. 给出可直接执行的命令行步骤，逐步编号\n"
        "3. 给出完整可运行的 Python 脚本\n"
        "4. 最后列出 3 条验证合并结果正确性的方法\n"
    ),
    "reasoning": (
        "一家公司全国有 8 个中心仓、20 个城市仓，商品从中心仓发往城市仓再发给客户。\n"
        "现在要把 28 个仓合并成 20 个，同时保证履约时效不下降。请按下面四部分作答，不要省略任何一部分：\n\n"
        "1. 先用三句话说明合并的最大风险是什么\n"
        "2. 列出决策前必须拿到的 5 个关键数据项，并说明每项用来判断什么\n"
        "3. 给出分阶段推进的步骤，标注每个阶段的可回退条件\n"
        "4. 最后给出 3 个衡量合并是否成功的指标，含计算方式\n"
    ),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="抽样包输出目录")
    ap.add_argument("--task", default="code", choices=sorted(TASKS), help="任务类型")
    ap.add_argument("--rounds", type=int, default=3, help="抽样轮数，默认 3")
    args = ap.parse_args()

    out = os.path.expanduser(args.out)
    resp_dir = os.path.join(out, "responses")
    os.makedirs(resp_dir, exist_ok=True)

    task = TASKS[args.task]
    for i in range(1, args.rounds + 1):
        with open(os.path.join(out, f"probe-{i}.txt"), "w", encoding="utf-8") as f:
            f.write(task)
        with open(os.path.join(resp_dir, f"r{i}.md"), "w", encoding="utf-8") as f:
            f.write(
                f"<!-- 第 {i} 轮：把模型完整回答原样粘贴到本行以下，不要编辑、不要删减 -->\n\n"
            )

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "task_type": args.task,
        "rounds": args.rounds,
        "note": "三次必须同模式、同账号、同节点；中途切换则整组作废",
    }
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[OK] 抽样包已生成: {out}")
    print(f"     任务类型: {args.task}   轮数: {args.rounds}")
    print()
    for i in range(1, args.rounds + 1):
        print(f"  第 {i} 轮: 复制 {out}/probe-{i}.txt 的内容 -> 模型 -> 回答粘回 {resp_dir}/r{i}.md")
    print()
    print(f"  回填完成后运行: python3 scripts/analyze.py --dir {out}")


if __name__ == "__main__":
    main()
