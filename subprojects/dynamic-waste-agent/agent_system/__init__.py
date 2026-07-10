"""初始化 dynamic-waste-agent 包并提供轻量懒加载入口。"""

__all__ = ["AGENT_ORDER", "COMPONENT_ORDER", "describe_graph"]


def __getattr__(name: str):
    if name in __all__:
        from . import graph

        return getattr(graph, name)
    raise AttributeError(f"module 'agent_system' has no attribute {name!r}")