# world_model_adapter

这是系统组件，不是智能体。

文件名 `world_model_adapter` 作为内部兼容名保留；它只适配知识图谱状态，不代表另有一个独立“世界模型”节点。

## 职责
从 dynamic-waste-kg 读取长期知识、短期实例记忆、关系和事件日志，投影为规划器可使用的 graph_state。

## 输出原则
- graph_state 回答“现在能不能尝试处理”。
- graph_state 携带 `recognition_status`、`current_handling_policy`、`task_status`、`attempt_count`、深度、遮挡和类别风险先验。
- graph_state 可以包含由 KG 事实派生的 `can_attempt_now`、`requires_review` 和可行性原因。
- graph_state 不包含规划优先级、评分或动作顺序。
