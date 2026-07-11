// 本文件验证 UI 的人工复核、ROS2 门控和 4 Agent + 2 节点边界。
import { describe, expect, it } from "vitest";
import { agentTraceRuns } from "../data/mockDashboard";
import { buildRos2CommandPreview, canSendToRos2, deriveReviewQueue, getConnectedGraphNodeIds, getFeedbackLoopNodeIds, getNestedTraceChildren, getRetryTraceNodes, type WasteInstance } from "./dashboard";

const autoBrick: WasteInstance = {
  instance_id: "brick_01", candidate_class: "brick", yolo_confidence: 0.9, recognition_status: "accepted", bbox_2d: [0,0,10,10], mask_ref: "m.png", crop_ref: "c.png",
  center_xyz_camera: [0,0,0.4], depth_valid_ratio: 0.8, observed_extent_3d: [0.1,0.1,0.1], occlusion_state: "none", vlm_consistency: "not_checked",
  current_handling_policy: "auto_allowed", task_status: "pending", attempt_count: 0,
};
const reviewGlass: WasteInstance = { ...autoBrick, instance_id: "glass_01", candidate_class: "glass", recognition_status: "review_required", current_handling_policy: "human_review_required", occlusion_state: "partial" };
const unknownObject: WasteInstance = { ...autoBrick, instance_id: "unknown_01", candidate_class: "foam", recognition_status: "unknown", current_handling_policy: "robot_forbidden", vlm_consistency: "conflict", attempt_count: 1 };

describe("dashboard logic", () => {
  it("allows ROS2 only for accepted auto-allowed objects with usable depth and occlusion", () => {
    expect(canSendToRos2(autoBrick)).toBe(true);
    expect(canSendToRos2(reviewGlass)).toBe(false);
    expect(canSendToRos2({ ...autoBrick, depth_valid_ratio: 0.2 })).toBe(false);
    expect(canSendToRos2({ ...autoBrick, occlusion_state: "partial" })).toBe(false);
    expect(canSendToRos2({ ...autoBrick, occlusion_state: "unknown" })).toBe(false);
    expect(canSendToRos2({ ...autoBrick, task_status: "processing" })).toBe(false);
    expect(canSendToRos2({ ...autoBrick, attempt_count: 2 })).toBe(false);
  });

  it("derives review queue from recognition, permission and VLM conflict", () => {
    const queue = deriveReviewQueue([autoBrick, reviewGlass, unknownObject]);
    expect(queue.map((item) => item.instance_id)).toEqual(["glass_01", "unknown_01"]);
    expect(queue[1].review_reasons).toContain("vlm_conflict");
  });

  it("builds ROS2 preview with document-defined gates", () => {
    expect(buildRos2CommandPreview(autoBrick).status).toBe("ready_for_ros2_bridge");
    expect(buildRos2CommandPreview(reviewGlass).status).toBe("blocked_by_policy");
    expect(buildRos2CommandPreview(autoBrick).gate).toHaveProperty("recognition_status");
    expect(buildRos2CommandPreview(autoBrick).gate).not.toHaveProperty("grasp");
  });

  it("finds graph neighbours", () => {
    expect(getConnectedGraphNodeIds([{ from: "scene", to: "brick_01" }, { from: "brick_01", to: "brick" }], "brick_01")).toEqual(new Set(["brick_01", "scene", "brick"]));
  });

  it("keeps exactly four real agents and no value function", () => {
    const agents = agentTraceRuns.filter((run) => run.runType === "agent" && !run.retryOf).map((run) => run.id);
    expect(agents).toEqual(expect.arrayContaining(["supervisor_agent", "perception_agent", "action_planning_agent", "execution_agent"]));
    expect(agentTraceRuns.map((run) => run.id)).not.toContain("value_function");
    expect(agentTraceRuns.map((run) => run.id)).toEqual(expect.arrayContaining(["kg_writer_perception", "human_review_interrupt"]));
    expect(agentTraceRuns.map((run) => run.id)).not.toContain("risk_gate");
  });

  it("keeps retry and feedback trace structure", () => {
    const trace = [
      { id: "run", parentId: null, retryOf: null, phase: "root" },
      { id: "perception", parentId: "run", retryOf: null, phase: "agent" },
      { id: "retry", parentId: "perception", retryOf: "review", phase: "retry" },
      { id: "feedback", parentId: "run", retryOf: null, phase: "feedback" },
    ];
    expect(getNestedTraceChildren(trace, "run")).toHaveLength(2);
    expect(getRetryTraceNodes(trace).map((node) => node.id)).toEqual(["retry"]);
    expect(getFeedbackLoopNodeIds(trace)).toEqual(new Set(["feedback"]));
  });
});
