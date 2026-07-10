# human_control_gate

这是人工控制门控组件，不是智能体。

## 职责
承接 high risk、unknown、VLM conflict、低深度有效率、失败次数过多等对象的人工确认流程。

## 边界
- 不自动批准机器人动作。
- 不修改长期知识层。
- 人工确认结果应以 `HumanReviewEvent` 形式回写 KG。
