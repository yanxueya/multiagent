# E2 受约束 VLM 图像复核

## 目的

回答 RQ2：当 YOLO 对某些样本低置信度、类别敏感或边界不稳定时，视觉语言模型是否能在受约束类别表内复核结果，并在不确定时触发人工审查。

## 为什么当前 E2 阻塞

当前代码已经能为每个复核对象生成三类视觉证据：

- 原始图像；
- bbox crop；
- mask overlay。

但是此前配置的 `deepseek-ai/DeepSeek-V4-Pro` 被硅基流动接口明确拒绝，错误含义是该模型不是 VLM，只支持文本提示。这说明失败原因是模型能力不匹配，而不是 YOLO、知识图谱或本地代码错误。

## 模型选择原则

必须满足以下条件：

1. 模型明确支持图像输入；
2. Chat Completions 接口接受 `image_url` 或等效图像字段；
3. 能返回严格 JSON；
4. 输出类别被限制在 11 个视觉类别内；
5. 不确定、非法 JSON、超时或 API 错误时，系统必须保留 YOLO 结果并升级为 `human_review_required`。

## 关于 `zai-org/GLM-5.2`

除非硅基流动控制台或模型文档明确标注 `zai-org/GLM-5.2` 是视觉语言模型，否则不建议用于 E2。E2 更应优先选择名称中明确带 `V` 的模型，例如 `GLM-4.5V`、`GLM-4.6V` 或平台提供的其他 VLM。

## GLM-4.5V 当前冒烟测试记录（2026-06-25）

已将本地 `.env` 配置为：

```env
LLM_MODEL=zai-org/GLM-4.5V
LLM_RESPONSE_FORMAT_JSON=false
```

原因：`zai-org/GLM-4.5V` 可以接收图像输入，但硅基流动接口返回 `Json mode is not supported for this model`，因此请求中不能携带 `response_format={"type":"json_object"}`。本项目改为通过提示词要求 JSON，并在本地解析和校验返回内容。

单图冒烟测试输出：

```text
artifacts/e2_glm45v_single_image_smoke_r3
```

结果：GLM-4.5V 成功读取图像证据并返回结构化视觉复核结果。该样本中，模型输出 `decision=uncertain`，系统保留 YOLO 的 `hard_plastic` 结果，同时将实例升级为 `human_review_required`。这说明 E2 的“图像证据输入 + VLM 复核 + 保守回退”链路已跑通。

注意：这只是单图冒烟测试，不能替代 C1/C2 批量评估。后续若用于论文，需要在固定 val/test 子集上统计 correction rate、harmful override rate、invalid fallback rate、human escalation rate 和平均延迟。

## GLM-4.5V 小批量冒烟测试记录（2026-06-25）

已执行 20 张验证集图片的小批量 E2 冒烟测试，每张图最多保留 1 个 YOLO 检测目标。为降低硅基流动的 TPM 限制，第三轮采用轻量证据模式：只向 VLM 发送 bbox crop 和 mask overlay，不发送整张原图，并在请求之间等待 5 秒。

最终推荐结果目录：

```text
artifacts/paper/e2_vlm_glm45v_batch20_r3_focused
```

主要结果：

```text
image_count = 20
detection_count = 18
reviewed_count = 17
valid_vlm_response_count = 13
valid_vlm_response_rate = 0.7647
human_review_required_count = 9
human_review_required_rate = 0.5000
mean_latency_seconds = 8.4690
decision_counts = agree: 8, change: 0, uncertain: 5, review_error: 4, not_reviewed: 1
```

剩余 4 个 `review_error` 均来自硅基流动接口的 `HTTP 429 TPM limit reached`，说明主要瓶颈是账号/模型服务的每分钟 token 限制，而不是图像证据生成、VLM 图像输入或 JSON 解析失败。系统对这些失败样本采取保守回退：保留 YOLO 类别，并将实例升级为 `human_review_required`。

论文写作边界：该结果可作为 E2 的小批量可运行性证据，但仍不是完整 C1/C2 test-set 对照实验。正式投稿前若要报告 VLM 性能，应扩大样本并在更高 TPM 配额、离线缓存或更低分辨率图像证据条件下重新运行。

## 解除阻塞后的最小测试

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image datasets\waste12_yolo\images\val\instseg_mix07_rgb_0038_png_jpg.rf.f85422203eb2cdf1f58a20d17d16fc25.jpg `
  --weights outputs\yolo_runs\segment\outputs\yolo_runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt `
  --out artifacts\single_image_vlm_smoke `
  --conf 0.5 `
  --device 0 `
  --max-det 1 `
  --llm-review
```

成功条件不是“模型返回了一段话”，而是 `vision_packet.json` 中能看到严格结构化复核状态，并且复核证据图像存在。
