// 本文件提供 UI 原型的 mock 运行数据，字段对齐 KG 快照和 LangGraph 状态输出。
import type { WasteInstance } from "../lib/dashboard";

export interface AgentTraceNode {
  id: string;
  title: string;
  subtitle: string;
  status: "done" | "review" | "waiting" | "blocked";
  metric: string;
  input: string;
  output: string;
  decision: string;
  linkedInstanceIds: string[];
}

export interface AgentTraceRun {
  id: string;
  parentId: string | null;
  retryOf: string | null;
  title: string;
  runType: "chain" | "agent" | "component" | "tool" | "gate" | "bridge";
  phase: "root" | "agent" | "component" | "tool" | "gate" | "retry" | "feedback";
  status: "success" | "waiting" | "blocked" | "retry";
  startMs: number;
  durationMs: number;
  input: string;
  output: string;
  linkedInstanceIds: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "instance" | "category" | "scene" | "unknown_sample" | "unknown_cluster" | "event";
  x: number;
  y: number;
  description: string;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export const runStatus = {
  task: "建筑废弃物分拣任务",
  mode: "Review gated",
  camera: "D435i online",
  ros2: "standby",
  gpu: "idle",
};

export const agentTrace: AgentTraceNode[] = [
  {
    id: "supervisor",
    title: "Supervisor Agent",
    subtitle: "workflow control",
    status: "done",
    metric: "4 agents",
    input: "objective, user intent, current run state",
    output: "next workflow step and audit trail",
    decision: "总体规划智能体只负责目标分解、调度和重规划触发，不写 KG 属性、不生成 ROS2 命令。",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_03"],
  },
  {
    id: "perception",
    title: "Perception Agent",
    subtitle: "YOLO + VLM + RGB-D",
    status: "done",
    metric: "3 instances",
    input: "RGB image, depth frame, YOLO proposal_conf=0.05, VLM checks",
    output: "structured perception_events",
    decision: "感知智能体只组织候选和属性证据，不决定最终类别或抓取顺序。",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_03"],
  },
  {
    id: "kg_state",
    title: "KG State Projection",
    subtitle: "knowledge graph state",
    status: "done",
    metric: "component",
    input: "perception_events and KG snapshot",
    output: "graph_state predicates",
    decision: "知识图谱以 KG state 形式提供长期知识、短期实例和事件日志，只回答现在能不能做，不是 agent。",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_03"],
  },
  {
    id: "risk_gate",
    title: "Risk Gate",
    subtitle: "safety policy",
    status: "review",
    metric: "2 holds",
    input: "graph_state, category risk, handling policy, attempt_count",
    output: "risk_assessments and human review holds",
    decision: "风险门控是确定性组件，不是 agent；高风险、unknown 和 VLM 冲突不能直接进入 ROS2。",
    linkedInstanceIds: ["glass_02", "unknown_03"],
  },
  {
    id: "action_planner",
    title: "Action Planning Agent",
    subtitle: "ordered actions",
    status: "waiting",
    metric: "1 ready",
    input: "graph_state, risk gate, robot capabilities",
    output: "ordered plan, deferred targets, failure policy",
    decision: "行动规划智能体决定先做什么、后做什么、失败后怎么办，但不直接控制硬件。",
    linkedInstanceIds: ["wood_01"],
  },
  {
    id: "human_gate",
    title: "Human Control Gate",
    subtitle: "manual confirmation",
    status: "review",
    metric: "2 pending",
    input: "recognition_status=review_required or unknown instances",
    output: "approve, reject, keep blocked, or request relabeling",
    decision: "人工控制是明确门控，不是智能体；确认结果以事件形式回写 KG。",
    linkedInstanceIds: ["glass_02", "unknown_03"],
  },
  {
    id: "execution",
    title: "Execution Agent",
    subtitle: "ROS2 bridge wrapper",
    status: "waiting",
    metric: "schema only",
    input: "approved structured execution_request",
    output: "PickAndPlaceRequest preview",
    decision: "执行智能体只封装结构化 ROS2 请求，不接收 LLM 自由文本命令。",
    linkedInstanceIds: ["wood_01"],
  },
];

export const agentTraceRuns: AgentTraceRun[] = [
  {
    id: "waste_sorting_task",
    parentId: null,
    retryOf: null,
    title: "建筑废弃物分拣任务规划",
    runType: "chain",
    phase: "root",
    status: "waiting",
    startMs: 0,
    durationMs: 980,
    input: "objective=recover safe recyclable objects",
    output: "wood_01 ready; glass_02 and unknown_01 gated",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "supervisor_agent",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "supervisor_agent",
    runType: "agent",
    phase: "agent",
    status: "success",
    startMs: 12,
    durationMs: 52,
    input: "objective + current run state",
    output: "dispatch perception_agent, then KG state projection",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "perception_agent",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "perception_agent",
    runType: "agent",
    phase: "agent",
    status: "success",
    startMs: 78,
    durationMs: 122,
    input: "RGB + depth + YOLO proposal_conf=0.05",
    output: "3 active instances, 2 review candidates",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "vlm_review_tool",
    parentId: "perception_agent",
    retryOf: null,
    title: "vlm_review_tool",
    runType: "tool",
    phase: "tool",
    status: "blocked",
    startMs: 122,
    durationMs: 62,
    input: "glass crop, YOLO class=glass conf=0.42",
    output: "insufficient visual evidence",
    linkedInstanceIds: ["glass_02"],
  },
  {
    id: "vlm_review_retry_1",
    parentId: "perception_agent",
    retryOf: "vlm_review_tool",
    title: "vlm_review_tool retry #1",
    runType: "tool",
    phase: "retry",
    status: "retry",
    startMs: 196,
    durationMs: 46,
    input: "same crop with stricter attribute schema",
    output: "still insufficient -> keep review_required",
    linkedInstanceIds: ["glass_02"],
  },
  {
    id: "kg_state_projection",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "kg_state_projection",
    runType: "component",
    phase: "component",
    status: "success",
    startMs: 252,
    durationMs: 82,
    input: "perception_events + KG snapshot",
    output: "graph_state projected for 3 instances",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "risk_gate",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "risk_gate",
    runType: "gate",
    phase: "gate",
    status: "blocked",
    startMs: 410,
    durationMs: 76,
    input: "graph_state + category policy + failure history",
    output: "glass_02 and unknown_01 require human review",
    linkedInstanceIds: ["glass_02", "unknown_01"],
  },
  {
    id: "action_planning_agent",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "action_planning_agent",
    runType: "agent",
    phase: "agent",
    status: "success",
    startMs: 500,
    durationMs: 96,
    input: "graph_state + risk_assessments",
    output: "compute dynamic priority, then plan wood_01 first",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "human_control_gate",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "human_control_gate",
    runType: "gate",
    phase: "gate",
    status: "waiting",
    startMs: 612,
    durationMs: 154,
    input: "recognition_status=review_required or unknown instances",
    output: "waiting for explicit user action",
    linkedInstanceIds: ["glass_02", "unknown_01"],
  },
  {
    id: "execution_agent",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "execution_agent",
    runType: "agent",
    phase: "agent",
    status: "waiting",
    startMs: 784,
    durationMs: 52,
    input: "first approved executable plan step",
    output: "wrap as structured bridge request",
    linkedInstanceIds: ["wood_01"],
  },
  {
    id: "ros2_bridge",
    parentId: "execution_agent",
    retryOf: null,
    title: "ros2_bridge",
    runType: "bridge",
    phase: "component",
    status: "waiting",
    startMs: 842,
    durationMs: 36,
    input: "structured execution_request",
    output: "PickAndPlaceRequest preview for wood_01",
    linkedInstanceIds: ["wood_01"],
  },
  {
    id: "feedback_update",
    parentId: "waste_sorting_task",
    retryOf: null,
    title: "feedback_update",
    runType: "component",
    phase: "feedback",
    status: "waiting",
    startMs: 870,
    durationMs: 72,
    input: "execution result or human review event",
    output: "append EventLog and trigger replanning when needed",
    linkedInstanceIds: ["wood_01", "glass_02", "unknown_01"],
  },
  {
    id: "replan_after_failure",
    parentId: "feedback_update",
    retryOf: "action_planning_agent",
    title: "action_planning_agent retry after failure",
    runType: "agent",
    phase: "retry",
    status: "retry",
    startMs: 926,
    durationMs: 42,
    input: "attempt_count incremented or review result changed",
    output: "recompute next executable step",
    linkedInstanceIds: ["wood_01"],
  },
];

export const instances: WasteInstance[] = [
  {
    instance_id: "wood_01",
    candidate_class: "wood",
    recognition_status: "accepted",
    current_handling_policy: "auto_allowed",
    task_status: "pending",
    attempt_count: 0,
    bbox_2d: [120, 180, 260, 260],
    mask_ref: "masks/wood_01.png",
    crop_ref: "crops/wood_01.png",
    center_xyz_camera: [0.1, 0.1, 0.3],
    depth_valid_ratio: 0.78,
    observed_extent_3d: [0.2, 0.1, 0.05],
    occlusion_state: "none",
    yolo_confidence: 0.86,
    vlm_consistency: "not_checked",
  },
  {
    instance_id: "glass_02",
    candidate_class: "glass",
    recognition_status: "review_required",
    current_handling_policy: "human_review_required",
    task_status: "pending",
    attempt_count: 0,
    bbox_2d: [300, 180, 380, 250],
    mask_ref: "masks/glass_02.png",
    crop_ref: "crops/glass_02.png",
    center_xyz_camera: [0.2, 0.1, 0.3],
    depth_valid_ratio: 0.64,
    observed_extent_3d: [0.1, 0.08, 0.02],
    occlusion_state: "partial",
    yolo_confidence: 0.42,
    vlm_consistency: "not_checked",
  },
  {
    instance_id: "unknown_01",
    candidate_class: "foam",
    recognition_status: "unknown",
    current_handling_policy: "robot_forbidden",
    task_status: "pending",
    attempt_count: 1,
    bbox_2d: [420, 190, 500, 260],
    mask_ref: "masks/unknown_01.png",
    crop_ref: "crops/unknown_01.png",
    center_xyz_camera: [0.3, 0.1, 0.3],
    depth_valid_ratio: 0.51,
    observed_extent_3d: [0.08, 0.08, 0.05],
    occlusion_state: "unknown",
    yolo_confidence: 0.11,
    vlm_consistency: "conflict",
  },
];

export const graphNodes: GraphNode[] = [
  { id: "scene_001", label: "Scene: scene_001", kind: "scene", x: 50, y: 50, description: "当前 RGB-D 场景观测。" },
  { id: "wood_01", label: "wood_01", kind: "instance", x: 58, y: 78, description: "ObjectInstance：accepted / auto_allowed。" },
  { id: "glass_02", label: "glass_02", kind: "instance", x: 178, y: 108, description: "ObjectInstance：review_required。" },
  { id: "unknown_01", label: "unknown_01", kind: "instance", x: 88, y: 212, description: "ObjectInstance：unknown / robot_forbidden。" },
  { id: "cat_wood", label: "WasteCategory: wood", kind: "category", x: 250, y: 56, description: "长期类别先验。" },
  { id: "cat_glass", label: "WasteCategory: glass", kind: "category", x: 308, y: 168, description: "长期类别先验。" },
  { id: "unknown_sample_001", label: "UnknownSample", kind: "unknown_sample", x: 338, y: 276, description: "未知样本记录。" },
  { id: "event_detection_01", label: "DetectionEvent", kind: "event", x: 404, y: 82, description: "YOLO 检测事件。" },
];

export const graphEdges: GraphEdge[] = [
  { from: "scene_001", to: "wood_01" },
  { from: "scene_001", to: "glass_02" },
  { from: "scene_001", to: "unknown_01" },
  { from: "wood_01", to: "cat_wood" },
  { from: "glass_02", to: "cat_glass" },
  { from: "unknown_01", to: "unknown_sample_001" },
  { from: "event_detection_01", to: "wood_01" },
];
