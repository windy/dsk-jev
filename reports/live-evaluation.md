# DeepSeek 非推理代理基线评测

日期：2026-09-22。实现和提示词在评测期间未修改。

## 自动化验证

11 个 Go 测试函数、19 个命名子测试全部通过；另有函数内表驱动断言。核心 decision 包语句覆盖率 90.7%，全项目 80.6%。竞态检测、go vet 和官方 Python SDK 模拟联调通过。

## 结果

- 44 次真实代理请求，140 个预先标注的判断。另发 1 次直接上游诊断请求，未混入评测统计。
- HTTP 200：30/44（68.2%）；502：14/44（31.8%）。
- 成功响应内：86/100 个判断符合预期（86%）。
- 包含失败请求的有效正确判断：86/140（61.4%）。
- Choice 16/23；Score 19/20；Noul 51/57。
- 成功请求 P50 694.10 ms，P95 1109.87 ms；排除了失败请求，不能表示全部请求的服务水平。
- 成功请求输入 13256 tokens，输出 882 tokens，其中缓存命中 2816 输入 tokens。
- 当前失败路径未保留 token 用量，因此不能据此报告完整调用成本。

## 方法与限制

Hand-authored synthetic set; choice exact match, noul >=0.5, score rounded to nearest level. Semantic/boundary concurrency 3; repeats/batch sequential. No retries; no Jev comparison.

合成样本小，预期结果为人工编写，尚无独立标注和统计置信区间。分数按最近等级评分，不代表概率已校准。并发模式混合，不是负载压测，也没有测量 Jev。批量题较简单，因此总体 86% 不能直接代表真实客服业务准确率。

## 失败案例

| 请求 | HTTP | 不符合预期的判断 |
|---|---:|---|
| double_charge | 200 | refund: 预期 False，实际 True |
| refund_yes | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| invoice | 200 | department: 预期 billing，实际 technical |
| outage | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| bug | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| demo | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| sales_deadline | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| thanks | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| quoted | 200 | department: 预期 sales，实际 other |
| conditional | 200 | department: 预期 billing，实际 sales |
| retracted | 200 | department: 预期 billing，实际 other |
| polite | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| no_urgency | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| urgent_refund | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| question_refund | 200 | department: 预期 billing，实际 technical；urgency: 预期 0，实际 1 |
| policy | 200 | department: 预期 billing，实际 sales |
| english | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| negated_deadline | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| injection | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| original_refund_regression | 200 | explicit_refund: 预期 False，实际 True |
| choice_null | 200 | x: 预期 猫，实际 狗 |
| object_state | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| choice_255 | 502 | {"error":{"message":"upstream returned invalid decision probabilities"}}
 |
| repeat_1 | 200 | explicit_refund: 预期 False，实际 True |
| repeat_2 | 200 | explicit_refund: 预期 False，实际 True |
| repeat_4 | 200 | explicit_refund: 预期 False，实际 True |
| repeat_5 | 200 | explicit_refund: 预期 False，实际 True |

## 批量与重复

| 请求 | 耗时 ms | 正确判断 |
|---|---:|---:|
| batch_1 | 581.08 | 1/1 |
| batch_5 | 637.88 | 5/5 |
| batch_10 | 620.47 | 10/10 |
| batch_20 | 927.09 | 20/20 |
| repeat_1 | 864.79 | 2/3 |
| repeat_2 | 572.36 | 2/3 |
| repeat_3 | 915.89 | 3/3 |
| repeat_4 | 876.95 | 2/3 |
| repeat_5 | 783.05 | 2/3 |

## 后续优先级

1. 定位模型概率数组的长度/总和错误，确保完整字段输出；保留失败调用用量。
2. 检查选项与概率的位置绑定，尤其是中文/null 描述以及较多选项。
3. 修正明确退款、否定、引用的语义判断；使用独立留出集验证，不能只改到当前样本通过。
4. 正确性达标后，再分别测冷缓存、热缓存和相同并发下的延迟与完整成本。

详细响应见 live-results.json，原始案例见 ../evals/cases.json。

14 次 502 均为上游决策概率校验失败，不是鉴权、限流或连接超时。现有错误信息未区分数组长度和概率总和等子原因，需要补充诊断后定位。
