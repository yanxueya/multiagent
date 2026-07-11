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
interface KgUnknownSampleRecord { sample_id?: string; crop_ref?: string; mask_ref?: string; yolo_topk?: Record<string, number>; vlm_attributes?: Record<string, unknown>; review_status?: string; human_label?: string | null; }
interface KgUnknownClusterRecord { cluster_id?: string; member_count?: number; prototype_attributes?: Record<string, unknown>; representative_crop_ref?: string; review_status?: string; candidate_category_name?: string | null; }
interface KgEdgeRecord { source_id?: string; target_id?: string; relation?: string; }
interface KgEventRecord { event_id?: string; event_type?: string; event_source?: string; event_time?: string; [key: string]: unknown; }
interface KgEventDefinitionRecord { source?: string; attributes?: string[]; trigger?: string; preconditions?: string[]; relations?: string[]; effects?: string[]; }
interface KgSchemaRecord {
  node_fields?: Record<string, string[]>;
  category_attribute_enums?: Record<string, string[]>;
  instance_attribute_enums?: Record<string, string[]>;
  unknown_sample_review_statuses?: string[];
  event_definitions?: Record<string, KgEventDefinitionRecord>;
}

export interface KgSnapshot {
  categories?: Record<string, KgCategoryRecord>;
  scenes?: Record<string, KgSceneRecord>;
  instances?: Record<string, KgInstanceRecord>;
  unknown_samples?: Record<string, KgUnknownSampleRecord>;
  unknown_clusters?: Record<string, KgUnknownClusterRecord>;
  edges?: KgEdgeRecord[];
  events?: KgEventRecord[];
  schema?: KgSchemaRecord;
  provenance?: { evidence_level?: string; model_inference_used?: boolean; training_used?: boolean; };
}

export interface KgCategoryView extends KgCategoryRecord { category_name: string; }
export interface KgEventView { event_id: string; event_type: string; event_source: string; event_time: string; properties: Record<string, string | number | boolean | null>; }
export interface KgEventDefinitionView { event_type: string; source: string; attributes: string[]; trigger: string; preconditions: string[]; relations: string[]; effects: string[]; }
export interface KgSchemaView { nodeFields: Record<string, string[]>; categoryAttributeEnums: Record<string, string[]>; instanceAttributeEnums: Record<string, string[]>; unknownSampleReviewStatuses: string[]; }
export interface AdaptedKgDashboardData {
  source: "kg_snapshot";
  instances: WasteInstance[];
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  categories: KgCategoryView[];
  events: KgEventView[];
  eventDefinitions: KgEventDefinitionView[];
  schema: KgSchemaView;
  provenance: { evidenceLevel: string; modelInferenceUsed: boolean; trainingUsed: boolean; };
}

export function adaptKnowledgeGraphSnapshot(snapshot: KgSnapshot): AdaptedKgDashboardData {
  const edges = snapshot.edges ?? [];
  const instances = Object.entries(snapshot.instances ?? {}).map(([id, record]) => mapInstance(id, record, edges));
  return {
    source: "kg_snapshot",
    instances,
    graphNodes: buildGraphNodes(snapshot, instances),
    graphEdges: buildGraphEdges(snapshot),
    categories: buildCategories(snapshot),
    events: buildEvents(snapshot),
    eventDefinitions: buildEventDefinitions(snapshot),
    schema: {
      nodeFields: { ...(snapshot.schema?.node_fields ?? {}) },
      categoryAttributeEnums: { ...(snapshot.schema?.category_attribute_enums ?? {}) },
      instanceAttributeEnums: { ...(snapshot.schema?.instance_attribute_enums ?? {}) },
      unknownSampleReviewStatuses: [...(snapshot.schema?.unknown_sample_review_statuses ?? [])],
    },
    provenance: {
      evidenceLevel: String(snapshot.provenance?.evidence_level ?? "unspecified"),
      modelInferenceUsed: Boolean(snapshot.provenance?.model_inference_used),
      trainingUsed: Boolean(snapshot.provenance?.training_used),
    },
  };
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
  Object.entries(snapshot.categories ?? {}).forEach(([name, category]) => nodes.push({
    id: name, label: `WasteCategory: ${name}`, kind: "category", layer: "long_term", x: 0, y: 0,
    description: `${category.risk_level ?? "unknown"} risk / ${category.default_handling_policy ?? "unknown"}`,
    properties: displayProperties(category, schemaFields(snapshot, "WasteCategory")),
  }));
  Object.entries(snapshot.scenes ?? {}).forEach(([id, scene]) => nodes.push({ id, label: `Scene: ${id}`, kind: "scene", layer: "short_term", x: 0, y: 0, description: `观测时间 ${scene.captured_at ?? "unknown"}`, properties: displayProperties(scene, schemaFields(snapshot, "Scene")) }));
  instances.forEach((instance) => nodes.push({ id: instance.instance_id, label: instance.instance_id, kind: "instance", layer: "short_term", x: 0, y: 0, description: `${instance.recognition_status} / ${instance.current_handling_policy}`, properties: displayProperties(instance, schemaFields(snapshot, "ObjectInstance")) }));
  Object.entries(snapshot.unknown_samples ?? {}).forEach(([id, sample]) => nodes.push({ id, label: `UnknownSample: ${id}`, kind: "unknown_sample", layer: "short_term", x: 0, y: 0, description: "无法可靠分类的未知样本", properties: displayProperties(sample, schemaFields(snapshot, "UnknownSample")) }));
  Object.entries(snapshot.unknown_clusters ?? {}).forEach(([id, cluster]) => nodes.push({ id, label: `UnknownCluster: ${id}`, kind: "unknown_cluster", layer: "short_term", x: 0, y: 0, description: "相似未知样本聚类", properties: displayProperties(cluster, schemaFields(snapshot, "UnknownCluster")) }));
  buildEvents(snapshot).forEach((event) => nodes.push({ id: event.event_id, label: event.event_type, kind: "event", layer: "event_log", x: 0, y: 0, description: `事件来源：${event.event_source}`, properties: { event_time: event.event_time, event_source: event.event_source, ...event.properties } }));
  return nodes;
}

function buildGraphEdges(snapshot: KgSnapshot): GraphEdge[] {
  return (snapshot.edges ?? []).filter((edge) => edge.source_id && edge.target_id).map((edge) => ({ from: String(edge.source_id), to: String(edge.target_id), relation: String(edge.relation ?? "RELATED_TO") }));
}

function buildCategories(snapshot: KgSnapshot): KgCategoryView[] {
  return Object.entries(snapshot.categories ?? {}).map(([name, category]) => ({ ...category, category_name: String(category.category_name || name) }));
}

function buildEvents(snapshot: KgSnapshot): KgEventView[] {
  return (snapshot.events ?? []).map((event, index) => {
    const properties = displayProperties(event);
    delete properties.event_id;
    delete properties.event_type;
    delete properties.event_source;
    delete properties.event_time;
    return {
      event_id: String(event.event_id || `event_${index}`),
      event_type: String(event.event_type || "Event"),
      event_source: String(event.event_source || "unknown"),
      event_time: String(event.event_time || ""),
      properties,
    };
  });
}

function buildEventDefinitions(snapshot: KgSnapshot): KgEventDefinitionView[] {
  return Object.entries(snapshot.schema?.event_definitions ?? {}).map(([eventType, definition]) => ({
    event_type: eventType,
    source: String(definition.source ?? ""),
    attributes: [...(definition.attributes ?? [])],
    trigger: String(definition.trigger ?? ""),
    preconditions: [...(definition.preconditions ?? [])],
    relations: [...(definition.relations ?? [])],
    effects: [...(definition.effects ?? [])],
  }));
}

function schemaFields(snapshot: KgSnapshot, nodeType: string): string[] {
  return snapshot.schema?.node_fields?.[nodeType] ?? [];
}

function displayProperties(record: object, fields?: string[]): Record<string, string | number | boolean | null> {
  const source = record as Record<string, unknown>;
  const keys = fields?.length ? fields : Object.keys(source);
  const result: Record<string, string | number | boolean | null> = {};
  keys.forEach((key) => {
    const value = source[key];
    if (value === undefined || value === null) result[key] = null;
    else if (["string", "number", "boolean"].includes(typeof value)) result[key] = value as string | number | boolean;
    else result[key] = JSON.stringify(value);
  });
  return result;
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
