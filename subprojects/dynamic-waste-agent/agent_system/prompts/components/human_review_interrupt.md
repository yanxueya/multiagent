# Human Review Interrupt Contract

`human_review_interrupt` 是确定性 LangGraph 节点，不是 Agent。

节点调用 `interrupt(payload)` 暂停当前 `thread_id`，等待 UI 使用 `Command(resume=...)` 恢复。interrupt 之前不得执行写库或机器人副作用，因为恢复时节点会从开头重新执行。

## 展示载荷

```text
instance_id
crop_ref
YOLO candidate relation
yolo_confidence
VLM 六项视觉属性
vlm_consistency
对应 visual_prototype
risk_level
fragility
graspability_prior
```

## 允许人工动作

```text
confirm_existing
mark_unknown
approve_robot
forbid_robot
discard_detection
```

`discard_detection` 表示人工确认候选为误检：KG Writer 将其移出当前 Scene 和规划候选，但保留事件到该实例的历史审计证据；不得新增 `rejected` 属性，也不得把它标记成抓取 `completed`。

## Resume 载荷

```json
{
  "instance_id": "obj_001",
  "review_action": "confirm_existing | mark_unknown | approve_robot | forbid_robot | discard_detection",
  "confirmed_category": "brick",
  "reason": ""
}
```

恢复结果只生成 HumanReviewEvent 写入请求，由 KG Writer 校验和提交。节点不得直接修改 KG。
