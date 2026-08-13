"""Memory-related Agent API routes."""

import logging
from typing import Callable

from fastapi import APIRouter

from schemas.agent import MemoryAddRequest


logger = logging.getLogger("agent_memory_router")
router = APIRouter()


def create_memory_router(get_conversation_memory: Callable[[], object]) -> APIRouter:
    """Create memory routes with injected conversation memory state."""

    @router.get("/agent/memory/{session_id}")
    async def get_agent_memory(session_id: str):
        """获取Agent记忆信息"""
        conversation_memory = get_conversation_memory()
        conversation_history = conversation_memory.get_conversation_history(session_id)
        important_memories = conversation_memory.get_important_memories(session_id)

        return {
            "session_id": session_id,
            "conversation_history": conversation_history,
            "important_memories": important_memories,
            "total_messages": len(conversation_history),
            "important_memory_count": len(important_memories)
        }

    @router.post("/agent/memory/{session_id}/important")
    async def add_important_memory(session_id: str, memory_data: MemoryAddRequest):
        """添加重要记忆"""
        conversation_memory = get_conversation_memory()
        memory_text = memory_data.text
        category = memory_data.category

        conversation_memory.add_important_memory(memory_text, session_id, category)

        logger.info(f"添加重要记忆，会话: {session_id}, 分类: {category}")
        return {"message": "重要记忆已添加", "session_id": session_id, "category": category}

    return router

