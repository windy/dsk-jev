# dsk-jev

Go 实现的 Jev HTTP 协议兼容服务，以 DeepSeek V4.1 Flash 非推理模式为后端。
客户端使用 Jev 的请求及返回结构，无须添加 mode 或更换题型。
额外支持图片输入：通过可选 `images` 字段传入图片，用相同的 Choice / Score / Noul 题型做视觉判断。图片是本项目扩展，原生 Jev 不支持该字段。

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

## 图片输入

在原有请求上添加 `images`，每张图包含 `url` 和可选 `detail`：

```json
{
  "model": "jev-latest",
  "state": "根据图片回答问题。",
  "images": [
    {"url": "https://your-host.example/photo.png", "detail": "low"}
  ],
  "questions": {
    "has_damage": {"type": "noul", "instructions": "商品是否有可见的破损？"}
  }
}
```

示例中的外链是占位符，需要换成真实的公开图片地址。`url` 也接受 `data:image/png;base64,...`，支持 PNG、JPEG、GIF、WebP。仓库提供无需上传图片的完整 Base64 示例，可以直接运行：

```sh
curl http://127.0.0.1:8080/v1/systemone \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/vision.json
```

- `state` 仍然必填，可以用空字符串；没有 `images` 时保持原有文本处理，包括对象和数组，不自动把其中的 URL 解释为图片。
- 图片按数组顺序送入同一条 user 消息，可在题目中引用“第一张图片”“第二张图片”。图像中文字视为证据，不作为系统指令。
- `detail` 支持 `auto`（省略时由上游决定）、`low`、`high`、`original`。先用 `low` 测试简单视觉判断；需要读取小字或细节时使用 `original`，并实测效果与用量。
- 本代理最多接收 **8 张图**；整个 JSON 请求不超过 **4 MiB**，单张内联图解码后不超过 **2 MiB**。多张图片的 Base64 总量仍受请求体限制。超限或非法图片字段返回 422。
- 内联图片校验 Base64、大小及文件头与 MIME 的一致性；完整图像解码由上游完成。公开 URL 由 DeepSeek 下载，本服务不下载、代理或存储图片；外链图片的可访问性、格式、大小限制由上游检查。外链必须是 HTTP(S)，最多 8192 字节，不接受用户密码或 URL fragment。
- 继续关闭 thinking，支持 strict 工具调用、标准/精简输出和局部重试。每次重试都会携带原图，相关 token 已包含在累计 usage 中，图片 tokens 不额外重复加算；流水增加 `image_count`，不记录 URL 或 Base64。
- 该扩展通过 HTTP JSON 调用；原生 TypeSafe SDK 不一定允许传入额外字段。已有纯文本 SDK 调用保持兼容。当前未接入 Files API、图片上传存储或本地图片路径。

可选的真实视觉冒烟测试（产生 DeepSeek API 费用，不需要 Jev key）：

```sh
go build -o bin/dsk-jev ./cmd/server
# 在环境中设置 DEEPSEEK_API_KEY
VISION_EVAL_PREFIX=vision-check-new python3 scripts/vision_smoke.py
```

测试使用两张确定性的颜色交换图，分别检查圆形颜色、方形数量、总图形数及双图差异，覆盖 standard/fast 两种输出模式。结果保存到 `reports/<VISION_EVAL_PREFIX>/`，前缀必须未使用。它只验证视觉链路，不代表真实业务视觉准确率或领先其他模型。使用 `python3 scripts/vision_smoke.py --fixtures-only` 可重新生成示例，不调用 API。

图片上游格式见 [DeepSeek Vision 文档](https://api-docs.deepseek.com/guides/vision/)。

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
- `usage.input_tokens/output_tokens` 累计该请求所有尝试的实际 DeepSeek 用量（包括被拒绝的输出），而非模拟 Jev 的 token 数。

实现保留完整概率输出。模型生成按问题 ID、选项 ID 对应的概率对象，Go 恢复客户端 ID、选项名称、
等级说明并计算加权分数。客户端问题 ID 映射成 q0/q1 等内部 ID；固定规则放在 system、问题定义放在工具 Schema，动态 state 在 user 消息。
Choice 选项排序稳定，平局按排序后的首个选项处理。

置信度公式参考 TypeSafe 官方开源适配器：Choice 将最高概率从均匀分布基线线性缩放；
Score 根据概率到众数等级的平均距离计算。它们描述分布集中程度，不是经过校准的准确率。
DeepSeek 生成的概率尚未通过独立校准，接口兼容不代表与 Jev 的预测、校准或延迟等价。

## 错误和边界

- 401：客户端鉴权失败；422：请求验证失败。
- 上游 429 → 429；503/529 → 529，保留 Retry-After。
- 上游鉴权失败、其他非成功状态、非法概率或截断 → 502；请求超时 → 504。
- 不向客户端透传上游错误正文或密钥；不记录输入内容。校验失败日志记录具体原因；成功及校验失败的已解析上游响应均记录 token 用量。
- 默认最多 3 次重试（首次＋重试最多 4 次），`MAX_RETRIES=0` 可禁用。仅重试临时错误/格式校验失败；不会因某个语义答案与预期不符而重试。SDK 也可能重试，调用方需避免叠加放大请求数。
- 概率须落在 [0,1]，总和只容忍 0.02 的舍入误差并归一化；不把非法数据补成确定答案。
- 请求体上限 4 MiB，估算输出预算上限 32768 tokens，超出返回 422。
  这些是本实现的资源限制，不等同于 Jev 原生 token 限制。
- 每次尝试调用一次 DeepSeek；部分题目有效时只补算失败题目。概率仍然顺序生成，不具备 Jev 原生并行模型特性。
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
本评测包含真实 API 费用；当前默认启用最多 3 次服务端重试，结果含尝试次数及累计用量。

使用相同固定用例评测官方 Jev：

```sh
export JEV_API_KEY='your-typesafe-key'
python3 scripts/jev_eval.py
```

写入 `reports/jev-results.json` 和 `reports/jev-summary.json`，不覆盖 DeepSeek 数据。
首轮同集对比见 [Jev 对比报告](reports/jev-comparison.md)。

### v2 历史优化评测

外部 Jev 协议不变。内部概率通过显式问题/选项键绑定，使用 DeepSeek beta 的 strict 工具调用，Schema 声明所有字段必填、禁止额外字段、概率数字范围为 [0,1]。Go 继续检查键、概率范围和总和，拒绝不合法响应。
v2 历史报告使用单次请求、不重试及原有概率校验。结构约束并不保证语义正确或概率校准。
参考：https://api-docs.deepseek.com/guides/tool_calls/#strict-mode-beta

```sh
MAX_RETRIES=0 PROMPT_MODE=standard EVAL_PREFIX=v2-recheck python3 scripts/live_eval.py
MAX_RETRIES=0 PROMPT_MODE=standard EVAL_PREFIX=v2-holdout-recheck EVAL_CASES=evals/holdout.json python3 scripts/live_eval.py
```

前者复用原始 44 个请求，后者使用优化后首次评测前固定的 12 个新请求。
报告包含 `upstream_usage_all_parsed_responses`，涵盖能解析的上游成功响应，即使决策校验失败。
网络中断或非 JSON 错误仍可能无法取得实际用量。留出集仍为手工合成，不能替代真实业务评测。

本次优化的完整结果和限制见 [v2 评测报告](reports/v2-evaluation.md)。

### v3 重试与开销优化

- `MAX_RETRIES=3`（默认）：首次加最多三次重试，范围 0–10。
- `UPSTREAM_TIMEOUT=30s`：整个逻辑请求的总预算，包括全部尝试和退避；预算耗尽可以早于第 4 次返回 504。
- `PROMPT_MODE=standard`（默认）：保留 v2 提示词。`compact` 为实验性精简版本；当前整轮成本更高，因此没有设为默认。
- 对 408、429、5xx、网络错误、截断/格式/概率校验失败重试。400、401、403、422 等永久错误不重试。
- 指数退避从 100ms 开始并加随机抖动；尊重 Retry-After 秒数或 HTTP 日期；客户端取消立即停止。
- 多问题批次保留已通过校验的答案，只重试失败问题。不会把缺失概率填成 0，也不会放宽概率总和校验。
- 外部 Jev JSON 结构不变；额外响应头 `X-Upstream-Attempts`、`X-Upstream-Input-Tokens`、`X-Upstream-Output-Tokens`、`X-Upstream-Cached-Tokens` 提供诊断，包括失败请求。
- 每次尝试记录耗时、题数、原因、token 用量及 `usage_known`。网络中断等拿不到用量的调用不能据此确认实际费用为零。
- 没有增加结果缓存；每个请求均实际调用上游，缓存数字仍指 DeepSeek 自动前缀缓存。

```sh
MAX_RETRIES=3 PROMPT_MODE=standard EVAL_PREFIX=v3-standard python3 scripts/live_eval.py
MAX_RETRIES=3 PROMPT_MODE=compact EVAL_PREFIX=v3-compact python3 scripts/live_eval.py
MAX_RETRIES=3 PROMPT_MODE=compact EVAL_PREFIX=v3-holdout EVAL_CASES=evals/holdout.json python3 scripts/live_eval.py
```

运行这些命令会覆盖对应报告。固定用例已被多轮测试，留出集是历史留出集，不能当作独立盲测。

同模板连续复用测试（28 次真实请求，不使用本地结果缓存）：

```sh
DSK_JEV_BINARY="$PWD/bin/dsk-jev" python3 scripts/cache_reuse_eval.py
python3 scripts/report_v3.py
```

模型＋system＋Schema 的稳定指纹可在 `X-Upstream-Template` 和日志中查看。
结构化描述已规范化，避免空白或对象键顺序变化破坏固定前缀。
完整结果见 [v3 重试与缓存报告](reports/v3-evaluation.md)。

## 用量流水与公平对比

设置 `USAGE_LEDGER_PATH` 开启逐次上游调用 JSONL 流水（新文件权限 0600）；每条包含内部 `request_id`、实际模型、模板指纹、UTC 时间、尝试序号、延迟、状态和原始 usage，不记录请求正文或密钥。响应的 `X-Request-ID` 可关联所有重试。流水写入失败会记录错误日志，当前不会阻断业务响应；这是观测用途，尚非具备事务持久性与对账保证的收费账本。

Jev 返回 `usage.input_tokens/output_tokens`；DeepSeek 返回 `prompt_tokens/completion_tokens` 和缓存命中字段。两者均不是实际扣款金额。`config/pricing.json` 保存带日期的美元公开报价，`scripts/accounting.py` 用十进制计算估算费用。DeepSeek 输入总量已包含缓存输入，计费时只计算一次；输出包含其中的 reasoning tokens，不额外累加。缺失/矛盾的缓存数或用量视为未知，总费用返回 null 并单列已知费用。失败、无效输出及重试全部进入用量流水。余额、赠金、税费、合约折扣和中转服务器费用不在估算内。

用同一份固定回归集交替测试两家（默认 44 请求/140 判断，每家最多 3 次重试，30 秒上游预算，持久连接、并发 1）：

```sh
go build -o bin/dsk-jev ./cmd/server
# 在环境中设置 DEEPSEEK_API_KEY 和 JEV_API_KEY 后运行；仅依赖 Python 标准库。
EVAL_PREFIX=comparison-new python3 scripts/compare_eval.py
```

每次选择新的 `EVAL_PREFIX`，防止旧流水混入新统计。产物包括两家逐次用量 JSONL、逐请求答案/耗时、JSON 汇总及 Markdown 对比。包含成功率、正确判断/全部预期判断、所有请求及成功请求 P50/P95、重试数、缓存比例、峰/谷估算美元、每千请求及每千正确判断成本，并按测试组细分。缓存未清空，不应把结果解释为冷启动；该数据集曾用于优化，不属于独立盲测。此运行方式不测满负载吞吐量。

```sh
go test -race ./...
python3 -m unittest discover -s scripts -p 'test_accounting.py'
```

## 提速实验与网络计时

默认仍为 `OUTPUT_MODE=standard`。设置 `OUTPUT_MODE=fast` 启用实验性的内部输出格式：Choice/Score 使用整数千分数；少于 16 项按固定顺序输出权重数组，16 项及以上输出所有非零项的 `[编号, 权重]` 数组，Go 补齐零项；Noul 保留原始 0～1 小数，再沿用现有的 choice/score/confidence 计算。此模式使用更短提示词，覆盖 `PROMPT_MODE` 的提示词选择。外部响应结构不变，但概率精度及模型输出行为会改变，不能把分类正确率等同于概率校准质量。没有 top-k 截断，也不以 one-hot 分布代替模型概率。非法编号、重复项、空分布、非法数值或不合法总和均会触发既有的局部重试。

两个模式都发送 `thinking: {"type":"disabled"}`，共享进程内 HTTP 客户端，并完整读取正常响应体后复用连接。每个服务器使用独立的 Transport，空闲连接池总计 128、每主机 64（用于并发连接保留，不会让单次推理加快）。用量流水新增 `network.connection_reused`、获取连接时间、首响应字节时间及首字节后时间。非流式首字节可能是服务端保活数据，因此这些数值不是模型首 token 延迟，也无法直接分离排队、预填充、解码与网络传输时间。

```sh
# 已设置 DEEPSEEK_API_KEY，并重新构建 bin/dsk-jev 后：
EVAL_PREFIX=speed-new python3 scripts/speed_eval.py
```

该脚本在相同时间段交替测试 standard/fast，使用持久连接，包含 44 请求回归集与 12 请求历史 holdout，逐次保存成本、耗时、缓存和连接复用证据。首次连接与模板缓存状态也保留在统计中，未声称是严格冷缓存对比。
