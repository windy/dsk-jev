# dsk-jev

Go 实现的 Jev HTTP 协议兼容服务，以 DeepSeek V4.1 Flash 非推理模式为后端。
客户端使用 Jev 的请求及返回结构，无须添加 mode 或更换题型。

## 启动

需要 Go 1.26.1。无第三方 Go 依赖。

```sh
export PROXY_API_KEY='your-local-client-key'
export DEEPSEEK_API_KEY='your-deepseek-key'
go run ./cmd/server
```

其他配置见 `.env.example`（不会自动读取 .env）。默认仅监听 `127.0.0.1:8080`。

```sh
curl http://127.0.0.1:8080/v1/systemone \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/ticket.json
```

可接现有 llm_proxy：设置 `DEEPSEEK_BASE_URL` 为其 OpenAI 兼容 API 根地址，
`DEEPSEEK_API_KEY` 为该代理的访问密钥，`DEEPSEEK_MODEL=dsk-deepseek-flash`。
根地址会追加 `/chat/completions`。直连默认 `https://api.deepseek.com/beta`，启用严格工具调用。
自有网关必须转发 `tools[].function.strict` 和 `tool_choice`，并将请求路由到 DeepSeek beta 端点；普通 chat 转发路径未必支持，需先验证。

## 协议

- `POST /v1/systemone`：必填 `model`、`state`、`questions`。
- `GET /v1/models`：返回 `models` 列表。
- `GET /healthz`：进程健康检查，无需鉴权，不检测上游。
- 支持 `jev-latest`、`jev-preview`、`jev-1.13.0` 兼容别名。
- 响应 `model` 为兼容版本 `jev-1.13.0`；这是协议别名，不代表执行了 Jev 权重。
  响应头 `X-Upstream-Model` 提供实际配置的上游模型。
- Choice：1–255 个选项，返回 choice / probabilities / confidence。
- Score：2–10 个等级，返回 score / probabilities / confidence / legend；从 0 编号。
- Noul：返回 noul 概率，不添加 confidence。
- 支持字符串、对象、数组形式的 instructions / 描述；Choice 描述可为 null。
- `usage.input_tokens/output_tokens` 为实际 DeepSeek 用量，而非模拟 Jev 的 token 数。

实现保留完整概率输出。模型生成按问题 ID、选项 ID 对应的概率对象，Go 恢复客户端 ID、选项名称、
等级说明并计算加权分数。客户端问题 ID 映射成 q0/q1 等内部 ID；固定问题定义位于 system 前缀，动态 state 在 user 消息。
Choice 选项排序稳定，平局按排序后的首个选项处理。

置信度公式参考 TypeSafe 官方开源适配器：Choice 将最高概率从均匀分布基线线性缩放；
Score 根据概率到众数等级的平均距离计算。它们描述分布集中程度，不是经过校准的准确率。
DeepSeek 生成的概率尚未通过独立校准，接口兼容不代表与 Jev 的预测、校准或延迟等价。

## 错误和边界

- 401：客户端鉴权失败；422：请求验证失败。
- 上游 429 → 429；503/529 → 529，保留 Retry-After。
- 上游鉴权失败、其他非成功状态、非法概率或截断 → 502；请求超时 → 504。
- 不向客户端透传上游错误正文或密钥；不记录输入内容。校验失败日志记录具体原因；成功及校验失败的已解析上游响应均记录 token 用量。
- 不自动重试，避免隐藏费用。SDK 可能自行重试，应按应用需要配置。
- 概率须落在 [0,1]，总和只容忍 0.02 的舍入误差并归一化；不把非法数据补成确定答案。
- 请求体上限 4 MiB，估算输出预算上限 32768 tokens，超出返回 422。
  这些是本实现的资源限制，不等同于 Jev 原生 token 限制。
- 一个批次调用一次 DeepSeek；概率仍然顺序生成，不具备 Jev 原生并行模型特性。
- 当前未实现多租户、计费存储和网关限流。

## 验证

```sh
go test -race ./...
go vet ./...
go build -o bin/dsk-jev ./cmd/server
```

测试包含模拟上游的完整请求链路、非推理参数、三个题型、非法输入/概率、限流、截断、超时和鉴权。
真实成本与延迟需配置上游密钥后测量，未宣称比 Jev 更快或更便宜。

## 参考

- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/confidence
- https://github.com/typesafe-ai/system-one-adapter-python
- https://api-docs.deepseek.com/guides/thinking_mode/

本项目非 TypeSafe 官方服务。置信度算法所参考代码的 MIT 许可见 THIRD_PARTY_NOTICES。

### 官方 Python SDK

已用 `typesafe-sdk==0.7.1` 完成真实 SDK → Go 服务 → 模拟上游的联调。

```python
from typesafe_sdk import TypeSafeClient, Noul

with TypeSafeClient(
    api_key="your-local-client-key",
    base_url="http://127.0.0.1:8080",
    model="jev-latest",
) as client:
    result = client.system_one(
        state="请今天处理重复扣款",
        questions={"urgent": Noul(instructions="用户是否提出明确期限？")},
    )
    print(result.nouls["urgent"].noul)
```

可重复执行 SDK 联调（启动并清理本地模拟上游和 Go 进程，不产生 API 费用）：

```sh
python3 -m venv .venv
.venv/bin/pip install typesafe-sdk==0.7.1
go build -o bin/dsk-jev ./cmd/server
.venv/bin/python scripts/sdk_smoke.py
```

### 真实模型评测

`evals/cases.json` 包含 44 次请求 / 140 个预先标注的判断。
包含中文和英文语义、否定、引用、提示注入、结构化描述、null 选项说明、1/32/255 个选项、
10 个等级、长文本、1/5/10/20 问批次，以及相同请求重复调用。

```sh
export DEEPSEEK_API_KEY='your-key'
python3 scripts/live_eval.py
```

输出到 `reports/live-results.json` 和 `reports/live-summary.json`，会覆盖上次结果。
必要时通过 `DSK_JEV_BINARY` 指定已构建的可执行文件。
首轮结果及失败明细见 [评测报告](reports/live-evaluation.md)。
本评测包含真实 API 费用；没有自动重试。

使用相同固定用例评测官方 Jev：

```sh
export JEV_API_KEY='your-typesafe-key'
python3 scripts/jev_eval.py
```

写入 `reports/jev-results.json` 和 `reports/jev-summary.json`，不覆盖 DeepSeek 数据。
首轮同集对比见 [Jev 对比报告](reports/jev-comparison.md)。

### v2 优化评测

外部 Jev 协议不变。内部概率通过显式问题/选项键绑定，使用 DeepSeek beta 的 strict 工具调用，Schema 声明所有字段必填、禁止额外字段、概率数字范围为 [0,1]。Go 继续检查键、概率范围和总和，拒绝不合法响应。
保持单次请求、不重试以及原有概率校验，不靠放宽校验提高成功率。结构约束并不保证语义正确或概率校准。
参考：https://api-docs.deepseek.com/guides/tool_calls/#strict-mode-beta

```sh
EVAL_PREFIX=v2-strict python3 scripts/live_eval.py
EVAL_PREFIX=v2-strict-holdout EVAL_CASES=evals/holdout.json python3 scripts/live_eval.py
```

前者复用原始 44 个请求，后者使用优化后首次评测前固定的 12 个新请求。
报告包含 `upstream_usage_all_parsed_responses`，涵盖能解析的上游成功响应，即使决策校验失败。
网络中断或非 JSON 错误仍可能无法取得实际用量。留出集仍为手工合成，不能替代真实业务评测。

本次优化的完整结果和限制见 [v2 评测报告](reports/v2-evaluation.md)。
