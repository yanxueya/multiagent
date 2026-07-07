"""定义 config 多智能体占位逻辑。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """Runtime switches that should remain independent from model training."""

    kg_endpoint: str = "local-dynamic-waste-kg"
    ros2_bridge_endpoint: str = "mock-ros2-bridge"
    require_human_confirmation_for_high_risk: bool = True
    max_gpu_memory_gb: int = 8
