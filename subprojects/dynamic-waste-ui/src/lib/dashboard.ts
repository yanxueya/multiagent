// 本文件定义与 Word 版 KG 规范一致的 UI 实例状态、人工复核和 ROS2 门控。
export type RecognitionStatus = "accepted" | "review_required" | "unknown";
export type HandlingPolicy = "auto_allowed" | "human_review_required" | "robot_forbidden";
export type TaskStatus = "pending" | "processing" | "completed" | "failed";
export type VlmConsistencyStatus = "support" | "conflict" | "not_checked";

export interface WasteInstance {
  instance_id: string;
  candidate_class: string;
  yolo_confidence: number;
  recognition_status: RecognitionStatus;
  bbox_2d: number[] | null;
  mask_ref: string;
  crop_ref: string;
  center_xyz_camera: number[];
  depth_valid_ratio: number;
  observed_extent_3d: number[];
  occlusion_state: "none" | "partial" | "unknown";
  vlm_consistency: VlmConsistencyStatus;
  current_handling_policy: HandlingPolicy;
  task_status: TaskStatus;
  attempt_count: number;
}

export interface ReviewQueueItem extends WasteInstance { review_reasons: string[]; }
export interface KgConnectionInput { hasJsonSnapshot: boolean; hasLiveApi: boolean; }
export interface KgConnectionSummary { status: "live_ready" | "snapshot_ready" | "not_ready"; label: string; nextStep: string; }
export interface GraphEdgeLike { from: string; to: string; }
export type DashboardView = "overview" | "trace" | "sim" | "kg" | "review" | "ros2" | "dataset";
export type DashboardPanel = "trace" | "sim" | "kg" | "review" | "backend" | "dataset";
export interface TraceNodeLike { id: string; parentId: string | null; retryOf: string | null; phase: string; }

export interface Ros2CommandPreview {
  bridge: "dynamic_waste_ros2";
  command_type: "PickAndPlaceRequest";
  status: "ready_for_ros2_bridge" | "blocked_by_human_gate";
  target_instance_id: string;
  frame_id: "camera_color_optical_frame";
  gate: {
    recognition_status: boolean;
    handling_policy: boolean;
    task_status: boolean;
    depth: boolean;
    occlusion: boolean;
    retry: boolean;
  };
  constraints: {
    require_recognition_status: "accepted";
    require_handling_policy: "auto_allowed";
    require_depth_valid_ratio_min: 0.3;
    require_occlusion_not: "partial";
    require_attempt_count_lt: 2;
  };
}

export function canSendToRos2(instance: WasteInstance): boolean {
  return (
    instance.recognition_status === "accepted" &&
    instance.current_handling_policy === "auto_allowed" &&
    ["pending", "processing"].includes(instance.task_status) &&
    instance.depth_valid_ratio >= 0.3 &&
    instance.occlusion_state !== "partial" &&
    instance.attempt_count < 2
  );
}

export function deriveReviewQueue(instances: WasteInstance[]): ReviewQueueItem[] {
  return instances.map((instance) => ({ ...instance, review_reasons: getReviewReasons(instance) })).filter((instance) => instance.review_reasons.length > 0);
}

export function resolveInstanceIdFromGraphNode(graphNodeId: string, instances: WasteInstance[]): string | undefined {
  return instances.some((instance) => instance.instance_id === graphNodeId) ? graphNodeId : undefined;
}

export function getConnectedGraphNodeIds(edges: GraphEdgeLike[], selectedNodeId: string): Set<string> {
  const connected = new Set<string>([selectedNodeId]);
  for (const edge of edges) {
    if (edge.from === selectedNodeId) connected.add(edge.to);
    if (edge.to === selectedNodeId) connected.add(edge.from);
  }
  return connected;
}

export function buildRos2CommandPreview(instance: WasteInstance): Ros2CommandPreview {
  const gate = {
    recognition_status: instance.recognition_status === "accepted",
    handling_policy: instance.current_handling_policy === "auto_allowed",
    task_status: ["pending", "processing"].includes(instance.task_status),
    depth: instance.depth_valid_ratio >= 0.3,
    occlusion: instance.occlusion_state !== "partial",
    retry: instance.attempt_count < 2,
  };
  return {
    bridge: "dynamic_waste_ros2",
    command_type: "PickAndPlaceRequest",
    status: Object.values(gate).every(Boolean) ? "ready_for_ros2_bridge" : "blocked_by_human_gate",
    target_instance_id: instance.instance_id,
    frame_id: "camera_color_optical_frame",
    gate,
    constraints: {
      require_recognition_status: "accepted",
      require_handling_policy: "auto_allowed",
      require_depth_valid_ratio_min: 0.3,
      require_occlusion_not: "partial",
      require_attempt_count_lt: 2,
    },
  };
}

export function getNestedTraceChildren<T extends TraceNodeLike>(trace: T[], parentId: string): T[] { return trace.filter((node) => node.parentId === parentId); }
export function getRetryTraceNodes<T extends TraceNodeLike>(trace: T[]): T[] { return trace.filter((node) => Boolean(node.retryOf) || node.phase === "retry"); }
export function getFeedbackLoopNodeIds<T extends TraceNodeLike>(trace: T[]): Set<string> {
  const feedbackIds = new Set(trace.filter((node) => node.phase === "feedback").map((node) => node.id));
  let changed = true;
  while (changed) {
    changed = false;
    for (const node of trace) {
      if (node.parentId && feedbackIds.has(node.parentId) && !feedbackIds.has(node.id)) { feedbackIds.add(node.id); changed = true; }
    }
  }
  return feedbackIds;
}

export function isPanelVisibleForView(view: DashboardView, panel: DashboardPanel): boolean {
  if (view === "overview") return true;
  const visiblePanels: Record<Exclude<DashboardView, "overview">, DashboardPanel[]> = {
    trace: ["backend", "trace"], sim: ["backend", "sim", "kg"], kg: ["backend", "kg"],
    review: ["backend", "review", "kg"], ros2: ["backend", "review"], dataset: ["backend", "dataset"],
  };
  return visiblePanels[view].includes(panel);
}

export function summarizeKgConnectionMode(input: KgConnectionInput): KgConnectionSummary {
  if (input.hasLiveApi) return { status: "live_ready", label: "可实时接入 API", nextStep: "对齐事件流 schema" };
  if (input.hasJsonSnapshot) return { status: "snapshot_ready", label: "已接入 JSON 快照", nextStep: "补充实时事件 API" };
  return { status: "not_ready", label: "等待 KG 导出", nextStep: "先导出三层 KG 快照" };
}

function getReviewReasons(instance: WasteInstance): string[] {
  const reasons: string[] = [];
  if (instance.recognition_status !== "accepted") reasons.push(`recognition_status=${instance.recognition_status}`);
  if (instance.current_handling_policy !== "auto_allowed") reasons.push(`handling_policy=${instance.current_handling_policy}`);
  if (instance.vlm_consistency === "conflict") reasons.push("vlm_conflict");
  if (instance.occlusion_state === "partial") reasons.push("occlusion_partial");
  if (instance.attempt_count >= 2) reasons.push("attempt_count_limit");
  return Array.from(new Set(reasons));
}
