# dynamic-waste-ui

`dynamic-waste-ui` 是建筑废弃物机器人分拣系统的人工复核、状态监控、知识图谱可视化、LangGraph trace 和后续仿真接入界面子项目。

当前状态：已有 Vite + React + TypeScript 工作台原型。UI 已接入 `dynamic-waste-kg` 导出的 JSON snapshot；LangGraph trace、仿真和 ROS2 bridge 仍是前端预览/占位数据，尚未连接真实后端服务或真实硬件。

## 已实现原型

- LangGraph Trace：以接近 LangSmith 的 run tree / nested span / timeline 形式展示 `4 个 Agent + 2 个确定性节点 + 外部工具`。
- 4 个真正 agent：`supervisor_agent`、`perception_agent`、`action_planning_agent`、`execution_agent`。
- 两个确定性图节点：`kg_writer`、`human_review_interrupt`。
- 三种模式：`exploration`、`supervised_execution`、`human_collaboration`，可在顶部切换展示。
- Knowledge Graph State：从 `/data/kg-snapshot.json` 读取 KG 快照，展示长期知识层、短期实例层、事件日志层和 graph_state 谓词。
- Human Review Queue：根据 KG 实例状态派生高风险、unknown、VLM 冲突和需要人工复核的对象。
- Simulation / Digital Twin：预留 D435i、PiPER/机械臂、mask、bbox 和回放时间轴位置。
- ROS2 Bridge Preview：只展示结构化命令预览，不直接控制硬件。
- 左侧导航：Overview、Agent Trace、Simulation、Knowledge Graph、Human Review、ROS2 Bridge、Dataset 可以切换工作区。

## 如何运行

PowerShell 中建议使用 `npm.cmd`，避免 Windows 执行策略拦截 `npm.ps1`。

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-ui
npm.cmd install --cache .npm-cache
npm.cmd run dev -- --port 5173
```

打开：

```text
http://127.0.0.1:5173/
```

## 刷新知识图谱快照

UI 默认读取：

```text
subprojects/dynamic-waste-ui/public/data/kg-snapshot.json
```

由 KG 子项目导出：

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-kg
.\.venv\Scripts\python.exe scripts\graph\export_ui_snapshot.py --output ..\dynamic-waste-ui\public\data\kg-snapshot.json
```

注意：`unknown` 不会作为长期类别导出；它只作为短期实例状态进入 UI。

## 如何测试和构建

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-ui
npm.cmd test -- --run
npm.cmd run build
```

## 当前接入状态

```text
KG：已接入 JSON snapshot 文件；尚未接 live API。
LangGraph：UI trace 已按三模式、4 Agent、KG Writer、interrupt 和单步重规划展示，但仍是前端预览数据。
ROS2：UI 只做结构化命令预览；dynamic-waste-ros2 bridge 尚未接入真实执行。
Simulation：当前是占位/回放界面，等待后续接仿真环境。
```

## 工程边界

- 前端不实现核心知识图谱推理，只展示 KG 或 agent bridge 输出的结构化状态。
- 前端不直接控制 ROS2 硬件节点，只提交经过门控确认的结构化命令请求。
- 高风险类别、低置信度候选、unknown 状态和 VLM 冲突对象必须进入人工复核。
- `kg_writer` 和 `human_review_interrupt` 显示为确定性节点，不显示为 Agent；资格校验和 ROS2 bridge 显示为工具或服务。
- UI 不展示 `task_value` 或独立价值函数节点；规划优先级只显示为 `action_planning_agent` 的动态计算结果。
- 涉及模型训练时，界面可以展示操作指令和显存检查提示，但不在沙盒中启动训练。
