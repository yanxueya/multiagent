"""集中定义知识图谱字段枚举和 7.2 节的七类事件状态迁移。"""

from __future__ import annotations

from typing import Any, Final


CATEGORY_ATTRIBUTE_ENUMS: Final[dict[str, tuple[str, ...]]] = {
    "risk_level": ("low", "medium", "high"),
    "fragility": ("low", "medium", "high"),
    "graspability_prior": ("low", "medium", "high"),
    "vlm_review_policy": ("threshold_based", "always"),
    "default_handling_policy": ("auto_allowed", "human_confirmation_required"),
}

VISUAL_ATTRIBUTE_ENUMS: Final[dict[str, tuple[str, ...]]] = {
    "dominant_color": (
        "clear", "white", "light_gray", "gray", "dark_gray", "black", "brown",
        "yellow_brown", "red_brown", "yellow", "silver", "rust_brown",
        "light_green", "light_blue", "mixed", "unknown",
    ),
    "transparency": ("transparent", "translucent", "opaque", "unknown"),
    "glossiness": ("low", "medium", "high", "metallic", "unknown"),
    "surface_texture": (
        "rough", "smooth", "powdery", "granular", "fibrous", "porous",
        "wrinkled", "layered", "wood_grain", "unknown",
    ),
    "edge_fracture": (
        "sharp", "blunt", "flat_broken", "irregular_broken", "torn", "folded",
        "layered_break", "unknown",
    ),
    "shape_form": (
        "block_like", "thin_plate", "sheet_like", "film_like", "rod_like",
        "irregular_chunk", "fragment", "unknown",
    ),
}

INSTANCE_ATTRIBUTE_ENUMS: Final[dict[str, tuple[str, ...]]] = {
    "recognition_status": ("accepted", "review_required", "unknown"),
    "occlusion_state": ("none", "partial", "unknown"),
    "vlm_consistency": ("support", "conflict", "not_checked"),
    "current_handling_policy": (
        "auto_allowed", "human_confirmation_required", "human_review_required", "robot_forbidden",
    ),
    "task_status": ("pending", "processing", "completed", "failed"),
}

UNKNOWN_SAMPLE_REVIEW_STATUSES: Final[tuple[str, ...]] = (
    "pending", "confirmed_existing", "confirmed_new", "rejected",
)


EVENT_DEFINITIONS: Final[dict[str, dict[str, Any]]] = {
    "DetectionEvent": {
        "source": "yolo_detector",
        "attributes": ("yolo_confidence", "bbox_2d", "mask_ref", "crop_ref"),
        "attribute_enums": {},
        "trigger": "YOLO 或已审核标注产生置信度不低于 proposal_threshold 的候选。",
        "preconditions": ("Scene 已创建", "候选类别属于 11 类词表"),
        "relations": ("IN_SCENE->Scene", "DETECTED->ObjectInstance", "PROPOSED->WasteCategory"),
        "effects": (
            "创建或更新 ObjectInstance", "创建 CANDIDATE_OF",
            "设置 vlm_consistency=not_checked", "设置 task_status=pending", "新实例设置 attempt_count=0",
        ),
    },
    "VLMReviewEvent": {
        "source": "vlm_service",
        "attributes": ("image_quality", "visual_attributes", "consistency", "reason"),
        "attribute_enums": {
            "image_quality": ("clear", "limited", "poor"),
            "consistency": ("support", "conflict"),
        },
        "trigger": "置信度或类别策略要求 VLM 复核，并且 crop 可用。",
        "preconditions": ("ObjectInstance 已存在", "CANDIDATE_OF 已存在"),
        "relations": ("REVIEWS->ObjectInstance", "CHECKS_AGAINST->WasteCategory"),
        "effects": (
            "support：设置 vlm_consistency=support、recognition_status=accepted，并创建 CONFIRMED_AS",
            "conflict：设置 vlm_consistency=conflict、recognition_status=unknown、robot_forbidden，并创建 UnknownSample",
        ),
    },
    "DepthUpdateEvent": {
        "source": "depth_processor",
        "attributes": ("center_xyz_camera", "depth_valid_ratio", "observed_extent_3d", "occlusion_state"),
        "attribute_enums": {"occlusion_state": ("none", "partial", "unknown")},
        "trigger": "RealSense 深度观测为实例提供有效三维证据。",
        "preconditions": ("Scene 已存在", "ObjectInstance 已存在", "深度证据可用"),
        "relations": ("IN_SCENE->Scene", "UPDATES->ObjectInstance"),
        "effects": ("更新四个几何字段", "重新计算当前 Scene 的 NEAR"),
    },
    "HumanReviewEvent": {
        "source": "human_reviewer",
        "attributes": ("review_action", "reason"),
        "attribute_enums": {
            "review_action": ("confirm_existing", "mark_unknown", "approve_robot", "forbid_robot", "discard_detection"),
        },
        "trigger": "Supervisor 到达 human_review_interrupt，并收到明确的人工决定。",
        "preconditions": ("复核目标存在", "人工决定明确"),
        "relations": ("REVIEWS->ObjectInstance/UnknownSample/UnknownCluster", "CONFIRMS->WasteCategory when applicable"),
        "effects": (
            "confirm_existing：设置 accepted 并创建 CONFIRMED_AS", "mark_unknown：设置 unknown、robot_forbidden，并创建 UnknownSample",
            "approve_robot/forbid_robot：不改变类别，只更新 current_handling_policy",
            "discard_detection：从当前场景状态移除误检，同时保留事件审计证据",
        ),
    },
    "PlanningEvent": {
        "source": "task_planner",
        "attributes": ("planned_action", "reason"),
        "attribute_enums": {
            "planned_action": ("robot_grasp", "request_human_review", "rescan", "no_action"),
        },
        "trigger": "Supervisor 基于最新 graph_state 请求唯一一个下一步动作。",
        "preconditions": ("当前 Scene 为最新场景", "硬资格检查已完成"),
        "relations": ("IN_SCENE->Scene", "SELECTS->ObjectInstance when one target is selected"),
        "effects": ("只记录一个下一步动作", "被选 ObjectInstance.task_status=processing"),
    },
    "ExecutionEvent": {
        "source": "robot_controller",
        "attributes": ("action_id", "physical_attempt_started", "execution_result", "failure_reason"),
        "attribute_enums": {"execution_result": ("success", "failure")},
        "trigger": "唯一结构化动作通过门控，且机器人真实物理尝试已经开始。",
        "preconditions": ("action_id 未执行", "MoveIt 规划通过", "physical_attempt_started=true"),
        "relations": ("IN_SCENE->Scene", "EXECUTES_ON->ObjectInstance"),
        "effects": (
            "attempt_count += 1", "success：task_status=completed", "failure：task_status=failed",
            "重新规划前强制采集 RGB-D 并创建新 Scene",
        ),
    },
    "KnowledgeEvolutionEvent": {
        "source": "knowledge_updater",
        "attributes": ("evolution_action", "reason"),
        "attribute_enums": {
            "evolution_action": (
                "assign_existing_category", "create_unknown_cluster", "propose_new_category",
                "promote_new_category", "discard_unknown",
            ),
        },
        "trigger": "unknown 证据通过所需的人工、样本、训练和验证门控。",
        "preconditions": ("人工确认", "样本充分", "数据审核", "晋升类别前完成训练和独立验证"),
        "relations": ("UPDATES->UnknownSample/UnknownCluster", "CREATES->WasteCategory only after promotion"),
        "effects": ("更新 unknown 记忆", "只有 promote_new_category 可以创建长期类别"),
    },
}


EVENT_SOURCES: Final[dict[str, str]] = {
    name: str(definition["source"]) for name, definition in EVENT_DEFINITIONS.items()
}
EVENT_ATTRIBUTE_FIELDS: Final[dict[str, set[str]]] = {
    name: set(definition["attributes"]) for name, definition in EVENT_DEFINITIONS.items()
}


def knowledge_schema_snapshot() -> dict[str, Any]:
    """返回供审计和 UI 使用的 schema，不把 schema 元数据写成业务节点属性。"""

    return {
        "node_fields": {
            "WasteCategory": [
                "category_name", "risk_level", "fragility", "graspability_prior",
                "vlm_review_policy", "default_handling_policy", "visual_prototype",
            ],
            "Scene": ["scene_id", "captured_at", "rgb_ref", "depth_ref"],
            "ObjectInstance": [
                "instance_id", "yolo_confidence", "recognition_status", "bbox_2d", "mask_ref", "crop_ref",
                "center_xyz_camera", "depth_valid_ratio", "observed_extent_3d", "occlusion_state",
                "vlm_consistency", "current_handling_policy", "task_status", "attempt_count",
            ],
            "UnknownSample": [
                "sample_id", "crop_ref", "mask_ref", "yolo_topk", "vlm_attributes", "review_status", "human_label",
            ],
            "UnknownCluster": [
                "cluster_id", "member_count", "prototype_attributes", "representative_crop_ref",
                "review_status", "candidate_category_name",
            ],
            "Event": ["event_id", "event_type", "event_time", "event_source"],
        },
        "category_attribute_enums": {key: list(values) for key, values in CATEGORY_ATTRIBUTE_ENUMS.items()},
        "visual_attribute_enums": {key: list(values) for key, values in VISUAL_ATTRIBUTE_ENUMS.items()},
        "instance_attribute_enums": {key: list(values) for key, values in INSTANCE_ATTRIBUTE_ENUMS.items()},
        "unknown_sample_review_statuses": list(UNKNOWN_SAMPLE_REVIEW_STATUSES),
        "event_definitions": {
            name: {
                **definition,
                "attributes": list(definition["attributes"]),
                "attribute_enums": {key: list(values) for key, values in definition["attribute_enums"].items()},
                "preconditions": list(definition["preconditions"]),
                "relations": list(definition["relations"]),
                "effects": list(definition["effects"]),
            }
            for name, definition in EVENT_DEFINITIONS.items()
        },
    }
