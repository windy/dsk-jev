"""Summarize recorded runs only; no network or paid requests."""
import json,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'reports'
source='https://api-docs.deepseek.com/quick_start/pricing/'
summaries={}
for name in ['v2-strict','v3-standard','v3-compact','v3-holdout']:
 s=json.loads((root/f'{name}-summary.json').read_text());u=s['upstream_usage_all_parsed_responses']
 cost=((u['input_tokens']-u['cached_tokens'])*.3+u['cached_tokens']*.006+u['output_tokens']*1.2)/1e6
 summaries[name]={'requests':s['requests'],'success':s['successful_requests'],'correct':s['correct_judgments'],'judgments':s['judgments'],'attempts':s.get('total_upstream_attempts',s['requests']),'latency_ms':s['latency_ms'],'tokens':u,'estimated_peak_usd':cost,'estimated_off_peak_usd':cost/2}
rows=json.loads((root/'cache-reuse-results.json').read_text());phases={}
for phase in dict.fromkeys(x['phase'] for x in rows):
 allrows=[x for x in rows if x['phase']==phase];steady=allrows[1:] if phase.endswith('continuous') else allrows
 assert len({x['template'] for x in allrows})==1
 u={k:sum(x['response']['usage'][k] for x in steady) for k in ['input_tokens','output_tokens']};cached=sum(x['cached_tokens'] for x in steady)
 cost=sum(x['estimated_peak_usd'] for x in steady);nocache=(u['input_tokens']*.3+u['output_tokens']*1.2)/1e6
 phases[phase]={'requests':len(allrows),'steady_sample_size':len(steady),'template':allrows[0]['template'],'steady_input_hit_ratio':cached/u['input_tokens'],'steady_mean_peak_usd':cost/len(steady),'steady_p50_ms':statistics.median(x['latency_ms'] for x in steady),'saved_vs_same_tokens_all_uncached':1-cost/nocache,'output_cost_share':u['output_tokens']*1.2/1e6/cost}
assert phases['standard-continuous']['template']==phases['standard-revisit']['template']
report={'pricing_source':source,'pricing_checked':'2026-09-22','cost_note':'Token-based estimate, not account invoice. Peak and off-peak rates shown separately; excludes hosting/network. All v3 runs reported known usage for every attempt.','runs':summaries,'continuous_cache':phases}
(root/'v3-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
text='''# v3：三次重试、成本与连续前缀复用

默认最多 3 次重试（首次加重试最多 4 次），受整个请求 30 秒预算限制。临时网络错误、408/429/5xx、格式失败可重试；永久错误不重试。成功题目保留，只补算失败题目。指数退避＋抖动，尊重 Retry-After，可取消。JSON 用量累计全部尝试。没有增加本地结果缓存。

## 同集结果

| 版本 | 成功请求 | 符合预期判断/全部计划判断 | 上游调用数 | P50/P95 ms | 高峰估算美元 |
|---|---:|---:|---:|---:|---:|
'''
for name,s in summaries.items():text+=f"| {name} | {s['success']}/{s['requests']} | {s['correct']}/{s['judgments']} | {s['attempts']} | {s['latency_ms']['p50']}/{s['latency_ms']['p95']} | {s['estimated_peak_usd']:.8f} |\n"
text+='''
默认保留 standard：compact 在这个混合集虽然 140/140 符合预期，但 255 选项案例触发重试，耗时 11.52 秒，导致整轮成本显著更高。standard 的唯一重试为 1 道题，不是重复执行整个数据集。不能因为某一轮达到 100% 就宣称通用准确率 100%。

各轮非同时运行、缓存状态不同；v3-standard 相对历史 v2 的成本降低不能全部归因于代码优化，缓存命中变化贡献很大。高峰单价：未缓存输入 $0.30/M、缓存输入 $0.006/M、输出 $1.20/M；低峰为一半。费用是用量估算，非账单。来源：'''+source+'''

## 连续复用实验

新的固定订单模板，连续改变订单号、商品、付款状态及发货要求。12 次 standard → 12 次 compact → 返回 standard 再执行 4 次，复用同一 Go 服务中的 HTTP 客户端。没有主动制造冷缓存、没有随机前缀，也没有额外填充 token。每个阶段输入数据均不同；28 次请求成功，84/84 判断符合预期，全部一次完成。

| 阶段 | 首次命中 | 后续连续命中 | 稳态输入命中率 | 稳态 P50 ms | 稳态每请求高峰估算美元 |
|---|---:|---:|---:|---:|---:|
'''
for phase,s in phases.items():
 rr=[x for x in rows if x['phase']==phase]
 text+=f"| {phase} | {rr[0]['cached_tokens']} | {rr[-1]['cached_tokens']} | {s['steady_input_hit_ratio']:.1%} | {s['steady_p50_ms']:.2f} | {s['steady_mean_peak_usd']:.8f} |\n"
text+='''
standard 阶段第 2–12 次连续命中 768 tokens，每次输入约 968 tokens；切换 compact 后回到 standard 的 4 次也持续命中 768。compact 第 2–12 次持续命中 640/约 803 tokens。第一请求已经部分命中，不能将它当作纯冷启动。

standard 稳态按相同 token 用量全未缓存的价格反事实估算，总 token 费用降低约 56.5%，而输出已经占约 62.7% 的费用。compact 在这一个固定小模板上更便宜、更快，但混合集的大选项退化说明需要按真实业务模板评估，不能全局替换。

## 缓存设计与边界

- 固定 model、system 和工具 Schema；变化数据仅放在 user state，不把时间、请求 ID 或历史答案插到固定部分。
- 问题/选项稳定排序，JSON 描述规范化，消除调用方空白及对象键顺序造成的无意义前缀变化。
- 对 model＋system＋Schema 计算稳定模板指纹，返回 X-Upstream-Template，并在每次尝试日志记录。指纹是诊断标识，不是可指定的 DeepSeek 缓存句柄。
- HTTP 连接复用与模型 KV 前缀复用是两层不同机制。服务保持无状态，不通过无限累积对话维持命中。
- DeepSeek 根据实际共同前缀自动持久化缓存，构建需要时间且为 best effort。不能保证每个相同模板都立刻满命中。见 https://api-docs.deepseek.com/guides/kv_cache/ 。
- 部分题目重试会形成子 Schema，可能降低该次缓存复用；收益是减少重复输出。日志逐次记录模板和用量，可继续比较全批重试与子集重试。
- 没有加入按模板排队或主动预热；这些可能增加首次延迟或额外调用，应在真实稳定负载下再评估。

## 验证

竞态测试、go vet、官方 SDK 模拟联调通过。测试覆盖首三次失败后第四次成功、耗尽次数、永久/临时错误分流、Retry-After、取消/总预算、仅重试失败题、累计用量、稳定模板序列化。

原始记录：v3-standard-results.json、v3-compact-results.json、v3-holdout-results.json、cache-reuse-results.json。合成集及历史留出集均被重复使用，不能作为独立盲测或生产 SLA。
'''
(root/'v3-evaluation.md').write_text(text)
print(json.dumps(report,ensure_ascii=False,indent=2))
