# file: llm_decision_system.py
import logging
from typing import Dict, List, Any, Optional
import httpx
import json
from config.settings import settings
import time

logger = logging.getLogger("llm_decision_system")

class LLMDecisionSystem:
    """基于LLM的智能决策系统"""
    
    def __init__(self):
        self.available_tools = [
            {
                "name": "get_weather",
                "description": "获取指定位置的天气信息，包括温度、天气状况等",
                "parameters": ["location"]
            },
            {
                "name": "get_location", 
                "description": "获取位置相关信息，包括用户当前位置、附近设施等",
                "parameters": ["query"]
            },
            {
                "name": "memory_recall",
                "description": "回忆与老人的过往对话和重要信息",
                "parameters": ["input_text"]
            },
            {
                "name": "knowledge_search",
                "description": "搜索相关知识库，获取老年人关心的健康、生活、娱乐等信息",
                "parameters": ["query"]
            },
            {
                "name": "elderly_chat",
                "description": "日常聊天陪伴，不需要特殊工具调用时的默认选择",
                "parameters": ["input_text"]
            }
        ]
    
    async def analyze_and_decide(self, user_input: str, session_id: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """使用LLM分析用户输入并决定是否需要调用工具"""
        try:
            # 构建系统提示词
            system_prompt = self._build_decision_prompt()
            
            # 构建消息历史
            messages = self._build_messages(system_prompt, user_input, conversation_history)
            
            logger.info(f"开始调用决策LLM，消息数量: {len(messages)}")
            
            # 调用LLM进行决策
            decision = await self._call_decision_llm(messages)
            
            logger.info(f"LLM决策结果: {decision}")
            
            return decision
            
        except Exception as e:
            logger.error(f"决策系统分析失败: {str(e)}", exc_info=True)
            # 出错时默认使用聊天
            return {
                "needs_tools": False,
                "tool_calls": [],
                "direct_chat": True,
                "reasoning": f"决策系统出错: {str(e)}"
            }
    
    def _build_decision_prompt(self) -> str:
        """构建决策系统提示词"""
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']} (参数: {', '.join(tool['parameters'])})"
            for tool in self.available_tools
        ])
        
        return f"""你是一个智能决策助手，负责分析用户输入并决定是否需要调用工具。

可用的工具：
{tools_description}

决策规则：
1. 仔细分析用户意图，判断是否需要外部信息或特殊功能
2. 如果需要获取天气信息，调用get_weather工具
3. 如果需要位置相关服务，调用get_location工具  
4. 如果需要回忆过往对话，调用memory_recall工具
5. 如果需要搜索知识，调用knowledge_search工具
6. 如果只是日常聊天，使用elderly_chat工具或不调用工具直接回复
7. 对于老年人用户，优先考虑简单直接的回应

输出格式必须是JSON：
{{
    "needs_tools": true/false,
    "tool_calls": [
        {{
            "tool_name": "工具名称",
            "parameters": {{"参数名": "参数值"}},
            "reasoning": "调用该工具的原因"
        }}
    ],
    "direct_chat": true/false,
    "reasoning": "整体决策理由"
}}

请确保输出是有效的JSON格式。"""
    
    def _build_messages(self, system_prompt: str, user_input: str, conversation_history: List[Dict]) -> List[Dict]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 添加最近的历史对话作为上下文
        for item in conversation_history[-4:]:  # 最近2轮对话
            messages.append({"role": "user", "content": item["user"]})
            messages.append({"role": "assistant", "content": item["assistant"]})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    async def _call_decision_llm(self, messages: List[Dict]) -> Dict[str, Any]:
        """调用LLM进行决策"""
        headers = {
            "Authorization": f"Bearer {settings.ARK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "ep-20250908145921-s8nfk",
            "messages": messages,
            "stream": False,
            "max_tokens": 500,
            "temperature": 0.1,  # 低温度确保决策稳定
            "response_format": {"type": "json_object"}  # 强制JSON输出
        }
        
        try:
            logger.info(f"发送决策请求到: {settings.ARK_API_URL}")
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=30.0) as client:  # 增加超时到30秒
                response = await client.post(
                    settings.ARK_API_URL,
                    headers=headers,
                    json=payload
                )
                
                request_time = time.time() - start_time
                logger.info(f"决策LLM响应时间: {request_time:.2f}秒, 状态码: {response.status_code}")
                
                if response.status_code == 200:
                    api_response = response.json()
                    response_text = api_response["choices"][0]["message"]["content"]
                    logger.info(f"决策LLM原始响应: {response_text}")
                    
                    try:
                        # 解析JSON响应
                        decision = json.loads(response_text)
                        return decision
                    except json.JSONDecodeError as e:
                        logger.error(f"LLM返回无效JSON: {response_text}, 错误: {e}")
                        # 尝试修复JSON格式
                        try:
                            # 移除可能的Markdown代码块标记
                            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
                            decision = json.loads(cleaned_text)
                            logger.info("成功修复JSON格式")
                            return decision
                        except:
                            return self._get_fallback_decision()
                else:
                    error_detail = f"状态码: {response.status_code}"
                    try:
                        error_body = response.text
                        error_detail += f", 响应: {error_body}"
                        logger.error(f"决策LLM API错误: {error_detail}")
                    except:
                        logger.error(f"决策LLM API错误: {error_detail}")
                    return self._get_fallback_decision()
                    
        except httpx.TimeoutException:
            logger.error("决策LLM调用超时")
            return self._get_fallback_decision()
        except Exception as e:
            logger.error(f"决策LLM调用异常: {str(e)}", exc_info=True)
            return self._get_fallback_decision()
    
    def _get_fallback_decision(self) -> Dict[str, Any]:
        """获取降级决策"""
        return {
            "needs_tools": False,
            "tool_calls": [],
            "direct_chat": True,
            "reasoning": "决策系统降级，使用直接聊天"
        }
    
    def extract_location_from_weather_query(self, user_input: str) -> str:
        """从天气查询中提取位置信息（备用方法）"""
        # 简单的关键词匹配作为备用
        import re
        
        weather_patterns = [
            r"(.+?)的天气",
            r"天气(.+?)",
            r"(.+?)天气怎么样",
            r"(.+?)气温"
        ]
        
        for pattern in weather_patterns:
            match = re.search(pattern, user_input)
            if match:
                location = match.group(1).strip()
                if location and len(location) > 1:
                    return location
        
        # 默认位置
        return "北京"

# 单例实例
llm_decision_system = LLMDecisionSystem()