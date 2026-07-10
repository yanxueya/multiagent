// 本文件把文档规范的三层 KG 快照映射为 UI，不创造 KG 中不存在的属性或节点。
import type { GraphEdge, GraphNode } from "../data/mockDashboard";
import type { HandlingPolicy, RecognitionStatus, TaskStatus, VlmConsistencyStatus, WasteInstance } from "./dashboard";

interface KgCategoryRecord { category_name?: string; risk_level?: string; fragility?: string; graspability_prior?: string; vlm_review_policy?: string; default_handling_policy?: string; visual_prototype?: Record<string, string[]>; }
interface KgSceneRecord { scene_id?: string; captured_at?: string; rgb_ref?: string; depth_ref?: string; }
interface KgInstanceRecord {
  instance_id?: string; yolo_confidence?: number; recognition_status?: string; bbox_2d?: number[] | null;
  mask_ref?: string; crop_ref?: string; center_xyz_camera?: number[]; depth_valid_ratio?: number;
  observed_extent_3d?: number[]; occlusion_state?: string; vlm_consistency?: string;
  current_handling_policy?: string; task_status?: string; attempt_count?: number;
}
interface KgUnknownSampleRecord { sample_id?: string; review_status?: string; human_label?: string | null; }
interface KgUnknownClusterRecord { cluster_id?: string; member_count?: number; review_status?: string; candidate_category_name?: string | null; }
interface KgEdgeRecord { source_id?: string; target_id?: string; relation?: string; }
interface KgEventRecord { event_id?: string; event_type?: string; event_source?: string; }

export interface KgSnapshot {
  categories?: Record<string, KgCategoryRecord>;
  scenes?: Record<string, KgSceneRecord>;
  instances?: Record<string, KgInstanceRecord>;
  unknown_samples?: Record<string, KgUnknownSampleRecord>;
  unknown_clusters?: Record<string, KgUnknownClusterRecord>;
  edges?: KgEdgeRecord[];
  events?: KgEventRecord[];
}

export interface AdaptedKgDashboardData { source: "kg_snapshot"; instances: WasteInstance[]; graphNodes: GraphNode[]; graphEdges: GraphEdge[]; }

export function adaptKnowledgeGraphSnapshot(snapshot: KgSnapshot): AdaptedKgDashboardData {
  const edges = snapshot.edges ?? [];
  const instances = Object.entries(snapshot.instances ?? {}).map(([id, record]) => mapInstance(id, record, edges));
  return { source: "kg_snapshot", instances, graphNodes: buildGraphNodes(snapshot, instances), graphEdges: buildGraphEdges(snapshot) };
}

function mapInstance(fallbackId: string, record: KgInstanceRecord, edges: KgEdgeRecord[]): WasteInstance {
  const instanceId = String(record.instance_id || fallbackId);
  return {
    instance_id: instanceId,
    candidate_class: resolveCategory(instanceId, edges),
    yolo_confidence: numberFrom(record.yolo_confidence),
    recognition_status: normalizeRecognition(record.recognition_status),
    bbox_2d: Array.isArray(record.bbox_2d) ? record.bbox_2d.map(Number) : null,
    mask_ref: String(record.mask_ref || ""),
    crop_ref: String(record.crop_ref || ""),
    center_xyz_camera: vectorFrom(record.center_xyz_camera),
    depth_valid_ratio: numberFrom(record.depth_valid_ratio),
    observed_extent_3d: vectorFrom(record.observed_extent_3d),
    occlusion_state: normalizeOcclusion(record.occlusion_state),
    vlm_consistency: normalizeVlm(record.vlm_consistency),
    current_handling_policy: normalizePolicy(record.current_handling_policy),
    task_status: normalizeTask(record.task_status),
    attempt_count: numberFrom(record.attempt_count),
  };
}

function buildGraphNodes(snapshot: KgSnapshot, instances: WasteInstance[]): GraphNode[] {
  const nodes: GraphNode[] = [];
  Object.keys(snapshot.categories ?? {}).forEach((name, index) => nodes.push({ id: name, label: `WasteCategory: ${name}`, kind: "category", x: 0, y: 0, description: `长期类别知识：${name}` }));
  Object.entries(snapshot.scenes ?? {}).forEach(([id, scene]) => nodes.push({ id, label: `Scene: ${id}`, kind: "scene", x: 0, y: 0, description: `观测时间 ${scene.captured_at ?? "unknown"}` }));
  instances.forEach((instance) => nodes.push({ id: instance.instance_id, label: instance.instance_id, kind: "instance", x: 0, y: 0, description: `${instance.recognition_status} / ${instance.current_handling_policy}` }));
  Object.keys(snapshot.unknown_samples ?? {}).forEach((id) => nodes.push({ id, label: `UnknownSample: ${id}`, kind: "unknown_sample", x: 0, y: 0, description: "无法可靠分类的未知样本" }));
  Object.keys(snapshot.unknown_clusters ?? {}).forEach((id) => nodes.push({ id, label: `UnknownCluster: ${id}`, kind: "unknown_cluster", x: 0, y: 0, description: "相似未知样本聚类" }));
  (snapshot.events ?? []).forEach((event, index) => { const id = String(event.event_id || `event_${index}`); nodes.push({ id, label: event.event_type || "Event", kind: "event", x: 0, y: 0, description: `事件来源：${event.event_source ?? "unknown"}` }); });
  return nodes;
}

function buildGraphEdges(snapshot: KgSnapshot): GraphEdge[] {
  return (snapshot.edges ?? []).filter((edge) => edge.source_id && edge.target_id).map((edge) => ({ from: String(edge.source_id), to: String(edge.target_id) }));
}

function resolveCategory(instanceId: string, edges: KgEdgeRecord[]): string {
  const confirmed = edges.filter((edge) => edge.source_id === instanceId && edge.relation === "CONFIRMED_AS");
  if (confirmed.length && confirmed[confirmed.length - 1].target_id) return String(confirmed[confirmed.length - 1].target_id);
  const candidates = edges.filter((edge) => edge.source_id === instanceId && edge.relation === "CANDIDATE_OF");
  return candidates.length ? String(candidates[candidates.length - 1].target_id) : "unknown";
}

function normalizeRecognition(value: unknown): RecognitionStatus { return value === "accepted" || value === "unknown" ? value : "review_required"; }
function normalizePolicy(value: unknown): HandlingPolicy { return value === "auto_allowed" || value === "robot_forbidden" ? value : "human_review_required"; }
function normalizeTask(value: unknown): TaskStatus { return value === "processing" || value === "completed" || value === "failed" ? value : "pending"; }
function normalizeVlm(value: unknown): VlmConsistencyStatus { return value === "support" || value === "conflict" ? value : "not_checked"; }
function normalizeOcclusion(value: unknown): "none" | "partial" | "unknown" { return value === "none" || value === "partial" ? value : "unknown"; }
function numberFrom(value: unknown): number { return typeof value === "number" && Number.isFinite(value) ? value : 0; }
function vectorFrom(value: unknown): number[] { return Array.isArray(value) ? value.slice(0, 3).map((item) => Number(item) || 0) : [0, 0, 0]; }
