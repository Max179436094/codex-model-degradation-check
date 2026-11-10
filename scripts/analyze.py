#!/usr/bin/env python3
"""对三次抽样回答做指标统计与判读。

用法:
    python3 scripts/analyze.py --dir ~/probe-1110
    python3 scripts/analyze.py --dir ~/probe-1110 --json
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

LIMIT_PATTERNS = [
    r"usage limit", r"rate limit", r"limit reached", r"try again later",
    r"too many requests", r"quota", r"upgrade to", r"plus 用户",
    r"使用上限", r"达到上限", r"稍后再试", r"请稍后", r"请求过于频繁",
    r"额度", r"限流", r"降级",
]

MD_COMMENT = re.compile(r"<!--.*?-->", re.S)
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|[一二三四五六七八九十]+[、.)]\s*)", re.M)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)
CODE_FENCE = re.compile(r"^```", re.M)
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)


def read_answer(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    text = MD_COMMENT.sub("", raw).strip()
    return text


def metrics(text: str) -> dict:
    chars = len(re.sub(r"\s", "", text))
    lines = len([ln for ln in text.splitlines() if ln.strip()])
    fences = len(CODE_FENCE.findall(text))
    code_blocks = fences // 2
    if fences % 2 == 1:  # 只有开头没有结尾，说明回答被截断
        code_blocks += 1
    lists = len(LIST_ITEM.findall(text))
    headings = len(HEADING.findall(text))
    tables = len([1 for ln in text.splitlines() if TABLE_ROW.match(ln)])
    hit = [p for p in LIMIT_PATTERNS if re.search(p, text, re.I)]
    return {
        "chars": chars,
        "lines": lines,
        "code_blocks": code_blocks,
        "list_items": lists,
        "headings": headings,
        "table_rows": tables,
        "limit_hits": sorted(set(hit)),
        "empty": chars < 20,
    }


def verdict(results: list, texts_ok: bool) -> tuple:
    """返回 (分类, 说明, 建议动作)"""
    valid = [r for r in results if not r["m"]["empty"]]
    if len(valid) < 2:
        return ("数据不足", "有效回答少于 2 条，无法判断。请补跑后再分析。",
                "补齐三次回答，且必须是同一模式、同一账号、同一节点")

    hits = sorted({h for r in valid for h in r["m"]["limit_hits"]})
    if hits:
        return ("真实降级 · 额度/限流层",
                f"回答中命中限流关键词: {', '.join(hits)}",
                "额度池告急会被降级到轻量模型。等额度恢复后重测；若长期出现，核对订阅状态")

    chars = [r["m"]["chars"] for r in valid]
    mean = statistics.mean(chars)
    spread = (max(chars) - min(chars)) / mean if mean else 0
    first, last = chars[0], chars[-1]
    structure_ok = all(
        r["m"]["list_items"] >= 2 or r["m"]["code_blocks"] >= 1 or r["m"]["headings"] >= 2
        for r in valid
    )

    if mean < 200:
        return ("需人工确认",
                f"平均仅 {mean:.0f} 字符，远低于完整作答所需长度",
                "先确认是否使用了 Codex 这类执行型模式（天生话少），排除后再判定为降级")

    # 递降要求「单调走低」：4x -> 1x -> 2x 属于剧烈波动，不算递降
    monotonic_down = all(b < a for a, b in zip(chars, chars[1:]))
    if len(chars) >= 3 and monotonic_down and last < first * 0.6:
        return ("真实降级 · 疑似递降",
                f"末轮比首轮短 {100 * (1 - last / first):.0f}%，且三轮持续走低",
                "同一任务三次递减，优先怀疑被 A/B 分到弱模型或被动态降级。换时段重测确认")

    if spread > 0.35:
        return ("疑似降级",
                f"轮间长度波动 {100 * spread:.0f}%，超出正常采样范围",
                "延长到 5 轮重测。若结构元素（分点数、代码块）同步减少，可判定降级")

    if spread >= 0.15 or not structure_ok:
        detail = f"轮间长度波动 {100 * spread:.0f}%"
        if not structure_ok:
            detail += "，且部分回答结构要素缺失"
        return ("正常波动", detail, "无需任何动作。单次长短属采样范围，观察即可")

    return ("稳定", f"轮间长度波动仅 {100 * spread:.0f}%，结构要素齐全", "无需任何动作")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="抽样包目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    base = os.path.expanduser(args.dir)
    files = sorted(
        glob.glob(os.path.join(base, "responses", "r*.md")),
        key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0),
    )
    if not files:
        print(f"[FAIL] 未找到回填文件: {base}/responses/r*.md")
        sys.exit(1)

    results = []
    for idx, path in enumerate(files, 1):
        text = read_answer(path)
        results.append({"round": idx, "file": os.path.basename(path),
                        "m": metrics(text), "text": text})

    category, detail, action = verdict(results, True)

    if args.json:
        print(json.dumps(
            {"rounds": [{k: v for k, v in r.items() if k != "text"} for r in results],
             "verdict": {"category": category, "detail": detail, "action": action}},
            ensure_ascii=False, indent=2))
        return

    print(f"抽测目录: {base}")
    print(f"回答文件: {len(results)} 条\n")
    header = f"{'轮次':<6}{'字符数':>8}{'行数':>7}{'代码块':>8}{'分点':>6}{'标题':>6}{'表格行':>8}"
    print(header)
    print("-" * len(header.encode("gbk", errors="ignore")))
    for r in results:
        m = r["m"]
        print(f"r{r['round']:<5}{m['chars']:>8}{m['lines']:>7}{m['code_blocks']:>8}"
              f"{m['list_items']:>6}{m['headings']:>6}{m['table_rows']:>8}")
    print()
    print(f"判读  : {category}")
    print(f"依据  : {detail}")
    print(f"建议  : {action}")


if __name__ == "__main__":
    main()
