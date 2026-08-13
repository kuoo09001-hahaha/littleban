"""基础Agent类 - 精简版本"""

import logging

logger = logging.getLogger("base_agent")

class BaseElderlyAgent:
    """老年人陪伴基础Agent - 精简版"""
    
    def __init__(self, tools, system_prompt, memory):
        self.tools = tools
        self.system_prompt = system_prompt
        self.memory = memory
        self.agent_executor = None
        
    def create_agent(self):
        raise NotImplementedError("子类必须实现create_agent方法")
    
    async def run(self, input_text: str, session_id: str, **kwargs):
        try:
            if self.agent_executor is None:
                self.agent_executor = self.create_agent()
            
            inputs = {
                "input": input_text,
                "session_id": session_id,
                **kwargs
            }
            
            result = await self.agent_executor.arun(inputs)
            
            self.memory.save_context(input_text, result, session_id)
            
            return {
                "success": True,
                "response": result,
                "session_id": session_id
            }
        except Exception as e:
            return {
                "success": False,
                "response": "抱歉，遇到问题请稍后再试。",
                "session_id": session_id,
                "error": str(e)
            }
    
    def get_conversation_history(self, session_id: str):
        return self.memory.get_conversation_history(session_id)
    
    def clear_conversation(self, session_id: str):
        self.memory.clear_memory(session_id)