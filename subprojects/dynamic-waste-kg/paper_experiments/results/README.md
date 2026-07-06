# 小论文实验结果索引

## 已固定证据

- E0 数据审计：`artifacts/e0_waste11_grouped_v1_r3`
- E1 分割测试：`artifacts/e1_test_evaluation_r2`
- E2 单图证据与失败回退：`artifacts/e2_visual_vlm_smoke_val_fallback_r2`
- E2 GLM-4.5V 单图视觉复核：`artifacts/e2_glm45v_single_image_smoke_r3`
- E2 GLM-4.5V 20 图小批量复核：`artifacts/paper/e2_vlm_glm45v_batch20_r3_focused`
- E3 保守任务路由：`artifacts/paper/e3_policy_routing`
- E4 软件事件回放：`artifacts/paper/e4_event_replay`
- E4 严格图片序列候选审查：`artifacts/paper/e4_image_sequence_candidates`

## E3 分层知识状态与保守路由

- 案例数：15
- Policy Consistency Rate：1.0000
- Restriction Recall：1.0000
- Unsafe Automation Rate：0.0000
- Human Escalation Rate：0.5333

解释：在当前保守策略库和受控案例中，敏感类别、低置信度和复核异常对象不会被自动路由。该实验不证明视觉模型永远不会误检，因此论文中仍需保留“依赖前端风险线索”的限制。

## E4 软件事件回放

- 案例数：32
- Instance Update Success Rate：1.0000
- Event Chain Completeness：1.0000
- State Version Consistency：1.0000
- Temporal Policy Consistency：1.0000

解释：该结果证明软件层面的短期状态和事件链可以被连续记录与复查，但不能写成真实机械臂抓取验证。

## E4 严格图片序列候选审查

- 输出目录：`artifacts/paper/e4_image_sequence_candidates`
- 候选审查图：`label_subset_strict_candidates.jpg`
- 放大候选图：`top_label_strict_candidates_large.jpg`
- 当前严格 before/after 移除对：未确认

解释：重新核实后，现有数据中的候选图片不能作为严格“移除前/移除后”论文证据。多数候选虽然满足标注数量减少，但视觉上存在物体替换、摆放变化、视角变化或形态变化。当前 E4 图片序列部分应标记为待补拍；已完成的 E4 证据仅限软件事件回放。

## E2 GLM-4.5V 20 图小批量复核

- 输出目录：`artifacts/paper/e2_vlm_glm45v_batch20_r3_focused`
- 图像数：20
- 检测目标数：18
- 触发复核目标数：17
- 有效 VLM 结构化响应数：13
- 有效 VLM 响应率：0.7647
- 人工复核目标数：9
- 平均端到端耗时：4.4690 秒/目标
- 决策分布：`agree=8`，`change=0`，`uncertain=5`，`review_error=4`，`not_reviewed=1`

解释：第三轮使用轻量证据模式，只发送 crop 和 mask overlay，并设置 5 秒请求间隔。剩余 4 个失败样本均为硅基流动 `HTTP 429 TPM limit reached`，不是本地图谱或 VLM 解析逻辑错误。论文中应将该结果写作小批量 smoke validation，而不是最终 VLM 性能评估。

## 当前结论边界

本文现阶段可以支撑“受控二维实例分割到可审计知识状态的原型验证”。在未接入 RealSense 深度、夹爪标定和 ROS2 执行前，不能写成真实机械臂自动分拣系统验证。
