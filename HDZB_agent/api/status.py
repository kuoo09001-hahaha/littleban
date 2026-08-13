"""Status, debug, metrics, and root Agent API routes."""

from datetime import datetime
from typing import Callable, Mapping

from fastapi import APIRouter

from config.settings import settings


router = APIRouter()


def _family_member_count(agents: Mapping) -> int:
    companion_agent = agents.get("companion")
    if companion_agent and hasattr(companion_agent, "family_personal_info"):
        return len(companion_agent.family_personal_info)
    return 0


def create_status_router(
    get_agents: Callable[[], Mapping],
    get_active_sessions: Callable[[], Mapping],
    get_conversation_memory: Callable[[], object],
) -> APIRouter:
    """Create status routes with injected runtime state."""

    @router.get("/agent/debug/{session_id}")
    async def debug_session(session_id: str):
        """调试会话信息"""
        active_sessions = get_active_sessions()
        conversation_memory = get_conversation_memory()
        conversation_history = conversation_memory.get_conversation_history(session_id)
        important_memories = conversation_memory.get_important_memories(session_id)

        return {
            "session_id": session_id,
            "conversation_history": conversation_history,
            "important_memories": important_memories,
            "total_messages": len(conversation_history),
            "active_sessions": list(active_sessions.keys()),
            "session_exists": session_id in active_sessions
        }

    @router.get("/agent/health")
    async def health_check():
        """健康检查端点"""
        agents = get_agents()
        active_sessions = get_active_sessions()
        conversation_memory = get_conversation_memory()

        weather_api_configured = bool(settings.AMAP_API_KEY and settings.AMAP_API_KEY != "您的高德API密钥")
        weather_api_status = "available" if weather_api_configured else "not_configured"

        ark_configured = bool(settings.ARK_API_KEY and settings.ARK_API_KEY != "您的API密钥")
        ark_api_status = "available" if ark_configured else "not_configured"

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agents_loaded": list(agents.keys()),
            "active_sessions": len(active_sessions),
            "api_status": {
                "weather_api": weather_api_status,
                "ark_api": ark_api_status
            },
            "memory_stats": {
                "conversation_sessions": len(conversation_memory.conversation_context),
                "important_memories": len(conversation_memory.important_memories),
                "family_members": _family_member_count(agents)
            },
            "version": "2.0.0"
        }

    @router.get("/agent/metrics")
    async def get_metrics():
        """获取服务性能指标"""
        agents = get_agents()
        active_sessions = get_active_sessions()
        conversation_memory = get_conversation_memory()

        total_messages = sum(
            len(conversation_memory.get_conversation_history(session_id))
            for session_id in active_sessions
        )

        now = datetime.now()
        session_ages = [
            (now - data["last_active"]).total_seconds()
            for data in active_sessions.values()
        ]
        avg_session_age = sum(session_ages) / len(session_ages) if session_ages else 0

        return {
            "active_sessions": len(active_sessions),
            "total_messages": total_messages,
            "family_members": _family_member_count(agents),
            "average_session_age_seconds": avg_session_age,
            "memory_usage": {
                "conversation_sessions": len(conversation_memory.conversation_context),
                "important_memories": len(conversation_memory.important_memories)
            },
            "agent_status": {
                agent_name: "active" for agent_name in agents.keys()
            },
            "timestamp": datetime.now().isoformat()
        }

    @router.get("/")
    async def root():
        """根端点，返回服务基本信息"""
        agents = get_agents()

        return {
            "message": "老年人陪伴AI Agent服务运行中",
            "version": "2.0.0",
            "framework": "LangChain AI Agent",
            "available_agents": list(agents.keys()),
            "family_members_count": _family_member_count(agents),
            "features": [
                "增强对话记忆管理",
                "多工具集成（天气、位置、知识搜索等）",
                "会话持久化支持",
                "连续对话上下文",
                "智能决策系统",
                "高德天气API集成",
                "DeepSeek V3 Function Calling",
                "老年人友好界面设计",
                "家庭成员个人信息管理"
            ],
            "external_services": {
                "weather_service": "高德地图天气API",
                "ai_model": "DeepSeek V3 (火山引擎)",
                "cache_mechanism": "已启用"
            },
            "endpoints": {
                "chat": "/agent/chat (POST)",
                "weather_query": "/agent/weather/query (POST)",
                "personal_info_add": "/agent/personal_info/add (POST)",
                "personal_info_get": "/agent/personal_info/{person_name} (GET)",
                "family_members_list": "/agent/personal_info (GET)",
                "session_management": "/agent/sessions/{session_id} (GET/DELETE)",
                "memory_management": "/agent/memory/{session_id} (GET/POST)",
                "health_check": "/agent/health (GET)",
                "metrics": "/agent/metrics (GET)"
            }
        }

    return router

