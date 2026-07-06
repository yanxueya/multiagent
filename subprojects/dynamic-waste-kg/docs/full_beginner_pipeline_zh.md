# 从零开始运行：知识图谱、Neo4j、YOLO 训练与复核模型

这份教程按“小白也能照着做”的方式写。你只需要一行一行复制命令，不需要一次理解所有原理。

## 0. 当前已测试结果

我已经在当前电脑上实际跑过：

- 知识图谱单元测试：成功；
- 数据集转换：成功；
- YOLO 分割数据集生成：成功；
- Neo4j Cypher 导出文件生成：成功；
- Neo4j Python 驱动安装：成功；
- Neo4j Docker 服务启动：未成功，因为 Docker Desktop 当前没有运行；
- YOLO 依赖：`ultralytics` 已安装在 `.venv` 中；
- YOLO GPU 训练：当前还不能用，因为 `.venv` 里的 PyTorch 是 CPU 版，`torch.cuda.is_available()` 为 `False`。

所以现在代码是可用的，但正式训练 YOLO 前，需要单独创建一个 GPU 训练环境。详细环境结论见：[本机开发环境画像](local_environment_profile_zh.md)。

## 1. 项目目录在哪里

你的知识图谱子项目在：

```powershell
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

以后所有命令都先进入这个目录：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

## 2. 是否需要虚拟环境

需要。

原因很简单：YOLO、PyTorch、Neo4j 驱动这些包比较大，如果直接装到系统 Python 里，以后别的项目可能会冲突。

当前我已经创建了虚拟环境：

```powershell
C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\.venv
```

如果以后你删掉了它，可以重新创建：

```powershell
python -m venv .venv
```

## 3. 不激活虚拟环境也能运行

为了避免 PowerShell 权限问题，推荐你直接用虚拟环境里的 Python。

检查 Python：

```powershell
.\.venv\Scripts\python.exe --version
```

以后教程里的 Python 命令，优先用：

```powershell
.\.venv\Scripts\python.exe
```

## 4. 安装基础依赖

Neo4j 驱动我已经装成功了。如果你以后重建虚拟环境，重新运行：

```powershell
.\.venv\Scripts\python.exe -m pip install neo4j
```

检查是否成功：

```powershell
.\.venv\Scripts\python.exe -c "import neo4j; print(neo4j.__version__)"
```

如果能打印版本号，就说明安装成功。

## 5. 安装 YOLO 训练依赖

YOLO 训练需要 `ultralytics` 和 PyTorch。当前 `.venv` 已经安装了 `ultralytics`，但 PyTorch 是 CPU 版，只适合做导入测试，不适合训练。

先检查当前 `.venv`：

```powershell
.\.venv\Scripts\python.exe -c "import ultralytics, torch; print('ultralytics ok'); print(torch.__version__); print(torch.cuda.is_available())"
```

如果最后输出是 `False`，说明当前环境不能用显卡训练，这是正常的。

当前最便捷方案是不重装 Python、不重装 CUDA，直接替换当前 `.venv` 里的 CPU 版 PyTorch。

先进入项目目录：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

卸载 CPU 版 PyTorch：

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y torch torchvision torchaudio
```

安装 nightly CUDA 12.8 版 PyTorch。这个版本已在本机验证支持 RTX 5060 Laptop GPU 的 `sm_120`：

```powershell
.\.venv\Scripts\python.exe -m pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu128
```

最后检查 GPU：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

只有 `torch.cuda.is_available()` 输出 `True`，才说明可以用显卡训练。

## 6. 训练数据在哪里

我已经把你两个原始数据集转换好了。

转换后的数据在：

```powershell
datasets\waste12_yolo
```

最重要的训练配置文件是：

```powershell
datasets\waste12_yolo\data.yaml
```

当前数据量：

- 训练集：3464 张；
- 验证集：984 张；
- 测试集：715 张。

注意：当前数据里没有 `glass` 和 `asbestos_suspect` 的正样本。这两个类别保留在知识图谱里，但当前 YOLO 训练主要依赖其他 10 类。

## 7. 如果要重新生成数据集

一般不需要重复做。

如果你想重新生成，运行：

```powershell
.\.venv\Scripts\python.exe -m wastekg.dataset_builder `
  --codd-root "D:\可能有用的data\Construction and Demolition Waste Object Detection Dataset  (CODD)" `
  --instance-seg-root "D:\可能有用的data\1. Instance Segmentation" `
  --output-root "C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg\datasets\waste12_yolo"
```

运行后看：

```powershell
datasets\waste12_yolo\dataset_summary.json
```

这个文件会告诉你每类有多少标注。

## 8. 开始训练 YOLO

先确保 `.venv` 已经安装 CUDA 12.8 版 PyTorch，并且 `torch.cuda.is_available()` 是 `True`。

然后运行：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 3 `
  --imgsz 640 `
  --batch 4 `
  --device 0
```

如果显存不够，把 `batch` 改小，比如：

```powershell
.\.venv\Scripts\python.exe scripts\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model yolo11n-seg.pt `
  --epochs 3 `
  --imgsz 640 `
  --batch 2 `
  --device 0
```

第一次建议先用 3 个 epoch 测试流程能不能跑通，再训练 80 个 epoch。

训练结果通常会在：

```powershell
runs\waste12_seg
```

里面会有模型权重，例如：

```powershell
best.pt
last.pt
```

## 9. 轻量复核模型是什么

YOLO 负责快速识别。

轻量复核模型只处理这些情况：

- YOLO 置信度不高；
- 类别容易混淆；
- 目标是 `glass`、`asbestos_suspect` 等高风险对象；
- 规划前需要人工确认。

当前项目已经有接口，不要求你一开始就训练真正的大模型。

最小复核模型只需要实现一个 `review()` 方法，返回：

```python
ReviewResult(
    class_name="glass",
    confidence=0.91,
    risk_hint="medium",
    reason="transparent brittle fragment",
    need_human_review=True,
)
```

以后你可以把这个位置替换成多模态模型、API 模型或本地轻量视觉语言模型。

## 10. YOLO 结果怎么写入知识图谱

最小例子：

```python
from wastekg import KnowledgeGraph, apply_perception_records_to_graph, seed_default_categories

graph = KnowledgeGraph()
seed_default_categories(graph)

packet, result = apply_perception_records_to_graph(
    graph,
    frame_id="frame_001",
    source="yolo_seg",
    yolo_records=[
        {
            "temp_id": "d1",
            "yolo_class_name": "brick",
            "yolo_confidence": 0.92,
            "center_xyz": [0.10, 0.20, 0.05],
        }
    ],
)
```

写入后，图谱会自动生成：

- 实例节点；
- 长期属性投影；
- 短期状态；
- 事件日志；
- 后续规划上下文。

## 11. Neo4j 怎么建

先打开 Docker Desktop。

然后在 PowerShell 运行：

```powershell
docker run --name wastekg-neo4j `
  -p 7474:7474 `
  -p 7687:7687 `
  -e NEO4J_AUTH=neo4j/wastekg123456 `
  -d neo4j:latest
```

打开浏览器：

```text
http://localhost:7474
```

登录：

```text
用户名：neo4j
密码：wastekg123456
```

## 12. 导出图谱到 Neo4j 文件

运行：

```powershell
.\.venv\Scripts\python.exe scripts\export_demo_neo4j.py --out artifacts\demo_graph
```

会生成：

```powershell
artifacts\demo_graph\neo4j_import.cypher
artifacts\demo_graph\graph_snapshot.json
artifacts\demo_graph\events.jsonl
artifacts\demo_graph\graph.mmd
```

## 13. 把图谱导入 Neo4j

确认 Docker 里的 Neo4j 已经启动后运行：

```powershell
.\.venv\Scripts\python.exe scripts\import_neo4j_cypher.py `
  --cypher artifacts\demo_graph\neo4j_import.cypher `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password wastekg123456
```

导入成功后，回到 Neo4j Browser，输入：

```cypher
MATCH (n) RETURN n LIMIT 50
```

你应该能看到：

- `Category` 节点；
- `Instance` 节点；
- `Event` 节点；
- 实例和类别之间的关系；
- 事件和对象之间的关系。

## 14. 每次运行前先做什么

建议顺序：

1. 打开 PowerShell；
2. 进入项目目录；
3. 用虚拟环境 Python；
4. 先跑测试；
5. 再训练或导入 Neo4j。

命令：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

如果测试通过，再继续。

## 15. 当前最推荐的下一步

先不要训练 80 个 epoch。

建议你先做三步：

1. 不重装 CUDA，不重装 Python；
2. 在当前 `.venv` 中卸载 CPU 版 `torch/torchvision`；
3. 安装 nightly CUDA 12.8 版 `torch/torchvision`；
4. 确认 `torch.cuda.is_available()` 是 `True`；
5. 用 3 个 epoch 跑通 YOLO 训练；
6. 打开 Docker Desktop，把 demo 图谱导入 Neo4j。

这三步跑通后，再进行长时间训练。
