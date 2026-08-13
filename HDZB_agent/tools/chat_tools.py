"""
聊天工具模块 - 集成各种功能工具
包含天气查询、位置服务、知识搜索等功能
移除缓存机制，确保功能正常运行
"""

import httpx
import json
from typing import Dict, Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import logging
from datetime import datetime
from config.settings import settings

logger = logging.getLogger("chat_tools")

# 修改输入模型，将所有参数合并为一个字符串
class ChatToolInput(BaseModel):
    input_text: str = Field(description="完整的输入文本，格式为: '消息内容 | session_id'")

class ElderlyChatTool(BaseTool):
    """老年人聊天工具"""
    
    name: str = "elderly_chat"
    description: str = """用于与55-85岁老人进行日常聊天陪伴。适合以下场景：
    - 日常问候和寒暄
    - 情感陪伴和倾听
    - 简单的生活交流
    - 回忆往事
    注意：语气要温和，使用简单语言，避免技术术语，回答要简洁。
    输入格式：消息内容 | session_id"""
    args_schema: Type[BaseModel] = ChatToolInput
    
    def _run(self, input_text: str) -> str:
        """同步调用聊天API"""
        try:
            # 解析输入文本
            parts = input_text.split('|')
            if len(parts) != 2:
                return "输入格式错误，请使用: 消息内容 | session_id"
            
            message = parts[0].strip()
            session_id = parts[1].strip()
            
            # 这里可以调用原有服务，暂时返回模拟响应
            return f"聊天回复: {message} (会话: {session_id})"
        except Exception as e:
            return f"处理消息时出错: {str(e)}"
    
    async def _arun(self, input_text: str) -> str:
        """异步调用聊天API"""
        try:
            # 解析输入文本
            parts = input_text.split('|')
            if len(parts) != 2:
                return "输入格式错误，请使用: 消息内容 | session_id"
            
            message = parts[0].strip()
            session_id = parts[1].strip()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8016/chat",  # 原有服务地址
                    json={
                        "message": message,
                        "session_id": session_id
                    },
                    timeout=15.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "抱歉，暂时无法回复")
                else:
                    return "聊天服务暂时不可用"
        except Exception as e:
            logger.error(f"聊天工具调用失败: {str(e)}")
            return f"聊天请求失败: {str(e)}"

# 同样修改其他工具
class MemoryRecallInput(BaseModel):
    input_text: str = Field(description="回忆查询，格式为: '查询内容 | session_id'")

class MemoryRecallTool(BaseTool):
    """记忆回忆工具"""
    
    name: str = "memory_recall"
    description: str = "回忆与老人的过往对话和重要信息，用于提供更个性化的陪伴。输入格式: 查询内容 | session_id"
    args_schema: Type[BaseModel] = MemoryRecallInput
    
    def _run(self, input_text: str) -> str:
        try:
            parts = input_text.split('|')
            if len(parts) != 2:
                return "输入格式错误，请使用: 查询内容 | session_id"
            
            query = parts[0].strip()
            session_id = parts[1].strip()
            return f"回忆查询: {query} (会话: {session_id})"
        except Exception as e:
            return f"处理记忆查询时出错: {str(e)}"
    
    async def _arun(self, input_text: str) -> str:
        try:
            parts = input_text.split('|')
            if len(parts) != 2:
                return "输入格式错误，请使用: 查询内容 | session_id"
            
            query = parts[0].strip()
            session_id = parts[1].strip()
            return f"找到相关记忆: 关于'{query}'的过往对话 (会话: {session_id})"
        except Exception as e:
            return f"处理记忆查询时出错: {str(e)}"

class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="搜索查询")

class KnowledgeSearchTool(BaseTool):
    """知识搜索工具"""
    
    name: str = "knowledge_search"
    description: str = "搜索相关知识库，获取老年人关心的健康、生活、娱乐等信息"
    args_schema: Type[BaseModel] = KnowledgeSearchInput
    
    def _run(self, query: str) -> str:
        return f"知识搜索: {query}"
    
    async def _arun(self, query: str) -> str:
        # 集成向量知识库搜索
        return f"找到相关知识: 关于'{query}'的信息"

# 更新天气信息工具 - 使用高德地图API，移除缓存机制
class WeatherToolInput(BaseModel):
    location: str = Field(description="城市名称或位置信息，例如：北京、上海")

class AmapWeatherTool(BaseTool):
    """高德天气工具 - 简化版本，无缓存"""
    
    name: str = "get_weather"
    description: str = "获取指定城市的实时天气信息，包括温度、天气状况、湿度、风力等，并提供温馨的生活建议"
    args_schema: Type[BaseModel] = WeatherToolInput
    
    def __init__(self):
        """初始化天气工具，无缓存机制"""
        super().__init__()
        logger.info("天气工具初始化完成")
    
    async def _arun(self, location: str) -> str:
        """
        使用高德地图API获取天气信息 - 简化版本
        
        Args:
            location: 城市名称
            
        Returns:
            str: 格式化的天气信息
        """
        try:
            logger.info(f"开始查询天气，位置: {location}")
            
            # 获取城市编码
            city_code = await self._get_city_code(location)
            if not city_code:
                return f"抱歉，找不到'{location}'的天气信息，请检查城市名称是否正确"
            
            # 获取实时天气
            weather_data = await self._get_weather_data(city_code)
            
            if weather_data:
                return self._format_weather_response(weather_data, location)
            else:
                return f"暂时无法获取{location}的天气信息，请稍后重试"
                
        except Exception as e:
            logger.error(f"高德天气查询失败: {str(e)}")
            return "天气查询服务暂时不可用，请稍后重试"
    
    async def _get_city_code(self, location: str) -> str:
        """
        获取城市编码 - 高德API需要城市编码
        
        Args:
            location: 城市名称
            
        Returns:
            str: 城市编码
        """
        try:
            params = {
                "key": settings.AMAP_API_KEY,
                "address": location,
                "output": "json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    settings.AMAP_GEOCODE_URL,
                    params=params,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] == "1" and data["geocodes"]:
                        city_code = data["geocodes"][0]["adcode"]
                        logger.info(f"获取城市编码成功: {location} -> {city_code}")
                        return city_code
                    else:
                        logger.warning(f"获取城市编码失败: {location}, 响应: {data}")
            
            return ""
            
        except Exception as e:
            logger.error(f"获取城市编码异常: {str(e)}")
            return ""
    
    async def _get_weather_data(self, city_code: str) -> Dict[str, Any]:
        """
        获取天气数据
        
        Args:
            city_code: 城市编码
            
        Returns:
            Dict: 天气数据
        """
        try:
            params = {
                "key": settings.AMAP_API_KEY,
                "city": city_code,
                "extensions": "base",  # base:实况天气, all:预报天气
                "output": "json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    settings.AMAP_WEATHER_URL,
                    params=params,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] == "1" and data["lives"]:
                        weather_data = data["lives"][0]
                        logger.info(f"获取天气数据成功: 城市编码 {city_code}")
                        return weather_data
                    else:
                        logger.warning(f"获取天气数据失败: 城市编码 {city_code}, 响应: {data}")
            
            return {}
            
        except Exception as e:
            logger.error(f"获取天气数据异常: {str(e)}")
            return {}
    
    def _format_weather_response(self, weather_data: Dict, location: str) -> str:
        """
        格式化天气响应，适合老年人阅读
        
        Args:
            weather_data: 天气数据
            location: 城市名称
            
        Returns:
            str: 格式化的天气信息
        """
        try:
            # 高德天气API返回字段
            province = weather_data.get("province", "")
            city = weather_data.get("city", "")
            weather = weather_data.get("weather", "未知")
            temperature = weather_data.get("temperature", "未知")
            wind_direction = weather_data.get("winddirection", "未知")
            wind_power = weather_data.get("windpower", "未知")
            humidity = weather_data.get("humidity", "未知")
            report_time = weather_data.get("reporttime", "")
            
            # 构建温馨的天气提示
            response_parts = [
                f"{province}{city}的天气情况：",
                f"• 天气：{weather}",
                f"• 温度：{temperature}°C",
                f"• 湿度：{humidity}%",
                f"• 风向：{wind_direction}风",
                f"• 风力：{wind_power}级"
            ]
            
            # 添加贴心的生活建议
            life_advice = self._generate_life_advice(weather, temperature)
            response_parts.append(f"• 温馨提示：{life_advice}")
            
            if report_time:
                response_parts.append(f"• 更新时间：{report_time}")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"格式化天气响应失败: {str(e)}")
            return f"{location}的天气信息：{weather}，温度{temperature}°C"
    
    def _generate_life_advice(self, weather: str, temperature: str) -> str:
        """
        生成生活建议
        
        Args:
            weather: 天气状况
            temperature: 温度
            
        Returns:
            str: 生活建议
        """
        try:
            temperature_int = int(temperature) if temperature.isdigit() else 20
            
            advice_parts = []
            
            # 温度相关建议
            if temperature_int > 30:
                advice_parts.append("今天天气较热，注意防暑降温，多喝水哦")
            elif temperature_int < 10:
                advice_parts.append("天气较冷，记得添衣保暖，小心感冒")
            elif 15 <= temperature_int <= 25:
                advice_parts.append("温度适宜，适合户外活动")
            
            # 天气状况相关建议
            if "雨" in weather:
                advice_parts.append("今天有雨，出门请带伞，注意安全")
            elif "雪" in weather:
                advice_parts.append("今天下雪，路滑请注意安全")
            elif "晴" in weather:
                advice_parts.append("天气晴朗，可以适当晒太阳")
            elif "雾" in weather or "霾" in weather:
                advice_parts.append("空气质量较差，建议减少外出")
            
            # 默认建议
            if not advice_parts:
                advice_parts.append("请根据天气情况合理安排活动")
            
            return "；".join(advice_parts)
            
        except Exception as e:
            logger.error(f"生成生活建议失败: {str(e)}")
            return "请根据天气情况注意身体健康"
    
    def _run(self, location: str) -> str:
        """同步方法 - 调用异步方法"""
        import asyncio
        try:
            return asyncio.run(self._arun(location))
        except Exception as e:
            logger.error(f"同步天气查询失败: {str(e)}")
            return f"无法获取{location}的天气信息"

# 为了保持兼容性，保留WeatherTool名称
WeatherTool = AmapWeatherTool

# 新增的位置信息工具
class LocationToolInput(BaseModel):
    query: str = Field(description="位置查询或用户当前位置信息")

class LocationTool(BaseTool):
    """位置信息工具"""
    
    name: str = "get_location"
    description: str = "获取位置相关信息，包括用户当前位置、附近设施等"
    args_schema: Type[BaseModel] = LocationToolInput
    
    def _run(self, query: str) -> str:
        """获取位置信息 - 模拟实现"""
        try:
            logger.info(f"处理位置查询: {query}")
            
            # 这里可以接入真实的位置服务API
            # 例如：百度地图、高德地图等
            
            # 模拟返回数据
            if "附近" in query or "周边" in query:
                return f"根据您的位置，附近有：公园（500米）、超市（300米）、医院（1公里）"
            elif "位置" in query or "在哪里" in query:
                return "您当前位于北京市朝阳区（模拟位置）"
            else:
                return f"已获取位置信息：{query}"
        
        except Exception as e:
            logger.error(f"获取位置信息失败: {str(e)}")
            return "无法获取位置信息"
    
    async def _arun(self, query: str) -> str:
        """异步获取位置信息"""
        return self._run(query)

# ==================== 新增：家庭成员个人信息管理工具 ====================

class AddPersonalInfoInput(BaseModel):
    person_name: str = Field(description="家庭成员姓名")
    age: str = Field(description="年龄")
    gender: str = Field(description="性别")
    health_condition: str = Field(description="健康状况描述")

class AddPersonalInfoTool(BaseTool):
    """添加家庭成员个人信息工具"""
    
    name: str = "add_personal_info"
    description: str = """记录家庭成员的基本个人信息，包括姓名、年龄、性别和健康状况。
    当用户主动提供这些信息时使用此工具，确保为每个家庭成员单独记录。
    
    重要：必须明确知道是在为哪个家庭成员记录信息，避免信息混淆。"""
    args_schema: Type[BaseModel] = AddPersonalInfoInput
    
    def _run(self, person_name: str, age: str, gender: str, health_condition: str) -> str:
        return f"个人信息记录: {person_name}, {age}岁, {gender}, 健康状况: {health_condition}"
    
    async def _arun(self, person_name: str, age: str, gender: str, health_condition: str) -> str:
        try:
            # 这里记录到专门的个人信息存储
            # 实际实现会在companion_agent中处理
            logger.info(f"记录个人信息: {person_name}, {age}, {gender}, {health_condition}")
            return f"✅ 已记录{person_name}的信息：{age}岁，{gender}，健康状况：{health_condition}"
        except Exception as e:
            logger.error(f"记录个人信息失败: {str(e)}")
            return f"记录个人信息时出错: {str(e)}"

class RecallPersonalInfoInput(BaseModel):
    person_name: str = Field(description="要查询的家庭成员姓名")

class RecallPersonalInfoTool(BaseTool):
    """回忆家庭成员个人信息工具"""
    
    name: str = "recall_personal_info"
    description: str = """回忆特定家庭成员的个人信息，包括年龄、性别和健康状况。
    当需要了解某个家庭成员的基本情况时使用此工具。"""
    args_schema: Type[BaseModel] = RecallPersonalInfoInput
    
    def _run(self, person_name: str) -> str:
        return f"查询个人信息: {person_name}"
    
    async def _arun(self, person_name: str) -> str:
        try:
            # 这里从个人信息存储中查询
            # 实际实现会在companion_agent中处理
            logger.info(f"查询个人信息: {person_name}")
            
            # 模拟返回数据 - 实际应该从存储中获取
            personal_info = {
                "张三": "68岁，男性，有高血压需要注意",
                "李四": "65岁，女性，关节不太好",
                "王五": "72岁，男性，血糖偏高"
            }
            
            if person_name in personal_info:
                return f"{person_name}的信息：{personal_info[person_name]}"
            else:
                return f"暂时没有找到{person_name}的个人信息记录"
                
        except Exception as e:
            logger.error(f"查询个人信息失败: {str(e)}")
            return f"查询个人信息时出错: {str(e)}"

class ListFamilyMembersInput(BaseModel):
    query: str = Field(description="查询词，固定为'列出所有家庭成员'")

class ListFamilyMembersTool(BaseTool):
    """列出所有已记录的家庭成员工具"""
    
    name: str = "list_family_members"
    description: str = "列出所有已记录个人信息的家庭成员姓名"
    args_schema: Type[BaseModel] = ListFamilyMembersInput
    
    def _run(self, query: str) -> str:
        return "列出家庭成员"
    
    async def _arun(self, query: str) -> str:
        try:
            logger.info("列出所有家庭成员")
            
            # 模拟返回数据 - 实际应该从存储中获取
            family_members = ["张三", "李四", "王五"]
            
            if family_members:
                return "已记录的家庭成员：\n" + "\n".join(f"• {name}" for name in family_members)
            else:
                return "暂时没有记录任何家庭成员信息"
                
        except Exception as e:
            logger.error(f"列出家庭成员失败: {str(e)}")
            return f"列出家庭成员时出错: {str(e)}"