// 本文件验证三层 KG 快照到 UI 的无损映射。
import { describe, expect, it } from "vitest";
import { adaptKnowledgeGraphSnapshot } from "./kgAdapter";

const snapshot = {
  categories: { brick: { category_name: "brick", risk_level: "medium", fragility: "low", graspability_prior: "medium", vlm_review_policy: "threshold_based", default_handling_policy: "auto_allowed" } },
  scenes: { scene_001: { scene_id: "scene_001", captured_at: "2026-07-11T00:00:00Z" } },
  instances: {
    brick_01: { instance_id: "brick_01", yolo_confidence: 0.9, recognition_status: "accepted", bbox_2d: [1,2,3,4], center_xyz_camera: [0,0,0.4], depth_valid_ratio: 0.8, observed_extent_3d: [0.1,0.1,0.1], occlusion_state: "none", vlm_consistency: "not_checked", current_handling_policy: "auto_allowed", task_status: "pending", attempt_count: 0 },
    unknown_01: { instance_id: "unknown_01", yolo_confidence: 0.1, recognition_status: "unknown", center_xyz_camera: [0.2,0,0.4], depth_valid_ratio: 0.5, observed_extent_3d: [0.1,0.1,0.1], occlusion_state: "unknown", vlm_consistency: "conflict", current_handling_policy: "robot_forbidden", task_status: "pending", attempt_count: 0 },
  },
  unknown_samples: { unknown_sample_001: { sample_id: "unknown_sample_001", review_status: "pending" } },
  events: [{ event_id: "evt_1", event_type: "DetectionEvent", event_source: "yolo_detector", event_time: "2026-07-11T00:00:01Z", yolo_confidence: 0.9 }],
  schema: {
    category_attribute_enums: { graspability_prior: ["low", "medium", "high"] },
    instance_attribute_enums: { vlm_consistency: ["support", "conflict", "not_checked"], task_status: ["pending", "processing", "completed", "failed"] },
    unknown_sample_review_statuses: ["pending", "confirmed_existing", "confirmed_new", "rejected"],
    node_fields: {
      UnknownSample: ["sample_id", "crop_ref", "mask_ref", "yolo_topk", "vlm_attributes", "review_status", "human_label"],
    },
    event_definitions: {
      DetectionEvent: {
        source: "yolo_detector",
        attributes: ["yolo_confidence", "bbox_2d", "mask_ref", "crop_ref"],
        trigger: "candidate above proposal threshold",
        preconditions: ["Scene exists"],
        relations: ["DETECTED->ObjectInstance"],
        effects: ["create ObjectInstance"],
      },
    },
  },
  edges: [
    { source_id: "scene_001", relation: "CONTAINS", target_id: "brick_01" },
    { source_id: "brick_01", relation: "CANDIDATE_OF", target_id: "brick" },
    { source_id: "brick_01", relation: "CONFIRMED_AS", target_id: "brick" },
    { source_id: "unknown_01", relation: "CANDIDATE_OF", target_id: "brick" },
    { source_id: "unknown_01", relation: "RECORDED_AS", target_id: "unknown_sample_001" },
    { source_id: "evt_1", relation: "DETECTED", target_id: "brick_01" },
  ],
};

describe("adaptKnowledgeGraphSnapshot", () => {
  it("derives category from relations instead of instance property", () => {
    const data = adaptKnowledgeGraphSnapshot(snapshot);
    expect(data.instances.find((item) => item.instance_id === "brick_01")).toMatchObject({ candidate_class: "brick", recognition_status: "accepted", current_handling_policy: "auto_allowed" });
    expect(data.instances.find((item) => item.instance_id === "unknown_01")).toMatchObject({ candidate_class: "brick", recognition_status: "unknown", vlm_consistency: "conflict" });
  });

  it("maps scenes, categories, unknown samples and typed events without synthetic risk nodes", () => {
    const data = adaptKnowledgeGraphSnapshot(snapshot);
    expect(data.graphNodes.map((node) => node.id)).toEqual(expect.arrayContaining(["scene_001", "brick", "brick_01", "unknown_sample_001", "evt_1"]));
    expect(data.graphNodes.some((node) => node.kind === "scene")).toBe(true);
    expect(data.graphNodes.some((node) => node.kind === "unknown_sample")).toBe(true);
    expect(data.graphNodes.map((node) => node.kind)).not.toContain("risk");
    expect(data.categories[0]).toMatchObject({ category_name: "brick", risk_level: "medium" });
    expect(data.events[0]).toMatchObject({ event_type: "DetectionEvent", event_source: "yolo_detector", properties: { yolo_confidence: 0.9 } });
    expect(data.graphEdges.find((edge) => edge.from === "evt_1")).toMatchObject({ relation: "DETECTED", to: "brick_01" });
  });

  it("keeps schema fields visible when nullable values are absent", () => {
    const data = adaptKnowledgeGraphSnapshot(snapshot);
    const unknownSample = data.graphNodes.find((node) => node.id === "unknown_sample_001");
    expect(unknownSample?.properties).toMatchObject({ human_label: null, review_status: "pending" });
    expect(data.eventDefinitions[0]).toMatchObject({ event_type: "DetectionEvent", source: "yolo_detector" });
    expect(data.schema.categoryAttributeEnums.graspability_prior).toEqual(["low", "medium", "high"]);
  });
});
