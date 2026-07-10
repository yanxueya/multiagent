"""按《建筑废弃物动态知识图谱设计》构建 11 类长期知识种子。"""

from __future__ import annotations

from typing import List

from wastekg.core.models import CategorySpec
from wastekg.graph.store import KnowledgeGraph


DEFAULT_CATEGORY_SPECS: List[CategorySpec] = [
    CategorySpec(
        name="concrete",
        risk_level="medium",
        fragility="low",
        graspability_prior="low",
        vlm_review_policy="threshold_based",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["gray", "dark_gray"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["rough", "granular"],
            "edge_fracture": ["irregular_broken"],
            "shape_form": ["irregular_chunk", "block_like"],
        },
    ),
    CategorySpec(
        name="brick",
        risk_level="medium",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="auto_allowed",
        visual_prototype={
            "dominant_color": ["red_brown", "brown"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["rough", "porous"],
            "edge_fracture": ["irregular_broken", "blunt"],
            "shape_form": ["block_like", "fragment"],
        },
    ),
    CategorySpec(
        name="tile",
        risk_level="medium",
        fragility="high",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["white", "gray", "mixed"],
            "transparency": ["opaque"],
            "glossiness": ["medium", "high"],
            "surface_texture": ["smooth"],
            "edge_fracture": ["sharp", "flat_broken"],
            "shape_form": ["thin_plate", "fragment"],
        },
    ),
    CategorySpec(
        name="wood",
        risk_level="low",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="auto_allowed",
        visual_prototype={
            "dominant_color": ["brown", "yellow_brown"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["wood_grain", "fibrous"],
            "edge_fracture": ["torn", "irregular_broken"],
            "shape_form": ["sheet_like", "rod_like", "fragment"],
        },
    ),
    CategorySpec(
        name="gypsum_board",
        risk_level="medium",
        fragility="high",
        graspability_prior="low",
        vlm_review_policy="always",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["white", "light_gray"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["powdery", "layered"],
            "edge_fracture": ["flat_broken", "layered_break"],
            "shape_form": ["thin_plate", "fragment"],
        },
    ),
    CategorySpec(
        name="foam",
        risk_level="low",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["white", "yellow", "mixed"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["porous"],
            "edge_fracture": ["blunt", "irregular_broken"],
            "shape_form": ["block_like", "fragment"],
        },
    ),
    CategorySpec(
        name="metal",
        risk_level="medium",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["silver", "gray", "rust_brown"],
            "transparency": ["opaque"],
            "glossiness": ["metallic"],
            "surface_texture": ["smooth", "rough"],
            "edge_fracture": ["sharp", "folded"],
            "shape_form": ["sheet_like", "rod_like", "fragment"],
        },
    ),
    CategorySpec(
        name="soft_plastic",
        risk_level="low",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["mixed"],
            "transparency": ["transparent", "translucent", "opaque"],
            "glossiness": ["medium", "high"],
            "surface_texture": ["wrinkled", "smooth"],
            "edge_fracture": ["folded", "torn"],
            "shape_form": ["film_like", "sheet_like"],
        },
    ),
    CategorySpec(
        name="hard_plastic",
        risk_level="low",
        fragility="low",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="auto_allowed",
        visual_prototype={
            "dominant_color": ["mixed"],
            "transparency": ["transparent", "translucent", "opaque"],
            "glossiness": ["medium", "high"],
            "surface_texture": ["smooth"],
            "edge_fracture": ["blunt", "irregular_broken"],
            "shape_form": ["fragment", "sheet_like", "block_like"],
        },
    ),
    CategorySpec(
        name="paperboard",
        risk_level="low",
        fragility="medium",
        graspability_prior="medium",
        vlm_review_policy="threshold_based",
        default_handling_policy="auto_allowed",
        visual_prototype={
            "dominant_color": ["brown", "yellow_brown"],
            "transparency": ["opaque"],
            "glossiness": ["low"],
            "surface_texture": ["layered", "fibrous"],
            "edge_fracture": ["torn", "folded"],
            "shape_form": ["sheet_like", "fragment"],
        },
    ),
    CategorySpec(
        name="glass",
        risk_level="high",
        fragility="high",
        graspability_prior="low",
        vlm_review_policy="always",
        default_handling_policy="human_confirmation_required",
        visual_prototype={
            "dominant_color": ["clear", "light_green", "light_blue"],
            "transparency": ["transparent", "translucent"],
            "glossiness": ["high"],
            "surface_texture": ["smooth"],
            "edge_fracture": ["sharp"],
            "shape_form": ["thin_plate", "fragment"],
        },
    ),
]


def seed_default_categories(graph: KnowledgeGraph) -> List[str]:
    """注册文档定义的 11 个 WasteCategory，初始种子不产生进化事件。"""

    registered: List[str] = []
    for spec in DEFAULT_CATEGORY_SPECS:
        graph.register_category(spec)
        registered.append(spec.name)
    return registered
