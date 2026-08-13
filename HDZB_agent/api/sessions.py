"""Session management Agent API routes."""

import logging
from datetime import datetime
from typing import Callable, MutableMapping

from fastapi import APIRouter, HTTPException


logger = logging.getLogger("agent_sessions_router")
router = APIRouter()


def create_sessions_router(
    get_active_sessions: Callable[[], MutableMapping],
    get_conversation_memory: Callable[[], object],
) -> APIRouter:
    """Create session routes with injected runtime state."""

    @router.get("/agent/sessions/{session_id}")
    async def get_agent_session(session_id: str):
        """获取Agent会话信息"""
        active_sessions = get_active_sessions()
        conversation_memory = get_conversation_memory()

        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")

        session_data = active_sessions[session_id]
        conversation_history = conversation_memory.get_conversation_history(session_id)
        important_memories = conversation_memory.get_important_memories(session_id)

        return {
            "session_id": session_id,
            "session_data": session_data,
            "conversation_history": conversation_history,
            "important_memories": important_memories,
            "history_count": len(conversation_history)
        }

    @router.delete("/agent/sessions/{session_id}")
    async def delete_agent_session(session_id: str):
        """删除Agent会话"""
        active_sessions = get_active_sessions()
        conversation_memory = get_conversation_memory()

        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"删除活跃会话: {session_id}")

        conversation_memory.clear_memory(session_id)

        logger.info(f"删除会话完成: {session_id}")
        return {"message": "会话已删除", "session_id": session_id}

    @router.get("/agent/sessions")
    async def list_agent_sessions():
        """列出所有活跃会话"""
        active_sessions = get_active_sessions()

        return {
            "sessions": {
                session_id: {
                    "created_at": data["created_at"].isoformat(),
                    "agent_type": data["agent_type"],
                    "message_count": data["message_count"],
                    "last_active": data["last_active"].isoformat(),
                    "age_seconds": (datetime.now() - data["last_active"]).total_seconds()
                }
                for session_id, data in active_sessions.items()
            },
            "total_sessions": len(active_sessions)
        }

    return router

