"""
增强的对话记忆管理模块
修复LangChain弃用警告，使用新的内存管理方式
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger("conversation_memory")


@dataclass(frozen=True)
class MemoryMessage:
    """Minimal message type retained for callers needing message objects."""

    role: str
    content: str

class EnhancedConversationMemory:
    """增强的对话记忆管理"""
    
    def __init__(self, max_token_limit: int = 2000, window_size: int = 6):
        # 使用新的 ConversationBufferWindowMemory 初始化方式
        # Keep a lightweight buffer per session. The Agent already consumes
        # ``conversation_context`` directly, so importing LangChain merely for
        # this compatibility cache added an unnecessary runtime dependency.
        self.window_size = window_size
        self.session_messages = {}
        self.conversation_context = {}
        self.important_memories = []
        logger.info(f"对话记忆初始化完成，窗口大小: {window_size}")
    
    def set_llm(self, llm):
        """设置LLM - 为了兼容性保留，但不再需要"""
        pass  # ConversationBufferWindowMemory 不需要LLM
    
    def save_context(self, user_input: str, assistant_response: str, session_id: str):
        """保存对话上下文"""
        # 确保session_id不为空
        if not session_id:
            logger.error("session_id为空，无法保存上下文")
            return
            
        messages = self.session_messages.setdefault(session_id, [])
        messages.extend((
            MemoryMessage(role="user", content=user_input),
            MemoryMessage(role="assistant", content=assistant_response),
        ))
        # ``window_size`` counts dialogue turns, hence two messages per turn.
        self.session_messages[session_id] = messages[-(self.window_size * 2):]
        
        # 保存到自定义记忆结构
        if session_id not in self.conversation_context:
            self.conversation_context[session_id] = []
        
        self.conversation_context[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "assistant": assistant_response,
            "tokens": len(user_input) + len(assistant_response)
        })
        
        # 调试信息
        logger.debug(f"保存对话上下文，会话: {session_id}, 历史记录数: {len(self.conversation_context[session_id])}")
        
        # 打印最新几条记录用于调试
        recent = self.conversation_context[session_id][-3:]  # 最近3条
        for i, item in enumerate(recent):
            logger.debug(f"历史记录[{i}]: 用户={item['user'][:20]}... AI={item['assistant'][:20]}...")
    
    def get_conversation_history(self, session_id: str, max_messages: int = 6) -> List[Dict]:
        """获取对话历史"""
        if session_id not in self.conversation_context:
            logger.debug(f"会话 {session_id} 没有历史记录")
            return []
        
        history = self.conversation_context[session_id][-max_messages:]
        logger.debug(f"获取会话 {session_id} 的历史记录 {len(history)} 条")
        return history
    
    def get_memory_as_messages(self, session_id: str) -> List[MemoryMessage]:
        """Return message objects for one session only."""
        return list(self.session_messages.get(session_id, []))
    
    def clear_memory(self, session_id: str = None):
        """清空记忆"""
        if session_id:
            if session_id in self.conversation_context:
                del self.conversation_context[session_id]
                self.session_messages.pop(session_id, None)
                logger.info(f"清空会话记忆: {session_id}")
        else:
            self.session_messages.clear()
            self.conversation_context.clear()
            logger.info("清空所有记忆")
    
    def add_important_memory(self, memory_text: str, session_id: str, category: str = "general"):
        """添加重要记忆"""
        memory = {
            "text": memory_text,
            "session_id": session_id,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "importance": "high"
        }
        self.important_memories.append(memory)
        logger.info(f"添加重要记忆: {category}, 会话: {session_id}")
    
    def get_important_memories(self, session_id: str = None) -> List[Dict]:
        """获取重要记忆"""
        if session_id:
            return [m for m in self.important_memories if m["session_id"] == session_id]
        return self.important_memories
