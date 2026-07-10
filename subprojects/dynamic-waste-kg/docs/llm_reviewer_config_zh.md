# 大模型复核器配置说明

本项目的大模型复核器使用 OpenAI-compatible Chat Completions 接口。你现在使用的是硅基流动，因此推荐按硅基流动配置 `.env`。

参考官方文档：<https://api-docs.siliconflow.cn/docs/api/chat-completions-post>

## 1. 硅基流动配置

硅基流动的请求地址是：

```text
https://api.siliconflow.cn/v1/chat/completions
```

所以项目里的 `LLM_BASE_URL` 应该写成：

```env
LLM_BASE_URL=https://api.siliconflow.cn/v1
```

完整 `.env` 示例：

```env
LLM_API_KEY=你的硅基流动 API token
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=硅基流动控制台中可用的模型名
LLM_TIMEOUT=30
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=400
```

注意：`LLM_MODEL` 必须使用硅基流动控制台中显示的准确模型名。不要把其他平台的模型名直接复制过来。

## 2. 模板文件和真实配置文件

模板文件：

```text
subprojects/dynamic-waste-kg/.env.example
```

真实配置文件：

```text
subprojects/dynamic-waste-kg/.env
```

`.env` 已经被 `.gitignore` 忽略，不应该提交到 Git。

重要：`.env.example` 只能放空占位符，不能放真实 token。如果真实 token 曾经写进 `.env.example`，建议立即去硅基流动后台重置该 token。

## 3. 为什么之前会 401

如果报错：

```text
HTTP 401 Unauthorized
Authentication Fails, Your api key is invalid
```

通常是下面几种原因：

- 硅基流动 token 写错；
- 复制 token 时多了空格；
- `LLM_BASE_URL` 仍然写成 `https://api.deepseek.com`；
- `LLM_API_KEY` 是硅基流动 token，但请求发到了 DeepSeek 官方地址；
- 终端环境变量里存在旧的 `LLM_API_KEY`，覆盖了 `.env`；
- token 被禁用、过期或额度不足。

你当前通过硅基流动调用，最关键的是：

```env
LLM_BASE_URL=https://api.siliconflow.cn/v1
```

## 4. 检查当前配置

正式跑 YOLO 之前，先运行：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py
```

它不会请求 API，也不会消耗 token，只会显示脱敏后的配置。

你应该看到类似：

```text
base_url: https://api.siliconflow.cn/v1
model: 你选择的模型名
api_key: sk-...xxxx
```

如果 `base_url` 仍然是 `https://api.deepseek.com`，说明 `.env` 没改对，或者终端环境变量覆盖了 `.env`。

## 5. 测试硅基流动 API 连通性

确认配置无误后，再运行：

```powershell
.\.venv\Scripts\python.exe scripts\llm\check_llm_config.py --live
```

`--live` 会真实请求硅基流动，会消耗少量 token。

如果 `--live` 成功，再运行 YOLO + 大模型复核。

## 6. 运行单图 YOLO + 大模型复核

建议先限制为 5 个目标，避免浪费 token：

```powershell
.\.venv\Scripts\python.exe scripts\graph\predict_image_to_graph.py `
  --image datasets\waste12_yolo\images\val\instseg_mix07_rgb_0038_png_jpg.rf.f85422203eb2cdf1f58a20d17d16fc25.jpg `
  --weights outputs\yolo_runs\segment\outputs\yolo_runs\waste12_seg\yolo11n_seg_cdw_glass_e50\weights\best.pt `
  --out artifacts\single_image_llm_demo `
  --conf 0.5 `
  --device 0 `
  --max-det 5 `
  --llm-review
```

## 7. VS Code 的 `.env` 提示

如果 VS Code 显示：

```text
An environment file is configured but terminal environment injection is disabled.
Enable "python.terminal.useEnvFile" to use environment variables from .env files in terminals.
```

这只是说明 VS Code 不会自动把 `.env` 注入终端。

本项目代码会主动读取项目根目录的 `.env`，所以一般不依赖 VS Code 注入。

如果你希望 VS Code 终端也自动注入 `.env`，可以在 VS Code `settings.json` 中加入：

```json
"python.terminal.useEnvFile": true
```

但要注意：终端环境变量优先级高于 `.env`。如果 PowerShell 里已经设置过旧的 `LLM_API_KEY`，旧值会覆盖 `.env`。

## 8. 当前复核逻辑

VLM 只负责结构化视觉属性抽取和一致性校验，不直接替代 YOLO。

流程：

```text
YOLO 输出类别和置信度
  -> 0.30 <= conf < 0.75 触发 VLM 属性一致性校验
  -> 0.05 <= conf < 0.30 进入 unknown/人工复核；conf < 0.05 不进入候选池
  -> VLM 提取颜色、透明度、光泽、纹理、边缘和形状线索
  -> VLM 判断这些属性是否支持 YOLO 类别假设
  -> 证据不足或冲突时进入 uncertain/unknown
```

硅基流动接口中，项目会自动为 `api.siliconflow.cn` 使用：

```json
"enable_thinking": false
```

而不是 DeepSeek 风格的：

```json
"thinking": {"type": "disabled"}
```
