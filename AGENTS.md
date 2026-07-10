# AGENTS.md

这是 AI 编码代理在本仓库工作的上下文地图。目标是减少上下文膨胀：先读本文件，再按任务读取少量相关文档，不要递归读取全部 Markdown。

## 1. 项目定位

`multiagent` 是动态建筑废弃物感知、知识图谱、多智能体决策和后续 ROS2 机械臂执行的研究工作区。

当前已实现：

```text
subprojects/dynamic-waste-kg
subprojects/dynamic-waste-agent
subprojects/dynamic-waste-ui
```

当前占位或待真实接入子项目：

```text
subprojects/dynamic-waste-ros2
subprojects/dynamic-waste-sim
```

当前稳定类别设计：

```text
11 个明确视觉类别 + 系统逻辑生成 unknown
```

11 个明确视觉类别：

```text
concrete
brick
tile
wood
gypsum_board
foam
metal
soft_plastic
hard_plastic
paperboard
glass
```

`unknown` 不是 YOLO 训练类别，而是低置信度、证据冲突、疑似危险、无法可靠归类或需要人工复核时的系统状态。`asbestos_suspect` 当前不是 YOLO 训练类别；除非用户明确要求查看旧实验，否则只视为历史记录或风险复核概念。

## 2. 用户电脑约束

规划命令、依赖、训练、ROS2 或部署时，必须考虑：

- 电脑：联想拯救者 Y7000P
- CPU：Intel i7-14650HX
- 内存：16 GB RAM
- 显卡：NVIDIA GeForce RTX 5060 Laptop GPU，约 8 GB 显存
- 系统：Windows 11 x64
- NVIDIA 驱动版本：582.05
- `nvidia-smi` 显示的 CUDA Version：13.0
- 已有工具：Docker、Git、Node.js、WSL
- 双系统：Ubuntu 22.04，之前安装并尝试过 ROS2 和机械臂相关内容

规则：

- GPU 训练要合理：进行显式显存检查。
- 涉及模型训练时，代理只输出操作指令、参数建议和风险提示，不要自己在沙盒里启动训练。
- Python、知识图谱、文档和轻量测试优先在 Windows 下进行。
- ROS2 和机械臂执行优先在 Ubuntu 22.04 下进行。

## 3. 当前目录结构

```text
multiagent/
  AGENTS.md
  README.md
  .gitignore
  subprojects/
    README.md
    dynamic-waste-kg/        # 已实现：知识图谱、数据处理、感知流水线、论文实验
    dynamic-waste-agent/     # 已实现：LangGraph 4-agent 编排与确定性门控
    dynamic-waste-ros2/      # 占位：ROS2 工作区与机器人执行桥接层
    dynamic-waste-ui/        # 已实现原型：人工复核、监控和可视化界面
    dynamic-waste-sim/       # 占位：仿真、数字孪生、离线回放
```

`dynamic-waste-kg` 源码分层：

```text
subprojects/dynamic-waste-kg/
  wastekg/
    core/          # 类别体系、数据模型、长期知识种子
    data/          # 数据集审计、合并、冻结、分组
    yolo/          # YOLO runtime、图像预测、分割评估
    llm/           # OpenAI-compatible/DeepSeek 复核器
    perception/    # 感知流水线与 VisionPacket 适配
    rgbd/          # RealSense、RGB-D IO、几何补全
    graph/         # 内存图谱、查询、JSON/Mermaid/Neo4j 导出
    interfaces/    # LangGraph/ROS2 对接契约
    paper/         # 小论文实验可复用逻辑
  scripts/
    data/
    yolo/
    llm/
    rgbd/
    graph/
    paper/
    tools/
  docs/            # 当前主线关键文档
  datasets/docs/   # 数据来源、合并、清洗、审计和中间数据处理说明
  paper_experiments/
```

旧的根目录扁平兼容包装已移除。新代码必须使用分层导入，例如 `wastekg.core.models`、`wastekg.data.audit`、`wastekg.yolo.evaluation`。

## 4. 职责边界

`dynamic-waste-kg` 负责知识图谱状态层：长期类别知识、短期对象记忆、`unknown` 复核入口、事件日志、YOLO/VLM/RealSense 输入适配、RGB-D 几何辅助、Neo4j 导出和面向多智能体/ROS2 的结构化接口。

`dynamic-waste-agent` 负责 4 个真正智能体编排：总体规划 `supervisor_agent`、感知组织 `perception_agent`、行动规划 `action_planning_agent`、执行封装 `execution_agent`。知识图谱、风险门控、人工控制门控和 ROS2 bridge 都是被调用的系统组件，不是 agent。

决策边界必须保持清晰：知识图谱 `graph_state` 只回答“当前对象是什么状态、现在能不能做”；`action_planning_agent` 先按可行性过滤，再根据任务目标、检测证据、处理权限和尝试次数动态计算 `priority_tier` 与 `dynamic_priority_score`，决定“先做什么、后做什么、失败后怎么办”。优先级、评分、计划顺序和失败策略不得写成 KG 属性。

`dynamic-waste-ros2` 负责 ROS2 消息、桥接、执行器和 bringup。ROS2 接收结构化命令，不接收 LLM 自由文本。

`dynamic-waste-ui` 负责人工复核、状态监控、风险确认和执行反馈可视化。

`dynamic-waste-sim` 负责仿真、数字孪生和离线回放。

推荐数据流：

```text
YOLO / RealSense / VLM
  -> perception_agent
  -> dynamic-waste-kg / KG graph_state
  -> dynamic-waste-agent supervisor_agent + risk_gate + action_planning_agent
  -> human_control_gate 或 execution_agent
  -> dynamic-waste-ros2
  -> 机械臂或仿真
  -> 执行反馈
  -> dynamic-waste-kg
```

## 5. 权威文档顺序

只读取当前任务需要的文档。优先顺序：

1. `AGENTS.md`
2. `README.md`
3. `subprojects/README.md`
4. `subprojects/dynamic-waste-kg/README.md`
5. `subprojects/dynamic-waste-kg/docs/README.md`
6. `subprojects/dynamic-waste-kg/docs/knowledge_seed_zh.md`
7. 相关源码和测试

判断当前系统事实时优先看：

```text
subprojects/dynamic-waste-kg/wastekg/core/taxonomy.py
subprojects/dynamic-waste-kg/wastekg/core/knowledge_base.py
subprojects/dynamic-waste-kg/wastekg/interfaces/contracts.py
subprojects/dynamic-waste-kg/docs/knowledge_seed_zh.md
```

冲突优先级：

```text
当前代码和测试
  > knowledge_seed_zh.md
  > 子项目 README
  > docs/README.md
  > paper_experiments/protocols/
  > 历史记录和论文草稿
```

## 6. 文档归属

```text
subprojects/dynamic-waste-kg/docs/
  只放当前主线和关键说明。

subprojects/dynamic-waste-kg/datasets/docs/
  放数据来源、数据合并、数据清洗、数据审计和中间数据处理说明。
  datasets/ 大数据被 git 忽略，但 datasets/docs/ 可提交。

subprojects/dynamic-waste-kg/paper_experiments/docs/
  放小论文补充实验文档，例如 e0、e1、e2、e3、e4 相关解释、审核总结和论文证据说明。

subprojects/dynamic-waste-kg/docs/archive/
  放历史稿、失败尝试、过期方案和不再作为当前依据的旧说明。
```

迁移文档时必须同步更新 README、索引和引用路径。不要把中间实验文件嵌入 README、AGENTS、架构设计或智能体 prompt。

## 7. 常用命令

进入知识图谱子项目：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

查看 Git 状态：

```powershell
cd C:\Users\12279\Documents\multiagent
git status --short --branch
```

## 8. 编码规范

- 核心库代码放在 `subprojects/dynamic-waste-kg/wastekg/` 的领域子包中。
- 脚本只作为命令行入口，放在 `subprojects/dynamic-waste-kg/scripts/` 的分类子目录中。
- 测试放在 `subprojects/dynamic-waste-kg/tests/`。
- 小论文专用实验放在 `subprojects/dynamic-waste-kg/paper_experiments/`。
- 不要提交数据集、YOLO outputs、模型权重、生成产物、`.venv` 或本地密钥。
- 不要提交 `subprojects/dynamic-waste-kg/wastekg/local_llm_config.py`。
- 优先复用现有 dataclass 和接口，不要随意新建 ad hoc 字典协议。
- 修改类别体系时，必须同步检查代码、测试和当前知识文档。

## 9. 安全边界

当前已验证范围是：

```text
受控二维实例分割 -> 可审计知识状态原型
```

不要声称当前仓库已经证明真实机械臂抓取成功、完整 ROS2 闭环执行、施工现场长期自主运行或危险废弃物处置已被验证。未来 ROS2 工作必须包含确认门控、失败处理、急停假设和高风险人工复核。
