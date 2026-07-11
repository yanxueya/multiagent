"""定义 execution agent 的相机采集和受约束工具执行职责。"""

def describe_execution_agent() -> dict[str, str]:
    return {
        "name": "execution_agent",
        "role": "acquire RGB-D scenes or execute one validated ActionPlan through allowlisted tools",
        "status": "implemented_contract_ros2_tools_pending",
    }
