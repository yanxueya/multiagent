# E3 分层知识状态与保守路由

## 目的

回答 RQ3 的第一部分：分层知识状态是否能把 YOLO/VLM 输出转换成可审计的任务语义，例如自动候选、监督候选或人工复核。

## 路由标签

- `AUTO_CANDIDATE`：可作为自动处理候选。
- `SUPERVISED_CANDIDATE`：可进入监督处理或后续规划，但不应直接宣称全自动。
- `HUMAN_REVIEW_REQUIRED`：需要人工复核或人工处理。

## 关键规则

- `human_only` 和 `human_review` 类别必须进入 `HUMAN_REVIEW_REQUIRED`。
- 高风险类别必须进入 `HUMAN_REVIEW_REQUIRED`。
- VLM uncertain、API 错误、schema 错误和低置信度必须进入 `HUMAN_REVIEW_REQUIRED`。
- `robot_with_supervision` 类别进入 `SUPERVISED_CANDIDATE`。
- 只有高置信度、`robot_grasp`、`auto_processable=true` 且非高风险对象才进入 `AUTO_CANDIDATE`。

## 指标

- Policy Consistency Rate
- Restriction Recall
- Unsafe Automation Rate
- Over-conservative Rate
- Human Escalation Rate

生成命令：

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e3_policy_routing.py
```
