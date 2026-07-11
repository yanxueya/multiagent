"""初始化 dynamic-waste-agent 包并提供轻量懒加载入口。"""

__all__ = [
    "AGENT_ORDER",
    "COMPONENT_ORDER",
    "DETERMINISTIC_NODE_ORDER",
    "GraphRuntime",
    "OPERATION_MODES",
    "build_langgraph_app",
    "build_thread_config",
    "describe_graph",
]


def __getattr__(name: str):
    if name == "build_thread_config":
        from .state import build_thread_config

        return build_thread_config
    if name in __all__:
        from . import graph

        return getattr(graph, name)
    raise AttributeError(f"module 'agent_system' has no attribute {name!r}")
