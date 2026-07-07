# 本机开发环境画像

记录日期：2026-06-12

用途：这份文件用于记录当前电脑与本项目相关的真实环境。后续开发知识图谱、YOLO 训练、Neo4j 可视化、LangGraph 接入、ROS2 接入时，优先按本文档选择命令和环境。

> 说明：我不能把信息写入系统级“永久记忆”，但已经把它保存为项目内文档。只要后续仍在这个 `multiagent` 项目中开发，就可以把这份文件当作本项目的环境记忆。

---

## 1. 你的电脑基础配置

你提供的硬件与系统信息：

- 电脑：联想拯救者 Y7000P
- CPU：Intel i7-14650HX
- 内存：16 GB RAM
- 显卡：8 GB 显存独立显卡
- 系统：Windows 11 x64
- 已有环境：Docker、Git、Node.js、WSL
- 另有系统：双系统 Ubuntu 22.04
- Ubuntu 22.04 中之前安装并尝试过 ROS2 和机械臂相关内容

当前检测到的关键显卡信息：

- NVIDIA 驱动版本：582.05
- `nvidia-smi` 显示的 CUDA Version：13.0
- 显卡名称：NVIDIA GeForce RTX 5060 系列笔记本显卡
- 显存：约 8 GB

重要解释：

- `nvidia-smi` 中的 `CUDA Version: 13.0` 表示“当前显卡驱动最高支持的 CUDA 运行时版本”。
- 它不等于你已经安装了 CUDA Toolkit。
- 当前命令行中没有检测到 `nvcc`，说明 CUDA Toolkit 没有安装，或者没有加入 PATH。
- 对 YOLO/PyTorch 训练来说，一般不需要单独安装 CUDA Toolkit，只要安装 CUDA 版 PyTorch 即可。

---

## 2. 当前 Python 状态

系统 Python：

- 版本：Python 3.14.4
- 路径：`C:\Python314\python.exe`

当前项目虚拟环境：

- 路径：`C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\.venv`
- Python 版本：3.14.4

当前 `.venv` 中已经安装：

- `ultralytics==8.4.66`
- `torch==2.12.0`
- `torchvision==0.27.0`
- `opencv-python==4.13.0.92`
- `neo4j==6.2.0`
- `numpy==2.4.6`

但当前 `.venv` 的 PyTorch 是 CPU 版：

- `torch.__version__`：`2.12.0+cpu`
- `torch.version.cuda`：`None`
- `torch.cuda.is_available()`：`False`
- `torch.cuda.device_count()`：`0`

结论：

- 当前 `.venv` 可以用于知识图谱代码、Neo4j 脚本、数据集转换、轻量测试。
- 当前 `.venv` 不适合 GPU 训练 YOLO。
- 不建议用 Python 3.14 作为深度学习训练环境，因为很多深度学习包对最新版 Python 的 GPU 轮子支持会滞后。

---

## 3. 推荐的环境分工

为了后续接 ROS2、Neo4j、YOLO、大模型时不互相干扰，建议分成三个环境。

### 3.1 知识图谱开发环境

用途：

- 长期知识层
- 短期记忆层
- 事件日志
- Neo4j 导出
- LangGraph 接口
- ROS2 输出接口的代码开发

推荐使用：

```powershell
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\.venv\Scripts\python.exe
```

当前这个环境已经基本够用。

### 3.2 YOLO 训练环境

用途：

- Ultralytics YOLO segmentation 训练
- 数据集验证
- 模型推理测试
- 后续接入轻量复核模型

当前最便捷方案：

- 不重装 CUDA；
- 不重装 NVIDIA 驱动；
- 不重装 Python；
- 先不创建 `.venv-yolo`；
- 直接把当前 `.venv` 中的 CPU 版 PyTorch 替换成 CUDA 12.8 版 PyTorch。

2026-06-12 已联网查询并安装 PyTorch 官方 nightly CUDA 12.8 源，当前 Python 3.14 项目环境使用：

- `torch 2.12.0.dev20260408+cu128`
- `torchvision 0.27.0.dev20260407+cu128`

原因：RTX 5060 Laptop GPU 的计算能力是 `sm_120`。本机验证显示 nightly 版 PyTorch 的架构列表包含 `sm_120`，比 `torch 2.11.0+cu128` 稳定版更适合当前新显卡。

备用方案：

- 如果替换 CUDA 12.8 版 PyTorch 后仍然不能调用 GPU，再考虑安装 Python 3.12 并创建 `.venv-yolo`。
- 现在不建议优先重装 Python 或 CUDA。

### 3.3 ROS2 机械臂环境

用途：

- ROS2
- MoveIt2
- RealSense
- 机械臂驱动
- 真实执行控制

推荐放在：

```text
Ubuntu 22.04 双系统
```

理由：

- ROS2 在 Ubuntu 22.04 上更稳定。
- 后续 RealSense、机械臂 SDK、MoveIt2 在 Ubuntu 上资料更多。
- Windows 端适合做数据处理、YOLO 训练、图谱开发；Ubuntu 端适合真实机器人执行。

---

## 4. 当前工具状态

Git：

- 已安装
- 版本：`2.54.0.windows.1`

Docker：

- 已安装
- 版本：`29.4.0`
- 当前 Docker daemon 没有运行
- 需要先打开 Docker Desktop，才能运行 Neo4j Docker 容器

Node.js：

- 已安装
- 版本：`v24.15.0`

npm：

- 已安装
- 版本：`11.12.1`
- PowerShell 直接运行 `npm` 可能会被执行策略拦截
- 推荐使用：

```powershell
cmd /c npm --version
```

WSL：

- 已安装过
- 当前命令行没有稳定读出 WSL 发行版列表
- 本项目主线暂时不依赖 WSL

---

## 5. 关于 CUDA 13.0 的正确处理方式

你看到的 `CUDA Version: 13.0` 不代表训练失败，也不代表必须安装 CUDA 13.0 Toolkit。

正确理解是：

1. 你的 NVIDIA 驱动比较新。
2. 新驱动通常可以兼容 PyTorch 官方提供的 CUDA 12.x 运行时轮子。
3. 训练前关键不是看 `nvidia-smi`，而是看 PyTorch 是否能调用 CUDA。

判断标准：

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

如果输出里有：

```text
True
NVIDIA GeForce ...
```

才说明 YOLO 可以用 GPU 训练。

当前 `.venv` 输出是 `False`，所以不能用 GPU。

---

## 6. 最便捷的 YOLO GPU 环境修复步骤

第一步：进入项目目录。

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

第二步：卸载当前 CPU 版 PyTorch。

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y torch torchvision torchaudio
```

第三步：安装 nightly CUDA 12.8 版 PyTorch。

```powershell
.\.venv\Scripts\python.exe -m pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128
```

第四步：验证 GPU 是否可用。

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

成功时应看到类似：

```text
2.12.0.dev20260408+cu128
12.8
True
NVIDIA GeForce RTX 5060 Laptop GPU
```

本机已经验证通过：

```text
torch 2.12.0.dev20260408+cu128
torch cuda 12.8
cuda available True
device count 1
name NVIDIA GeForce RTX 5060 Laptop GPU
capability (12, 0)
arch list ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```

如果 `torch.cuda.is_available()` 是 `True`，就可以开始训练。只有这一步失败时，才考虑安装 Python 3.12 和创建 `.venv-yolo` 的备用方案。

---

## 7. 你的显卡训练建议

由于显存约 8 GB，建议先用保守参数跑通。

第一次只测试流程：

```powershell
.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 3 `
  --imgsz 640 `
  --batch 4 `
  --device 0
```

如果显存不足，把 `batch` 改成 2：

```powershell
--batch 2
```

如果仍然不足，把图片尺寸改小：

```powershell
--imgsz 512
```

训练稳定后再考虑：

- `epochs 80`
- `batch 4` 或 `batch 8`
- `imgsz 640`
- 模型从 `yolo11n-seg.pt` 升到 `yolo11s-seg.pt`

不建议一开始用大模型，因为会慢、显存容易不够，也更难判断问题来自数据还是模型。

---

## 8. 后续开发必须遵守的环境原则

1. 知识图谱代码优先用 `.venv`。
2. 当前最便捷方案是也用 `.venv` 训练 YOLO，但要先把 CPU 版 PyTorch 替换为 CUDA 12.8 版。
3. ROS2 和机械臂执行优先放在 Ubuntu 22.04。
4. 不要把所有包都装进系统 Python。
5. 不要为了 `nvidia-smi` 的 CUDA 13.0 去盲目安装 CUDA Toolkit。
6. 训练前必须先确认 `torch.cuda.is_available()` 是 `True`。
7. Neo4j 如果用 Docker，先打开 Docker Desktop。
8. Windows 端负责训练和图谱开发，Ubuntu 端负责真实 ROS2 执行，是当前最稳的路线。

---

## 9. 当前项目环境结论

当前状态：

- 知识图谱项目：可继续开发和测试。
- 数据集转换：已经完成。
- YOLO 权重文件：已经存在 `yolo11n-seg.pt`。
- Ultralytics：已安装在 `.venv`，但当前是 CPU PyTorch。
- GPU 训练：还没有配置成功。
- Neo4j Docker：需要先启动 Docker Desktop。

最推荐的下一步：

1. 不重装 CUDA，不重装 Python。
2. 在当前 `.venv` 中卸载 CPU 版 `torch/torchvision`。
3. 安装 nightly CUDA 12.8 版 `torch/torchvision`。
4. 验证 `torch.cuda.is_available()`。
5. 用 3 个 epoch 跑通 YOLO segmentation 训练。
6. 再把训练好的 `best.pt` 接入知识图谱感知入口。
