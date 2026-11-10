#!/usr/bin/env python3
"""可选：有 OpenAI API Key 时自动跑三次抽样。

用法:
    export OPENAI_API_KEY=sk-...
    python3 scripts/probe_api.py --out ~/probe-1110 --model gpt-5

说明:
    - 必须固定 temperature，否则长度波动来自采样而非模型本身
    - 会自动写入 responses/rN.md，可直接交给 analyze.py 分析
    - 不依赖第三方库，只用标准库 urllib
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

from make_probe_pack import TASKS


def call(api_key: str, model: str, prompt: str, temperature: float, timeout: int = 180) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="抽样包目录（与 make_probe_pack 一致）")
    ap.add_argument("--model", default="gpt-5", help="模型名")
    ap.add_argument("--task", default="code", choices=sorted(TASKS))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("[FAIL] 未设置 OPENAI_API_KEY")

    out = os.path.expanduser(args.out)
    resp_dir = os.path.join(out, "responses")
    os.makedirs(resp_dir, exist_ok=True)

    prompt = TASKS[args.task]
    for i in range(1, args.rounds + 1):
        print(f"[{i}/{args.rounds}] 调用 {args.model} ...", end=" ", flush=True)
        try:
            text = call(api_key, args.model, prompt, args.temperature)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            print(f"HTTP {e.code} -> {body}")
            if e.code in (429, 403):
                print("  命中限流或地区拦截，这一轮数据作废")
            raise SystemExit(1)
        except Exception as e:  # noqa: BLE001
            print(f"失败: {e}")
            raise SystemExit(1)
        with open(os.path.join(resp_dir, f"r{i}.md"), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{len(text)} 字符")
        time.sleep(1.5)

    print(f"\n[OK] 已写入 {resp_dir}")
    print(f"     下一步: python3 scripts/analyze.py --dir {out}")


if __name__ == "__main__":
    main()
