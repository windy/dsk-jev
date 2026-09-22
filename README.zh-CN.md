# dsk-jev

**用 Go 和 DeepSeek 实现 Jev 兼容的决策 API，并扩展图片输入。**

[English](README.md) · [完整指南](docs/guide.zh-CN.md) · [评测](docs/benchmarks.md) · [下载](https://github.com/windy/dsk-jev/releases)

输入文本、结构化状态或图片，输出 Choice、Score、Noul。单个 Go 二进制，无第三方 Go 模块依赖，支持局部重试、缓存观测和逐次用量记录。

本项目是实验性、非官方实现，不运行 Jev 权重。协议兼容不代表预测、置信度校准、速度或成本等价。图片是本项目的扩展；复杂认知优势尚待专项评测，当前不宣称比 Jev 更快、更便宜或更准。

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
