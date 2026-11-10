# codex-model-degradation-check

把「感觉 ChatGPT / Codex 变笨了」变成一张可以摆出来看的数字表。

一个给 AI Agent 用的技能（Skill），配合命令行脚本使用，也能人肉跑。

## 解决什么问题

语言模型的质量投诉里，绝大部分其实是三件完全不同的事被混成了一件：

| 真实情况 | 用户感受 | 该做什么 |
|---|---|---|
| **模型定位差异** | 换了 Codex 模式，话变少了，「变笨了」 | 什么都不用做 |
| **正常采样波动** | 这次回答短了点 | 观察即可 |
| **真实降级** | 持续变短、结构丢失、出现限流 | 才需要采取行动 |

不做区分就动手，结果一定是重装客户端、换账号、重置设置——三招全无效，纯浪费时间。

这个技能用「同任务三次抽样 + 网络出口核查」把三类情况切开，每一步都有可核对的数字。

## 为什么不用「问它一句看它聪不聪明」

因为单次回答的长度和质量本身就是随机变量。一次回答短，可能只是采样运气。

**能说明问题的最小单位是一组三次抽样，不是一次。** 这是整个技能的立足点。

## 安装

```bash
git clone https://github.com/<你的用户名>/codex-model-degradation-check.git \
  ~/.workbuddy/skills/codex-model-degradation-check
chmod +x ~/.workbuddy/skills/codex-model-degradation-check/scripts/*.sh \
         ~/.workbuddy/skills/codex-model-degradation-check/scripts/*.py
```

装完对 Agent 说「ChatGPT 好像变笨了」，技能会自动触发。

## 用法（三步）

### 1. 网络与地区核查

```bash
bash scripts/network_check.sh
```

自动探测系统代理端口，输出：走代理的出口 IP 与地区、当前直连出口、OpenAI / Codex 四个端点的状态码。

端点返回 `401` / `405` 说明链路通、未被封锁；返回 `403` 或超时说明是网络问题，**这时候不要谈模型降级**。

### 2. 生成抽样包

```bash
python3 scripts/make_probe_pack.py --out ~/probe-$(date +%m%d)
```

生成三条完全相同的任务 prompt 和三个回填模板。把 prompt 粘进客户端，把完整回答粘回 `responses/r1.md` ~ `r3.md`。

用 API 的话更省事：

```bash
export OPENAI_API_KEY=sk-...
python3 scripts/probe_api.py --out ~/probe-$(date +%m%d) --model gpt-5
```

**纪律：三次必须同模式、同账号、同节点。中途切模式或换节点，整组数据作废。**

### 3. 出对比表

```bash
python3 scripts/analyze.py --dir ~/probe-$(date +%m%d)
```

```
轮次         字符数     行数     代码块    分点    标题     表格行
------------------------------------------------------------------
r1         1284      62       2     14     0       0
r2         1196      58       2     13     0       0
r3          412      21       0      4     0       0

判读  : 真实降级 · 疑似递降
依据  : 末轮比首轮短 67%，且三轮持续走低
建议  : 同一任务三次递减，优先怀疑被 A/B 分到弱模型或被动态降级。换时段重测确认
```

## 判读口径

| 指标 | 阈值 | 结论 |
|---|---|---|
| 轮间波动率 `(max-min)/mean` | < 15% | 稳定 |
| 同上 | 15% – 35% | 正常采样波动 |
| 同上 | > 35% | 疑似降级，延长到 5 轮确认 |
| 末轮 / 首轮，且三轮单调走低 | < 60% | 疑似递降 |
| 平均字符数 | < 200 | 先排除执行型模式，再判定 |
| 分点数 / 代码块 / 标题数同步下降 | —— | 降级的强信号 |

结构要素比长度更可靠：长度受话题影响，但「该分点的地方不分点、该给代码的地方只给描述」是能力变化，不是风格变化。

完整阈值推导与例外情况见 [`references/interpretation.md`](references/interpretation.md)。

## 目录结构

```
codex-model-degradation-check/
├── SKILL.md                      # 技能主文件，Agent 读取的执行流程
├── README.md
├── scripts/
│   ├── network_check.sh          # 出口 IP / 地区 / 端点状态码核查
│   ├── make_probe_pack.py        # 生成三次同任务抽样包
│   ├── probe_api.py              # 可选，有 API key 时自动跑三次
│   └── analyze.py                # 指标统计与判读
└── references/
    └── interpretation.md         # 判读阈值、例外情况、误判纠正
```

## 设计和它刻意的边界

**它只测「能不能稳定地产出结构化结果」，不测「答案对不对」。**

答案正确性需要人工判断，脚本不碰。这里的指标都是可计算的代理信号：长度、结构、限流提示。这些信号能可靠地区分「模型能力掉了」和「这次手气不好」，但它们不等于答案质量评估。

**它也不做跨模型、跨模式比较。** 拿聊天模式和 Codex 模式比长度，比出来的是产品分工，不是降级。技能里明确禁止这种比较。

## 配套技能

| 现象 | 用哪个 |
|---|---|
| 打不开、转圈、卡加载页、报 403 | `proxy-openai-diagnosis` |
| 能正常用，但觉得回答质量下降 | 本技能 |

两者不重叠：先确认能连上，再谈质量。

## License

MIT
