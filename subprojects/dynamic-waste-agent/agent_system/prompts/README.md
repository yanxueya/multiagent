# 多智能体 Prompt 与确定性契约

本目录严格区分 Agent Prompt、非智能体图节点契约和专用模型 Prompt。

```text
prompts/
  agents/
    supervisor.md          # 三模式条件路由
    perception.md          # YOLO/VLM/D435i 感知组织
    action_planning.md     # 单步规划与字典序
    execution.md           # 相机采集与受约束动作执行
  components/
    kg_writer.md           # 确定性 KG 写入契约，不调用 LLM
    human_review_interrupt.md  # interrupt/Command(resume) 契约
  modules/
    vlm_reviewer.md        # 六项视觉属性一致性复核
```

当前图只有：

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

KG 查询、候选加载、资格校验、相机、YOLO、VLM、D435i、MoveIt 和 ROS2 bridge 都是 Agent 调用的工具或服务，不额外包装成图节点。

核心闭环：

```text
Execute one action
  -> acquire a new Scene
  -> perceive
  -> KG Writer
  -> Supervisor
  -> plan one action again
```

旧的根级 Prompt 兼容文件已删除，避免重复入口和错误引用。
