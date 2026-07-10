# multiagent 工作区

这是一个多智能体与动态建筑废弃物知识图谱研究工作区。当前已实现知识图谱核心、LangGraph 4-agent 编排和前端工作台原型；ROS2 真实桥接、机械臂闭环和仿真仍待接入。

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
    dynamic-waste-agent/            # 已实现：LangGraph 4-agent 编排层
    dynamic-waste-ros2/             # 占位：ROS2 工作区与机器人桥接层
    dynamic-waste-ui/               # 已实现原型：前端/人工复核/监控界面
    dynamic-waste-sim/              # 占位：仿真、数字孪生、离线回放
```


## 决策逻辑

本项目把知识事实和规划期决策严格分开：

```text
知识图谱 graph_state：提供类别先验、实例状态和当前可行性
行动规划智能体：动态计算优先级，决定先后顺序和失败恢复
```

知识图谱维护长期类别属性、短期实例、关系和追加式事件。处理优先级与评分不保存到知识图谱；规划器先用 `graph_state` 排除当前不可执行对象，再根据任务目标、YOLO 证据、处理权限和 `attempt_count` 计算动态优先级，生成动作顺序与失败恢复策略。
## 分层关系

```text
dynamic-waste-ui
  -> dynamic-waste-agent
      -> action_planning_agent
      -> dynamic-waste-kg graph_state
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
