# core/response_utils.py
import logging
from typing import Any, Dict, Union

logger = logging.getLogger("response_utils")

def normalize_agent_response(response_data: Union[str, Dict, Any]) -> str:
    """
    统一处理Agent返回的响应格式
    
    Args:
        response_data: Agent返回的响应数据
        
    Returns:
        str: 标准化的响应文本
    """
    try:
        if response_data is None:
            return "抱歉，暂时无法回复您的问题。"
        
        if isinstance(response_data, str):
            return response_data.strip()
        
        if isinstance(response_data, dict):
            # 优先提取text字段
            if "text" in response_data:
                text = response_data["text"]
                if isinstance(text, str):
                    return text.strip()
            
            # 其次提取response字段
            if "response" in response_data:
                response = response_data["response"]
                if isinstance(response, str):
                    return response.strip()
                elif isinstance(response, dict) and "text" in response:
                    return response["text"].strip()
            
            # 如果都没有，转换为字符串
            return str(response_data).strip()
        
        # 其他类型直接转换为字符串
        return str(response_data).strip()
    
    except Exception as e:
        logger.error(f"标准化响应格式失败: {str(e)}")
        return "抱歉，处理回复时出现了问题。"