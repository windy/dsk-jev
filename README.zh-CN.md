# dsk-jev

**用 Go 和 DeepSeek 实现 Jev 兼容的决策 API，并扩展图片输入。**

[English](README.md) · [完整指南](docs/guide.zh-CN.md) · [评测](docs/benchmarks.md) · [下载](https://github.com/windy/dsk-jev/releases)

输入文本、结构化状态或图片，输出 Choice、Score、Noul。单个 Go 二进制，无第三方 Go 模块依赖，支持局部重试、缓存观测和逐次用量记录。

本项目是实验性、非官方实现，不运行 Jev 权重。协议兼容不代表预测、置信度校准、速度或成本等价。图片是本项目的扩展；当前推理子集评测落后于 Jev，不宣称比 Jev 更快、更便宜或更准。

## Benchmark：Jev 与 dsk-jev 对比

2026-09-22 实测：每家 **44 个请求 / 140 个判断**，同机、同一时间段交替调用，复用连接，并发 1。dsk-jev 使用默认 standard 模式，关闭 thinking。两家最多允许 3 次重试，本轮均未触发。

| 指标 | Jev | dsk-jev / DeepSeek |
|---|---:|---:|
| 请求成功率 | 44/44（100%） | 44/44（100%） |
| 判断正确率 | 139/140（99.29%） | 138/140（98.57%） |
| 端到端 P50 | **318 ms** | 909 ms |
| 端到端 P95 | **374 ms** | 1,231 ms |
| 每千请求估算费用（美元） | **$0.0313** | 高峰 $0.2199 / 低峰 $0.1100 |
| 输入缓存命中比例 | 未返回 | 87.1% |

**这轮文本测试中，Jev 更快、更便宜。** 数据集为开发中已使用过的小型合成回归集，不是独立盲测；没有清空提供商缓存。费用采用带日期的公开报价估算，不是实际扣款，不含服务器、税费和赠金影响。正确率不代表置信度已经校准。

**图片能力单独验证：** dsk-jev 在 6 次真实图片请求中完成 14/14 正确判断，耗时 0.66～0.96 秒。Jev 原生不接收图片，因此这不是双方的图片准确率对比，也不代表我们在复杂视觉或推理任务上已经领先。

[原始对比数据](reports/comparison-v4-summary.json) · [图片测试结果](reports/vision-smoke/summary.json) · [完整口径及精简输出实验](docs/benchmarks.md)

### 新增：公开 BBH 推理子集

从[论文作者发布的 BIG-Bench Hard](https://github.com/suzgunmirac/BIG-Bench-Hard)固定抽取 **400 道原题**：300 道评测、100 道预留开发。10 类任务各 30 道评测题，原文与选项保留；双方同题、无示例、关闭 DeepSeek thinking，使用默认 standard 输出，Jev 固定 `jev-1.13.0`。

| 指标 | Jev | dsk-jev / DeepSeek |
|---|---:|---:|
| 正确率 | **274/300（91.3%）** | 177/300（59.0%） |
| 请求成功率 | 300/300 | 300/300 |
| 端到端 P50 / P95 | **353 / 548 ms** | 700 / 993 ms |
| 每千请求估算费用（美元） | **$0.0191** | 高峰 $0.1975 / 低峰 $0.0988 |
| 7 对象交换追踪 | **30/30** | 2/30 |
| 7 对象逻辑推断 | **29/30** | 17/30 |
| 日期理解 | **26/30** | 20/30 |

**当前版本在这个子集上明显落后于 Jev。** 这是选定任务的诊断子集，不是完整 BBH 榜单、Jev 官方评测或生产流量分布；公开题目是否进入过模型训练未知。结果衡量当前代理配置，不代表 DeepSeek 的能力上限。所有失败均计入，未根据结果重选题；已有测试结果以后作为回归基线。

[全部 10 类结果](reports/public-bbh-v1-analysis.md) · [速度与费用](reports/public-bbh-v1.md) · [数据来源与复现](evals/public-bbh/README.md) · [评测来源调研](docs/benchmark-sources.md)

## 快速启动

自备 DeepSeek API Key；实际调用产生上游费用。源码运行需要 Go 1.26.1 或更新版本。

```sh
git clone https://github.com/windy/dsk-jev.git
cd dsk-jev
export PROXY_API_KEY='choose-a-local-client-key'
export DEEPSEEK_API_KEY='your-deepseek-key'
go run ./cmd/server
```

也可下载 Release 中的二进制，校验 SHA256SUMS 后运行 `./dsk-jev`。macOS 二进制未经 Apple 公证。

Docker 启动（先设置以上环境变量）：

```sh
docker build -t dsk-jev:local .
docker run --rm --name dsk-jev -p 127.0.0.1:8080:8080 \
  -e PROXY_API_KEY -e DEEPSEEK_API_KEY dsk-jev:local
```

另开终端并设置相同的 `PROXY_API_KEY`：

```sh
curl --fail-with-body http://127.0.0.1:8080/v1/systemone \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/vision.json
```

图片示例已内嵌 PNG，无需上传；换成 `examples/ticket.json` 即可测试文本请求。

## 图片与边界

在原请求上加 `images: [{"url": "图片公开 URL 或 Base64 data URL", "detail": "low"}]`。`state` 必填，可为空字符串。支持多图、PNG/JPEG/GIF/WebP；最多 8 张，整个 JSON 4 MiB，单张内联图解码后 2 MiB。图片由模型直接处理；HTTP JSON 支持该扩展，原生 TypeSafe SDK 不一定提供额外字段入口。

默认关闭 thinking，最多 3 次重试，整个请求预算 30 秒；批次中只重试无效题目。`usage` 累计包括失败尝试在内的上游已知用量。拿不到 usage 的调用不能视为免费。

默认 `OUTPUT_MODE=standard`；`fast` 是压缩概率输出实验模式；纯文本输出协议尚未接入产品。没有租户管理、网关限流、内置 TLS 或本地结果缓存。JSONL 用量记录不是事务收费账本。默认只监听本机；不要直接开放无保护的公网服务。

配置见 [.env.example](.env.example)，服务不会自动读取 `.env`。完整协议、SDK 示例、错误码、图片测试和评测命令见[指南](docs/guide.zh-CN.md)。

MIT 许可证；引用算法的版权信息保留在 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES)。
