#!/usr/bin/env bash
# 网络与地区核查：排除「地区限制 / 线路阻断」这类非模型因素
# 用法: bash scripts/network_check.sh [代理端口]
set -uo pipefail

PORT="${1:-}"

# --- 1. 自动探测系统代理端口 ---
if [ -z "$PORT" ]; then
  PORT=$(scutil --proxy 2>/dev/null | awk '/HTTPPort|HTTPSPort/ {print $3; exit}')
fi
if [ -z "$PORT" ]; then
  for p in 7897 7890 1087 8889 6152; do
    if nc -z -G 1 127.0.0.1 "$p" 2>/dev/null; then PORT=$p; break; fi
  done
fi
if [ -z "$PORT" ]; then
  echo "[FAIL] 未找到可用代理端口，先确认梯子是否开启"
  exit 1
fi
echo "[INFO] 代理端口: $PORT"
echo

# --- 2. 走代理的出口 ---
echo "=== 走代理的出口 ==="
PROXY_TRACE=$(curl -s --max-time 12 -x "http://127.0.0.1:$PORT" https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null)
if [ -z "$PROXY_TRACE" ]; then
  echo "[FAIL] 代理不通，无法取出口信息"
else
  echo "$PROXY_TRACE" | grep -E '^(ip|loc|colo)='
  LOC=$(echo "$PROXY_TRACE" | awk -F= '/^loc=/{print $2}')
  IP=$(echo "$PROXY_TRACE" | awk -F= '/^ip=/{print $2}')
  if [ "$LOC" = "CN" ]; then
    echo "[WARN] 走代理出口仍为中国大陆，节点路由有问题"
  else
    echo "[OK] 出口地区: $LOC"
  fi
fi
echo

# --- 3. 直连出口（应暴露出国内 IP，用于确认代理确实生效）---
echo "=== 直连出口（不走代理）==="
curl -s --max-time 8 https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -E '^(ip|loc)=' || echo "[WARN] 直连探测失败"
echo

# --- 4. OpenAI / Codex 端点状态码（000 时重试一次，排除偶发抖动）---
probe() {
  local method="$1" url="$2" code
  for attempt in 1 2; do
    if [ "$method" = "POST" ]; then
      code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 -x "http://127.0.0.1:$PORT" -X POST "$url")
    else
      code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 -x "http://127.0.0.1:$PORT" "$url")
    fi
    [ "$code" != "000" ] && break
    sleep 1
  done
  printf "%-4s %-45s -> HTTP %s\n" "$method" "$url" "$code"
}

echo "=== OpenAI / Codex 端点 ==="
probe GET  "https://api.openai.com/v1/models"
probe GET  "https://chatgpt.com/backend-api/me"
probe POST "https://chatgpt.com/backend-api/codex/responses"
probe POST "https://chatgpt.com/backend-api/codex/models"
echo

# --- 5. 判读 ---
echo "=== 判读 ==="
echo "  401 / 405  => 端点存在、未被封锁，链路正常，可继续抽测"
echo "  403        => 地区封锁，属网络问题，不是模型降级"
echo "  超时/000   => 线路阻断，属网络问题，不是模型降级"
