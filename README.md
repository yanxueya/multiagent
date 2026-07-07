# multiagent 工作区

这是一个多智能体与动态建筑废弃物知识图谱研究工作区。当前已经实现的核心子项目是 `subprojects/dynamic-waste-kg`，其余子项目是为了后续接入 LangChain/LangGraph 多智能体、ROS2、前端和仿真而建立的占位结构。

## 推荐阅读顺序

1. [代理上下文与项目规则](AGENTS.md)
2. [子项目结构说明](subprojects/README.md)
3. [知识图谱项目总入口](subprojects/dynamic-waste-kg/README.md)
4. [知识图谱文档索引](subprojects/dynamic-waste-kg/docs/README.md)
5. [长期知识层种子说明](subprojects/dynamic-waste-kg/docs/knowledge_seed_zh.md)
6. [数据集处理与感知流水线](subprojects/dynamic-waste-kg/docs/dataset_and_perception_pipeline_zh.md)
7. [YOLO + 大模型接入指南](subprojects/dynamic-waste-kg/docs/yolo_llm_integration_zh.md)

## 当前项目结构

```text
multiagent/
  AGENTS.md                         # AI 编码代理上下文规则
  README.md                         # 工作区入口
  .gitignore                        # 忽略数据集、outputs、权重、虚拟环境等
  subprojects/
    README.md                       # 子项目边界说明
    dynamic-waste-kg/               # 已实现：知识图谱、数据处理、感知流水线、论文实验
      wastekg/                      # 按 core/data/yolo/llm/perception/rgbd/graph/interfaces/paper 分层
      scripts/                      # 按 data/yolo/llm/rgbd/graph/paper/tools 分类的命令行入口
    dynamic-waste-agent/            # 占位：LangChain/LangGraph 多智能体编排层
    dynamic-waste-ros2/             # 占位：ROS2 工作区与机器人桥接层
    dynamic-waste-ui/               # 占位：前端/人工复核/监控界面
    dynamic-waste-sim/              # 占位：仿真、数字孪生、离线回放
```

## 分层关系

```text
dynamic-waste-ui
  -> dynamic-waste-agent
      -> dynamic-waste-kg
      -> dynamic-waste-ros2
          -> robot / sensors
      -> dynamic-waste-sim
```

## 核心规则

- 根目录不放活动项目文档目录，不再使用根 `docs/`。
- 当前关键文档放在 `subprojects/dynamic-waste-kg/docs/`。
- 数据处理和中间数据说明放在 `subprojects/dynamic-waste-kg/datasets/docs/`。
- 核心 Python 代码按领域放入 `wastekg/core`、`wastekg/data`、`wastekg/yolo`、`wastekg/llm` 等子包。
- `scripts/` 只放命令行入口，真实逻辑应在 `wastekg/` 子包中。
- 小论文补充实验文档放在 `subprojects/dynamic-waste-kg/paper_experiments/docs/`。
- 数据集、YOLO outputs、模型权重、虚拟环境和本地密钥不进入 Git。
- 涉及模型训练时，AI 代理只输出操作指令、参数建议和风险提示，不在沙盒中启动训练。
- GPU 训练要合理：运行前显式检查显存，并考虑本机约 8 GB 显存限制。

## 常用命令

进入知识图谱子项目：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

运行现有测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

查看仓库状态：

```powershell
cd C:\Users\12279\Documents\multiagent
git status --short --branch
```

继续 YOLO-seg 训练时，请由用户在本机确认显存后手动运行，例如：

```powershell
.\.venv\Scripts\python.exe scripts\yolo\train_yolo_seg.py `
  --data datasets\waste12_yolo\data.yaml `
  --model outputs\yolo_runs\segment\outputs\yolo_runs\waste12_seg\yolo11n_seg_e50\weights\best.pt `
  --epochs 50 `
  --imgsz 640 `
  --batch 4 `
  --device 0 `
  --name yolo11n_seg_next
```
