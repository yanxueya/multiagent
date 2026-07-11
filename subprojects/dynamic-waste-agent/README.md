# dynamic-waste-agent

本子项目实现建筑废弃物系统的三模式 LangGraph 编排。它不维护 KG 领域事实、不训练模型，也不发送自由文本 ROS2 命令。

## 节点边界

```text
4 个 Agent
  supervisor_agent
  perception_agent
  action_planning_agent
  execution_agent

2 个确定性节点
  kg_writer
  human_review_interrupt
```

KG 查询、资格校验、相机、YOLO、VLM、D435i、MoveIt 和 ROS2 bridge 是工具或服务，不额外包装成图节点。

## 三种模式

| 模式 | 用途 | 主要流程 |
| --- | --- | --- |
| `exploration` | 当前环境探查或历史 KG 查询 | 相机/只读 KG -> Perception -> KG Writer -> complete |
| `supervised_execution` | 已知重复对象的监督自动执行 | 单步规划 -> 执行 -> 新 Scene -> 重规划 |
| `human_collaboration` | 混杂、不确定或高风险场景 | 感知 -> interrupt 人工审核 -> 单步执行 -> 新 Scene |

三种模式共用一张图。Supervisor 是条件路由器；安全规则仍由确定性条件边和 validator 强制执行。

## 滚动闭环

```text
START -> Supervisor
  -> acquire_scene -> Execution -> Perception -> KG Writer -> Supervisor
  -> human_review -> Human Review Interrupt -> KG Writer -> Supervisor
  -> plan -> Action Planner -> KG Writer -> Supervisor
  -> execute -> Execution -> KG Writer -> Supervisor
  -> complete / abort -> END
```

一次计划只包含一个动作。任何真实物理动作成功或失败后都必须令当前 Scene 失效，重新采集 RGB-D 后再规划。

## State 与 KG

LangGraph State 只保存 `operation_mode`、`user_goal`、`current_scene_id`、新鲜度、待复核/可执行 ID、当前单步计划、最近执行结果和 KG 引用。完整 WasteCategory、Scene、ObjectInstance、UnknownSample、事件和关系保存在 KG 中。

一个完整任务使用一个稳定 `thread_id`。当前默认使用 `InMemorySaver` 便于原型测试；接真实 UI/ROS2 前应换成持久化 checkpointer。

`agent_system.integrations.WasteKgRuntimeAdapter` 已把候选读取、历史查询、人工复核以及 perception/planning/human_review/execution 四类写入映射到真实内存 `KnowledgeGraph`。感知通过一次性 `observation_ref` 传递 Observation，写入后立即释放，不把完整 KG 或 Observation 放入 checkpoint。

## 规划规则

- 先做识别、处理权限、任务状态、尝试次数、深度和遮挡硬过滤。
- `failed` 不能直接重试，必须先形成新 Scene，重观测后恢复为 `pending`。
- 第一阶段按 depth、graspability、NEAR 数量、运动距离和 attempt_count 做字典序。
- `rank_candidates` 历史统计接口保留，但当前明确禁用。
- 不保存 `task_value` 或人工加权分数。

## Prompt

权威入口是 [agent_system/prompts/README.md](agent_system/prompts/README.md)。旧的根级兼容 Prompt 已删除。

## 运行

```powershell
cd C:\Users\12279\Documents\multiagent\subprojects\dynamic-waste-agent
.\.venv\Scripts\python.exe -m pip install -e ..\dynamic-waste-kg
.\.venv\Scripts\python.exe -m agent_system.graph
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

当前已实现编排、checkpointer、interrupt、schema、内存 KG 适配器、Neo4j 提交后镜像、UI 快照发布和跨子项目闭环测试；真实相机、持久化 LangGraph checkpointer、ROS2/MoveIt 和机械臂闭环仍待接入。
