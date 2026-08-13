# tools/__init__.py
from .chat_tools import (
    ElderlyChatTool, 
    MemoryRecallTool, 
    KnowledgeSearchTool,
    WeatherTool,  # 更新为使用高德天气的WeatherTool
    LocationTool
)
from .llm_decision_system import LLMDecisionSystem, llm_decision_system

__all__ = [
    "ElderlyChatTool",
    "MemoryRecallTool", 
    "KnowledgeSearchTool",
    "WeatherTool",  # 保持名称一致
    "LocationTool",
    "LLMDecisionSystem",
    "llm_decision_system"
]