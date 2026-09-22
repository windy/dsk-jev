# Launch copy (draft for the maintainer)

## English

I built dsk-jev: an experimental Jev-compatible decision API in Go, backed by DeepSeek Flash, with image input. Feed it text or pictures and ask Choice, Score or Noul questions. It includes partial retries, token/cache observability, and reproducible evaluations.

The goal is to explore multimodal and richer decision tasks behind a small typed API. This is not Jev's model and we aren't claiming better latency, cost or calibrated confidence. The first release includes runnable text/image fixtures, Docker and source code.

https://github.com/windy/dsk-jev

## 中文

开源一个实验项目 dsk-jev：用 Go + DeepSeek Flash 实现 Jev 兼容的决策 API，并扩展图片输入。把文本或图片转成 Choice / Score / Noul，支持局部重试、用量和缓存观测，以及可复现的测试。

希望探索多模态和更复杂的判断任务。目前不宣称比 Jev 更快、更便宜或概率校准更好；首版提供文本/图片示例、Docker 和源码，欢迎用真实业务场景测试和贡献。

https://github.com/windy/dsk-jev
