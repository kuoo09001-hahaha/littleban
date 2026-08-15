
"""老年人陪伴AI Agent - 完整功能版本
支持function calling，集成天气查询、位置服务、个人信息管理等功能
"""

import httpx
import json
from .base_agent import BaseElderlyAgent
from config.settings import settings
import logging
import re
from typing import List, Dict, Any
from datetime import datetime 
from domain.device_config import DeviceConfig
from domain.modes import ModeProfile
from services.prompt_builder import PromptBuilder

logger = logging.getLogger("companion_agent")

GENERIC_REMINDER_TITLES = {"", "提醒", "设置提醒", "通知", "闹钟", "记得"}


def reminder_task_text(value: str | None) -> str:
    """Use a natural placeholder when no concrete reminder task exists."""
    text = str(value or "").strip()
    return "这件事" if text in GENERIC_REMINDER_TITLES else text

def clean_response(text: str) -> str:
    """
    清理回复内容，确保对老年人友好
    
    Args:
        text: 原始回复文本
        
    Returns:
        str: 清理后的友好文本
    """
    if not text:
        return "抱歉，我没有理解您的意思，能再说一次吗？"
    
    # 移除思考过程标签和特殊格式
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<\/?think>', '', cleaned, flags=re.IGNORECASE)
    
    # 移除各种星号格式
    cleaned = re.sub(r'\*+', '', cleaned)
    
    # 移除代码块标记
    cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'`', '', cleaned)
    
    # 移除其他可能的有害格式
    cleaned = re.sub(r'#{1,6}\s?', '', cleaned)
    cleaned = re.sub(r'\[.*?\]\(.*?\)', '', cleaned)
    
    # 简化格式
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    
    cleaned = cleaned.strip()
    
    if not cleaned:
        return "抱歉，我没有理解您的意思，能再说一次吗？"
    
    if cleaned and cleaned[-1] not in ['。', '！', '？', '.', '!', '?']:
        cleaned += '。'
        
    return cleaned

class CompanionAgent(BaseElderlyAgent):
    """支持function calling的陪伴聊天Agent"""

    def __init__(self, tools, memory, profile_service=None, prompt_builder=None, action_service=None):
        """
        初始化陪伴Agent
        
        Args:
            tools: 工具列表
            memory: 记忆管理器
        """
        super().__init__(tools, "", memory)
        
        # 工具映射
        self.tool_map = {tool.name: tool for tool in tools}
        logger.info(f"工具映射建立完成，可用工具: {list(self.tool_map.keys())}")
        
        # 家庭成员个人信息存储
        self.profile_service = profile_service
        self._family_personal_info = {}
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.action_service = action_service
        
        # 可用函数
        self.available_functions = self._build_available_functions()

    @property
    def family_personal_info(self) -> Dict:
        """Return family member info for metrics/status compatibility."""
        if self.profile_service:
            return {
                member["person_name"]: {
                    "age": member.get("age", ""),
                    "gender": member.get("gender", ""),
                    "health_condition": member.get("health_condition", ""),
                }
                for member in self.profile_service.list_family_members()
            }

        return self._family_personal_info

    async def _execute_intent_analyzer_tool(self, args: Dict) -> str:
        """Run only the deterministic fast path before the main LLM."""
        try:
            user_input = args.get("user_input", "")
            intent_tool = self.tool_map.get("intent_analyzer")
            if intent_tool:
                local_intent = intent_tool._extract_local_reminder_intent(user_input)
                if local_intent:
                    return json.dumps(local_intent, ensure_ascii=False)
            return json.dumps({"intent_type": "NONE", "is_system_command": False}, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"意图识别工具执行失败: {str(e)}")
            return json.dumps({
                "intent_type": "NONE",
                "is_system_command": False
            }, ensure_ascii=False)
    
    async def _check_user_intent(self, input_text: str, session_id: str) -> dict:
        """使用LLM检查用户意图"""
        try:
            logger.info(f"开始意图识别检查: '{input_text}'")
            
            # 调用意图识别工具
            intent_result = await self._execute_intent_analyzer_tool({"user_input": input_text})
            
            # 解析意图识别结果
            intent_data = json.loads(intent_result)
            
            # 如果是系统指令
            if intent_data.get("is_system_command", False):
                
                command_type = intent_data.get("intent_type")
                logger.info(f"识别到系统指令: {command_type}")
                
                # 构建响应数据 - 确保包含command_type
                response_data = {
                    "success": True,
                    "response": "",  # 空字符串，表示纯指令
                    "session_id": session_id,
                    "agent_type": "companion",
                    "is_system_command": True,
                    "command_type": command_type,  # 关键修复：确保设置command_type
                    "tool_used": True,
                    "tool_results": [{
                        "tool_name": "intent_analyzer",
                        "arguments": {"user_input": input_text},
                        "result": intent_result
                    }]
                }
                
                # 处理不同类型的系统指令
                # 音量相关指令
                if command_type == "VOLUME_MUTE":
                    response_data["volume_control"] = {
                        "action": "mute",
                        "timestamp": datetime.now().isoformat()
                    }
                    response_data["response"] = "好的，已静音"
                    
                elif command_type == "VOLUME_SET":
                    volume_change = intent_data.get("volume_change", 120)  # 默认减少20
                    
                    response_data["volume_control"] = {
                        "action": "set",
                        "change": volume_change,  # 编码值，如 070, 120, 220 等
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # 根据编码值生成友好的响应
                    if volume_change < 100:
                        # 0-99表示设置绝对值
                        response_data["response"] = f"好的，音量已设置为{volume_change}%"
                        response_data["volume_control"]["absolute_value"] = volume_change
                    elif 100 <= volume_change < 200:
                        # 100-199表示减少音量
                        decrease_value = volume_change - 100
                        response_data["response"] = f"好的，音量已减少{decrease_value}%"
                    else:
                        # 200+表示增加音量
                        increase_value = volume_change - 200
                        response_data["response"] = f"好的，音量已增加{increase_value}%"
                
                # 闹钟设置指令
                elif command_type == "SET_ALARM":
                    alarm_info = intent_data.get("alarm_info", {})

                    if alarm_info.get("needs_time"):
                        repeat_text = "每天" if alarm_info.get("repeat_desc") == "daily" else ""
                        name_str = reminder_task_text(alarm_info.get("name"))
                        response_data["response"] = f"好的，我可以{repeat_text}提醒您{name_str}。请问要在几点提醒您？"
                        response_data["alarm_control"] = {"action": "needs_time", "alarm_info": alarm_info, "timestamp": datetime.now().isoformat()}
                        return response_data
                    
                    response_data["alarm_control"] = {
                        "action": "set",
                        "alarm_info": alarm_info,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # 根据时间类型生成不同的响应
                    time_type = alarm_info.get("time_type", "absolute")
                    display_time = alarm_info.get("display_time", "08:00")
                    name_str = reminder_task_text(alarm_info.get("name"))
                    repeat_desc = alarm_info.get("repeat_desc", "once")
                    
                    # 生成重复描述文本
                    repeat_text = self._generate_repeat_text(repeat_desc)
                    
                    if time_type == "relative":
                        minutes = alarm_info.get("minutes_from_now", 60)
                        response_data["response"] = f"好的，{minutes}分钟后{repeat_text}提醒您：{name_str}。"
                    else:
                        response_data["response"] = f"好的，已设置{repeat_text}{display_time}的提醒：{name_str}。"
                
                # 其他系统指令（关机、重启、呼叫等）
                elif command_type in ["SYSTEM_SHUTDOWN", "SYSTEM_RESTART"]:
                    response_data["response"] = f"好的，执行{command_type}指令"
                
                # 呼叫指令
                elif command_type in ["CALL_CONTACT_1", "CALL_CONTACT_2", "CALL_CONTACT_3"]:
                    contact_map = {
                        "CALL_CONTACT_1": "第一个联系人",
                        "CALL_CONTACT_2": "第二个联系人", 
                        "CALL_CONTACT_3": "第三个联系人"
                    }
                    response_data["response"] = f"好的，正在呼叫{contact_map.get(command_type, '联系人')}"
                    if "contact_id" in intent_data:
                        response_data["contact_id"] = intent_data["contact_id"]
                    if "display_name" in intent_data:
                        response_data["display_name"] = intent_data["display_name"]
                
                logger.info(f"系统指令响应数据: {response_data}")
                return response_data
            
            logger.info(f"未识别到系统指令，意图类型: {intent_data.get('intent_type')}")
            return None
            
        except Exception as e:
            logger.error(f"用户意图检查失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _generate_repeat_text(self, repeat_desc: str) -> str:
        """生成重复描述文本"""
        # 单个重复类型
        repeat_map = {
            "once": "单次",
            "daily": "每天", 
            "weekdays": "工作日",
            "weekend": "周末",
            "custom": "自定义"
        }
        
        # 处理每周重复（单个或多个日期）
        if repeat_desc.startswith("weekly_"):
            days = repeat_desc.replace("weekly_", "").split("_")
            day_map = {
                "mon": "一", "tue": "二", "wed": "三", "thu": "四",
                "fri": "五", "sat": "六", "sun": "日"
            }
            
            if len(days) > 1:
                # 多个日期
                day_names = [day_map.get(day, "") for day in days if day in day_map]
                if day_names:
                    return f"每周{''.join(day_names)}"
                else:
                    return "每周"
            else:
                # 单个日期
                day_cn = day_map.get(days[0], "")
                return f"每周{day_cn}"
        
        return repeat_map.get(repeat_desc, "")
    
    async def _execute_weather_tool(self, args: Dict) -> str:
        """
        执行天气查询工具
        
        Args:
            args: 工具参数
            
        Returns:
            str: 天气查询结果
        """
        try:
            location = args.get("location", "北京")
            
            weather_tool = self.tool_map.get("get_weather")
            
            if weather_tool:
                return await weather_tool._arun(location)
            else:
                logger.error("天气工具未找到")
                return f"天气查询服务暂不可用"
                
        except Exception as e:
            logger.error(f"天气工具执行失败: {str(e)}")
            location = args.get("location", "未知位置")
            return f"无法获取{location}的天气信息"
    
    async def _execute_location_tool(self, args: Dict) -> str:
        """
        执行位置查询工具
        
        Args:
            args: 工具参数
            
        Returns:
            str: 位置查询结果
        """
        try:
            query = args.get("query", "")
            
            location_tool = self.tool_map.get("get_location")
            
            if location_tool:
                return await location_tool._arun(query)
            else:
                logger.error("位置工具未找到")
                return "位置查询服务暂不可用"
                
        except Exception as e:
            logger.error(f"位置工具执行失败: {str(e)}")
            return "无法获取位置信息"
    
    async def _execute_add_personal_info_tool(self, args: Dict) -> str:
        """
        执行添加个人信息工具
        
        Args:
            args: 工具参数
            
        Returns:
            str: 执行结果
        """
        try:
            person_name = args.get("person_name", "").strip()
            age = args.get("age", "").strip()
            gender = args.get("gender", "").strip()
            health_condition = args.get("health_condition", "").strip()
            
            if not person_name:
                return "请提供要记录的家庭成员姓名"
            
            if self.profile_service:
                self.profile_service.upsert_family_member(
                    person_name=person_name,
                    age=age,
                    gender=gender,
                    health_condition=health_condition,
                )
            else:
                self._family_personal_info[person_name] = {
                    "age": age,
                    "gender": gender,
                    "health_condition": health_condition
                }
            
            logger.info(f"记录个人信息: {person_name}, {age}岁, {gender}, 健康状况: {health_condition}")
            
            # 返回确认信息
            response = f"✅ 已记录{person_name}的个人信息："
            if age:
                response += f"\n• 年龄：{age}岁"
            if gender:
                response += f"\n• 性别：{gender}"
            if health_condition:
                response += f"\n• 健康状况：{health_condition}"
                
            return response
            
        except Exception as e:
            logger.error(f"添加个人信息失败: {str(e)}")
            return f"记录个人信息时出错：{str(e)}"
    
    async def _execute_recall_personal_info_tool(self, args: Dict) -> str:
        """
        执行回忆个人信息工具
        
        Args:
            args: 工具参数
            
        Returns:
            str: 个人信息查询结果
        """
        try:
            person_name = args.get("person_name", "").strip()
            
            if not person_name:
                return "请提供要查询的家庭成员姓名"
            
            info = None
            if self.profile_service:
                info = self.profile_service.get_family_member(person_name)
            elif person_name in self._family_personal_info:
                info = {
                    "person_name": person_name,
                    **self._family_personal_info[person_name],
                }

            # 查询个人信息
            if info:
                response = f"📋 {person_name}的个人信息："
                
                if info.get("age"):
                    response += f"\n• 年龄：{info['age']}岁"
                if info.get("gender"):
                    response += f"\n• 性别：{info['gender']}"
                if info.get("health_condition"):
                    response += f"\n• 健康状况：{info['health_condition']}"
                    
                return response
            else:
                return f"暂时没有找到{person_name}的个人信息记录"
                
        except Exception as e:
            logger.error(f"查询个人信息失败: {str(e)}")
            return f"查询个人信息时出错：{str(e)}"
    
    async def _execute_list_family_members_tool(self, args: Dict) -> str:
        """
        执行列出家庭成员工具
        
        Args:
            args: 工具参数
            
        Returns:
            str: 家庭成员列表
        """
        try:
            family_members = (
                self.profile_service.list_family_members()
                if self.profile_service
                else [
                    {"person_name": name, **info}
                    for name, info in self._family_personal_info.items()
                ]
            )

            if not family_members:
                return "暂时没有记录任何家庭成员信息"
            
            response = "👨‍👩‍👧‍👦 已记录的家庭成员："
            for info in family_members:
                name = info["person_name"]
                response += f"\n• {name}"
                if info.get("age"):
                    response += f"（{info['age']}岁）"
            
            response += f"\n\n共记录了 {len(family_members)} 位家庭成员"
            return response
            
        except Exception as e:
            logger.error(f"列出家庭成员失败: {str(e)}")
            return f"列出家庭成员时出错：{str(e)}"
    
    def _build_available_functions(self) -> Dict[str, callable]:
        """
        动态构建可用函数映射
        
        Returns:
            Dict[str, callable]: 函数名称到函数方法的映射
        """
        function_map = {
            "get_weather": self._execute_weather_tool,
            "add_personal_info": self._execute_add_personal_info_tool,
            "recall_personal_info": self._execute_recall_personal_info_tool,
            "list_family_members": self._execute_list_family_members_tool,
        }
        
        # 动态验证工具可用性
        available_functions = {}
        for func_name, func_method in function_map.items():
            if self.action_service and func_name in {"add_personal_info", "recall_personal_info"}:
                continue
            if (func_name in self.tool_map or 
                func_name in ["add_personal_info", "recall_personal_info", "list_family_members"]):
                available_functions[func_name] = func_method
                logger.info(f"注册可用函数: {func_name}")
        if self.action_service:
            for name in (
                "set_reminder", "save_family_relationship", "query_family_relationship",
                "record_health_event", "resolve_health_event", "query_health_events",
                "save_preference", "query_preferences", "update_member_profile", "query_member_profile",
            ):
                available_functions[name] = None
                logger.info(f"注册可用函数: {name}")
        
        return available_functions
        
    def create_agent(self):
        """创建Agent执行器"""
        return None
    
    async def run(self, input_text: str, session_id: str, **kwargs) -> dict:
        """
        支持function calling的Agent运行方法 - 修复版本：包含对话历史
        """
        try:
            logger.info(f"开始处理用户输入: '{input_text}'")
            
            # 第一步：检查用户意图
            intent_check = await self._check_user_intent(input_text, session_id)
            
            if intent_check and intent_check.get("is_system_command", False):
                logger.info(f"识别到系统指令，直接返回: {intent_check.get('command_type')}")
                return {
                    "success": True,
                    "response": intent_check.get("response", ""),
                    "session_id": session_id,
                    "agent_type": "companion",
                    "is_system_command": True,
                    "command_type": intent_check.get("command_type"),
                    "tool_used": True,
                    "tool_results": intent_check.get("tool_results", []),
                    "volume_control": intent_check.get("volume_control"),
                    "alarm_control": intent_check.get("alarm_control")
                }
            
            # 第二步：正常聊天流程
            logger.info(f"进入正常聊天流程: '{input_text}'")
            
            # 构建系统提示词
            mode_profile = kwargs.get("mode_profile")
            device_config = kwargs.get("device_config")
            system_prompt = self._build_system_prompt(
                mode_profile, device_config, kwargs.get("session_location"), kwargs.get("actor_name"),
                kwargs.get("persistent_context"),
            )
            
            # 构建基础消息（系统提示 + 当前用户输入）
            base_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text}
            ]
            
            # 构建工具描述
            tools = self._build_tools_description()
            
            # 调用聊天API（会自动包含历史）
            result = await self._call_chat_api_with_tools(
                base_messages,
                tools,
                session_id,
                tool_context={
                    "session_id": session_id,
                    "family_id": kwargs.get("family_id", "default"),
                    "actor_name": kwargs.get("actor_name"),
                    "input_text": input_text,
                },
            )
            
            # 确保返回完整的结果
            if result and "success" in result:
                # 保存对话上下文
                if result["success"] and "response" in result:
                    self.memory.save_context(input_text, result["response"], session_id)
                return result
            else:
                # 如果API调用失败，返回降级响应
                return {
                    "success": True,
                    "response": "我来给您讲个故事吧：从前有座山，山里有座庙，庙里有个老和尚在给小和尚讲故事。讲的什么呢？从前有座山...",
                    "session_id": session_id,
                    "tool_used": False
                }
            
        except Exception as e:
            logger.error(f"聊天处理失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "response": "聊天处理失败:抱歉，服务暂时不可用，请稍后再试。",
                "session_id": session_id,
                "error": str(e)
            }
    
    def _build_tools_description(self) -> List[Dict]:
        """
        动态构建tools描述供DeepSeek V3使用
        
        Returns:
            List[Dict]: 工具描述列表
        """
        # 基础工具描述模板
        tool_templates = {
            "get_weather": {
                "name": "get_weather",
                "description": "获取指定城市的实时天气信息，包括温度、天气状况、湿度、风力等，并提供温馨的生活建议",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "城市名称，例如：北京、上海、广州。支持省市区名称，如'北京市'、'徐汇区'等"
                        }
                    },
                    "required": ["location"]
                }
            },
            "add_personal_info": {
                "name": "add_personal_info",
                "description": "记录家庭成员的基本个人信息，包括姓名、年龄、性别和健康状况。当用户主动提供这些信息时使用此工具，确保为每个家庭成员单独记录",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "person_name": {
                            "type": "string",
                            "description": "家庭成员姓名"
                        },
                        "age": {
                            "type": "string",
                            "description": "年龄"
                        },
                        "gender": {
                            "type": "string",
                            "description": "性别"
                        },
                        "health_condition": {
                            "type": "string",
                            "description": "健康状况描述"
                        }
                    },
                    "required": ["person_name"]
                }
            },
            "recall_personal_info": {
                "name": "recall_personal_info",
                "description": "回忆特定家庭成员的个人信息，包括年龄、性别和健康状况。当需要了解某个家庭成员的基本情况时使用此工具",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "person_name": {
                            "type": "string",
                            "description": "要查询的家庭成员姓名"
                        }
                    },
                    "required": ["person_name"]
                }
            },
            "intent_analyzer": {
                "name": "intent_analyzer",
                "description": "使用AI分析用户输入的真实意图，识别是否包含系统操作指令。基于语义理解而不是关键词匹配。",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "user_input": {
                            "type": "string",
                            "description": "用户输入的文本内容"
                        }
                    },
                    "required": ["user_input"]
                }
            },
            "list_family_members": {
                "name": "list_family_members",
                "description": "列出所有已记录个人信息的家庭成员姓名",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询词，固定为'列出所有家庭成员'"
                        }
                    },
                    "required": ["query"]
                }
            },
            "set_reminder": {
                "name": "set_reminder",
                "description": "为当前用户或其家庭成员创建提醒。用户表达提醒、到时通知、叫某人做某事时调用。请将不同说法归一成稳定的动作和对象。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient_ref": {"type": "string", "description": "接收人：self、原话姓名或关系称呼，如奶奶"},
                        "canonical_action": {"type": "string", "description": "规范动作，如服用、前往、联系、测量、出门"},
                        "canonical_object": {"type": "string", "description": "动作对象，如降压药、知春路地铁站；没有则为空"},
                        "task": {"type": "string", "description": "给用户展示的简短任务"},
                        "date": {"type": "string", "description": "ISO日期YYYY-MM-DD"},
                        "time": {"type": "string", "description": "24小时制HH:MM"},
                        "repeat": {"type": "string", "enum": ["once", "daily", "weekdays", "weekend"], "description": "重复规则"}
                    },
                    "required": ["recipient_ref", "canonical_action", "canonical_object", "task", "date", "time", "repeat"]
                }
            },
            "save_family_relationship": {
                "name": "save_family_relationship",
                "description": "仅当用户明确陈述家庭关系事实时记录。询问‘我奶奶是谁’绝不能调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relation": {"type": "string", "enum": ["奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿", "老伴", "父母", "祖辈", "孩子", "孙辈"]},
                        "target_name": {"type": "string", "description": "用户原话明确说出的姓名"},
                        "target_age": {"type": "integer", "description": "明确提到的年龄；未提到时省略"}
                    },
                    "required": ["relation", "target_name"]
                }
            },
            "query_family_relationship": {
                "name": "query_family_relationship",
                "description": "查询某个家庭关系对应的是谁，例如‘你认识我奶奶吗’。",
                "parameters": {
                    "type": "object",
                    "properties": {"relation": {"type": "string", "enum": ["奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿", "老伴", "父母", "祖辈", "孩子", "孙辈"]}},
                    "required": ["relation"]
                }
            },
            "record_health_event": {
                "name": "record_health_event",
                "description": "用户明确描述自己或家人近期身体不适时，记录全部症状。不要扩展成医学诊断。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "symptoms": {"type": "array", "items": {"type": "string"}, "description": "原话中的症状列表"}
                    },
                    "required": ["subject_ref", "symptoms"]
                }
            },
            "query_health_events": {
                "name": "query_health_events",
                "description": "查询自己或家人近期的健康和不适记录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "days": {"type": "integer", "minimum": 1, "maximum": 30, "description": "查询最近多少天，默认7"}
                    },
                    "required": ["subject_ref", "days"]
                }
            },
            "resolve_health_event": {
                "name": "resolve_health_event",
                "description": "用户明确表示自己或家人之前的近期症状已经缓解、消失或恢复时调用；保留历史但标记已恢复。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "symptoms": {"type": "array", "items": {"type": "string"}, "description": "已经恢复的症状"}
                    },
                    "required": ["subject_ref", "symptoms"]
                }
            },
            "save_preference": {
                "name": "save_preference",
                "description": "记录自己或家人明确、稳定的长期偏好。适用于爱吃、爱喝、平时喜欢、不喜欢等表达；临时的今天想吃或现在想玩不能记录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "category": {"type": "string", "enum": ["food", "activity", "entertainment", "habit", "other"]},
                        "polarity": {"type": "string", "enum": ["like", "dislike"]},
                        "item": {"type": "string", "description": "保留用户原话里的具体偏好对象，不要换成原话没有的词"}
                    },
                    "required": ["subject_ref", "category", "polarity", "item"]
                }
            },
            "query_preferences": {
                "name": "query_preferences",
                "description": "查询自己或某位家人的长期偏好。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "category": {"type": "string", "enum": ["food", "activity", "entertainment", "habit", "other"], "description": "明确限定类别时填写，否则省略"}
                    },
                    "required": ["subject_ref"]
                }
            },
            "update_member_profile": {
                "name": "update_member_profile",
                "description": "更新自己或家人的当前年龄和长期健康情况。年龄使用覆盖更新；长期疾病或体质可新增，也可在用户明确表示已经治愈或不再患有时解除。不要用于短期头疼、头晕等近期症状。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"},
                        "age": {"type": "integer", "minimum": 0, "maximum": 130, "description": "明确说出的当前年龄；未提到则省略"},
                        "health_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "condition": {"type": "string"},
                                    "status": {"type": "string", "enum": ["active", "resolved"]}
                                },
                                "required": ["condition", "status"]
                            }
                        }
                    },
                    "required": ["subject_ref"]
                }
            },
            "query_member_profile": {
                "name": "query_member_profile",
                "description": "查询自己或家人的当前年龄、长期健康情况和长期偏好，数据按家庭和成员隔离。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {"type": "string", "description": "self、原话姓名或关系称呼"}
                    },
                    "required": ["subject_ref"]
                }
            }
        }
        
        # 动态构建可用工具列表
        tools = []
        for tool_name in self.available_functions.keys():
            if tool_name in tool_templates:
                tools.append({
                    "type": "function",
                    "function": tool_templates[tool_name]
                })
        
        logger.info(f"动态构建工具列表: {[tool['function']['name'] for tool in tools]}")
        return tools
    
    async def _call_chat_api_with_tools(self, messages: List[Dict], tools: List[Dict], session_id: str, tool_context: Dict | None = None) -> Dict[str, Any]:
        """
        调用支持function calling的聊天API - 修复版本：包含对话历史
        """
        headers = {
            "Authorization": f"Bearer {settings.ARK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 获取对话历史并构建完整消息
        full_messages = await self._build_messages_with_history(messages, session_id)
        
        payload = {
            "model": settings.ARK_MODEL_NAME,
            "messages": full_messages,  # 使用包含历史的消息
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": settings.AGENT_MAX_TOKENS,
            "temperature": settings.AGENT_TEMPERATURE,
            "presence_penalty": 0.1,
            "frequency_penalty": 0.1,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.ARK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    api_response = response.json()
                    message = api_response["choices"][0]["message"]
                    
                    # 检查是否有tool calls
                    if "tool_calls" in message and message["tool_calls"]:
                        logger.info(f"检测到工具调用: {[tool_call['function']['name'] for tool_call in message['tool_calls']]}")
                        return await self._handle_tool_calls(
                            message, session_id, full_messages, tool_context or {}, tools, 2
                        )
                    else:
                        # 直接返回AI回复
                        cleaned_response = clean_response(message["content"])
                        return {
                            "success": True,
                            "response": cleaned_response,
                            "session_id": session_id,
                            "tool_used": False
                        }
                else:
                    error_detail = f"API返回状态码: {response.status_code}"
                    try:
                        error_body = response.json()
                        error_detail += f", 错误信息: {error_body}"
                        logger.error(f"聊天API调用失败: {error_detail}")
                    except:
                        error_detail += f", 响应内容: {response.text}"
                        logger.error(f"聊天API调用失败: {error_detail}")
                        
                    return {
                        "success": False,
                        "response": f"API状态码：{response.status_code}，抱歉，服务暂时不可用，请稍后再试。",
                        "error": error_detail
                    }
        
        except httpx.TimeoutException:
            logger.error("聊天API调用超时")
            return {
                "success": False,
                "response": "请求超时，请稍后重试。",
                "error": "API调用超时"
            }
        except Exception as e:
            logger.error(f"聊天API调用异常: {str(e)}")
            return {
                "success": False,
                "response": "聊天API调用异常:抱歉，服务暂时不可用，请稍后再试。",
                "error": str(e)
            }

    async def _build_messages_with_history(self, current_messages: List[Dict], session_id: str) -> List[Dict]:
        """
        构建包含对话历史的消息列表
        """
        # 获取对话历史
        conversation_history = self.memory.get_conversation_history(session_id)
        
        # 构建完整消息列表
        full_messages = []
        
        # 添加系统提示词（从current_messages中提取）
        system_message = None
        for msg in current_messages:
            if msg.get("role") == "system":
                system_message = msg
                break
        
        if system_message:
            full_messages.append(system_message)
        
        # 添加对话历史（最多最近4轮对话）
        for item in conversation_history[-4:]:  # 最近2轮用户+AI对话
            full_messages.append({"role": "user", "content": item["user"]})
            full_messages.append({"role": "assistant", "content": item["assistant"]})
        
        # 添加当前用户消息（从current_messages中提取）
        user_message = None
        for msg in current_messages:
            if msg.get("role") == "user":
                user_message = msg
                break
        
        if user_message:
            full_messages.append(user_message)
        
        logger.info(f"构建消息完成，系统消息: {1 if system_message else 0}, 历史轮数: {len(conversation_history)}, 总消息数: {len(full_messages)}")
        
        # 调试：打印消息结构
        for i, msg in enumerate(full_messages):
            role = msg.get("role", "unknown")
            content_preview = msg.get("content", "")[:50] + "..." if len(msg.get("content", "")) > 50 else msg.get("content", "")
            logger.debug(f"消息[{i}]: {role} - {content_preview}")
        
        return full_messages
    
    async def _handle_tool_calls(
        self,
        message: Dict,
        session_id: str,
        original_messages: List[Dict],
        tool_context: Dict | None = None,
        tools: List[Dict] | None = None,
        remaining_tool_rounds: int = 0,
    ) -> Dict[str, Any]:
        """
        处理tool calls并执行相应工具
        
        Args:
            message: 包含tool calls的消息
            session_id: 会话ID
            original_messages: 原始消息列表
            
        Returns:
            Dict: 处理结果
        """
        tool_calls = message["tool_calls"]
        tool_results = []
        action_results = []

        # A model may emit independent-looking calls in either order. Stateful
        # writes must be visible before dependent reads in the same turn, e.g.
        # “王刚是我爸爸，你知道他几岁吗”.
        write_tools = {
            "save_family_relationship", "update_member_profile", "save_preference",
            "record_health_event", "resolve_health_event", "set_reminder",
        }
        ordered_tool_calls = sorted(
            enumerate(tool_calls),
            key=lambda item: (0 if item[1]["function"]["name"] in write_tools else 1, item[0]),
        )

        for _, tool_call in ordered_tool_calls:
            tool_call_id = tool_call["id"]
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
            
            logger.info(f"执行工具: {function_name}, 参数: {function_args}")
            
            if self.action_service and function_name in {
                "set_reminder", "save_family_relationship", "query_family_relationship",
                "record_health_event", "resolve_health_event", "query_health_events",
                "save_preference", "query_preferences", "update_member_profile", "query_member_profile",
            }:
                execution = self.action_service.execute(function_name, function_args, tool_context or {})
                result = execution.get("content", "工具执行完成")
                action_results.append(execution)
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "tool_name": function_name,
                    "arguments": function_args,
                    "result": result,
                })
            elif function_name in self.available_functions:
                # 执行对应的工具函数
                result = await self.available_functions[function_name](function_args)
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "tool_name": function_name,
                    "arguments": function_args,
                    "result": result
                })
            else:
                logger.warning(f"未知工具: {function_name}")
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "tool_name": function_name,
                    "arguments": function_args,
                    "result": f"工具{function_name}暂不可用"
                })
        
        # If the normal Function Calling path discovers a system command,
        # promote it to the same structured result used by the first-pass
        # intent check.  Previously it was only shown to the LLM as text, so
        # the assistant could say “已设置” without the reminder being stored.
        promoted_command = self._promote_intent_tool_result(tool_results, session_id)
        if promoted_command:
            return promoted_command

        if tools and remaining_tool_rounds > 0:
            response = await self._continue_tool_conversation(
                original_messages, message, tool_results, session_id,
                tools, tool_context or {}, remaining_tool_rounds,
            )
            response["tool_results"] = tool_results + list(response.get("tool_results") or [])
            response["tool_used"] = True
        else:
            # No more planning rounds: ask the model to express the actual
            # tool result without exposing executable tools again.
            final_response = await self._get_tool_final_response(original_messages, message, tool_results, session_id)
            response = {
                "success": True,
                "response": final_response,
                "session_id": session_id,
                "tool_used": True,
                "tool_results": tool_results
            }
        # The model writes the user-facing sentence, but executable state is
        # always copied from the backend result.  This prevents a fluent final
        # answer from becoming the source of truth for reminders or memory.
        direct = next((item for item in reversed(action_results) if item.get("direct_response")), None)
        if direct:
            for key in (
                "command_type", "alarm_control", "reminder", "reminder_persisted", "health_events",
                "resolved_health_events", "preference", "preferences", "profile_updates",
                "member_profile", "family_facts",
            ):
                if key in direct:
                    response[key] = direct[key]
        return response

    async def _continue_tool_conversation(
        self,
        original_messages: List[Dict],
        tool_message: Dict,
        tool_results: List[Dict],
        session_id: str,
        tools: List[Dict],
        tool_context: Dict,
        remaining_tool_rounds: int,
    ) -> Dict[str, Any]:
        """Let the main model plan a dependent next tool call, up to a limit."""
        messages = original_messages.copy()
        messages.append(tool_message)
        messages.extend(self._build_tool_result_messages(tool_results))
        payload = {
            "model": settings.ARK_MODEL_NAME,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": settings.AGENT_MAX_TOKENS,
            "temperature": settings.AGENT_TEMPERATURE,
        }
        headers = {
            "Authorization": f"Bearer {settings.ARK_API_KEY}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient() as client:
                api_response = await client.post(settings.ARK_API_URL, headers=headers, json=payload, timeout=30.0)
            if api_response.status_code != 200:
                return {
                    "success": True, "response": self._construct_fallback_response(tool_results),
                    "session_id": session_id, "tool_used": True, "tool_results": [],
                }
            next_message = api_response.json()["choices"][0]["message"]
            if next_message.get("tool_calls"):
                return await self._handle_tool_calls(
                    next_message, session_id, messages, tool_context,
                    tools, remaining_tool_rounds - 1,
                )
            return {
                "success": True,
                "response": clean_response(next_message.get("content", "")),
                "session_id": session_id,
                "tool_used": True,
                "tool_results": [],
            }
        except Exception as exc:
            logger.error(f"继续多步工具调用失败: {exc}")
            return {
                "success": True, "response": self._construct_fallback_response(tool_results),
                "session_id": session_id, "tool_used": True, "tool_results": [],
            }

    @staticmethod
    def _promote_intent_tool_result(tool_results: List[Dict], session_id: str) -> Dict[str, Any] | None:
        """Turn a fallback intent tool result into an executable command."""
        for tool_result in tool_results:
            if tool_result.get("tool_name") != "intent_analyzer":
                continue
            try:
                intent_data = json.loads(tool_result.get("result", ""))
            except (TypeError, json.JSONDecodeError):
                continue
            if not intent_data.get("is_system_command") or intent_data.get("intent_type") != "SET_ALARM":
                continue
            alarm = intent_data.get("alarm_info") or {}
            action = "needs_time" if alarm.get("needs_time") else "set"
            repeat_text = "每天" if alarm.get("repeat_desc") == "daily" else ""
            if action == "needs_time":
                response = f"好的，我可以{repeat_text}提醒您{reminder_task_text(alarm.get('name'))}。请问要在几点提醒您？"
            else:
                response = f"好的，已设置{repeat_text}{alarm.get('display_time', '08:00')}的提醒：{reminder_task_text(alarm.get('name'))}。"
            return {
                "success": True,
                "response": response,
                "session_id": session_id,
                "agent_type": "companion",
                "is_system_command": True,
                "command_type": "SET_ALARM",
                "tool_used": True,
                "tool_results": tool_results,
                "alarm_control": {"action": action, "alarm_info": alarm, "timestamp": datetime.now().isoformat()},
            }
        return None
    
    def _build_tool_result_messages(self, tool_results: List[Dict]) -> List[Dict]:
        """Build OpenAI-compatible tool result messages."""
        return [
            {
                "role": "tool",
                "content": result["result"],
                "tool_call_id": result["tool_call_id"],
            }
            for result in tool_results
        ]
    
    async def _get_tool_final_response(self, original_messages: List[Dict], tool_message: Dict, tool_results: List[Dict], session_id: str) -> str:
        """
        获取工具执行后的最终回复
        
        Args:
            original_messages: 原始消息列表
            tool_message: 工具调用消息
            tool_results: 工具执行结果
            session_id: 会话ID
            
        Returns:
            str: 最终回复内容
        """
        try:
            # 构建包含工具结果的消息
            messages = original_messages.copy()
            
            # 添加AI的工具调用消息
            messages.append(tool_message)
            
            # 添加工具执行结果
            messages.extend(self._build_tool_result_messages(tool_results))
            
            # 调用API获取最终回复
            headers = {
                "Authorization": f"Bearer {settings.ARK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": settings.ARK_MODEL_NAME,
                "messages": messages,
                "stream": False,
                "max_tokens": settings.AGENT_MAX_TOKENS,
                "temperature": settings.AGENT_TEMPERATURE,
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.ARK_API_URL, headers=headers, json=payload, timeout=30.0)
                if response.status_code == 200:
                    api_response = response.json()
                    final_text = api_response["choices"][0]["message"]["content"]
                    return clean_response(final_text)
                else:
                    # 如果最终调用失败，使用工具结果直接构造回复
                    return self._construct_fallback_response(tool_results)
        except Exception as e:
            logger.error(f"获取工具最终回复失败: {str(e)}")
            return self._construct_fallback_response(tool_results)
    
    def _construct_fallback_response(self, tool_results: List[Dict]) -> str:
        """
        构造降级回复
        
        Args:
            tool_results: 工具执行结果
            
        Returns:
            str: 降级回复内容
        """
        if not tool_results:
            return "我已经尝试查询相关信息，但暂时无法获取完整结果。"
        
        if len(tool_results) == 1:
            return str(tool_results[0]["result"])

        response_parts = ["已经处理了这些事情："]
        for result in tool_results:
            response_parts.append(f"\n{result['result']}")
        
        return "".join(response_parts)
    
    def _build_system_prompt(self, mode_profile: ModeProfile = None, device_config: DeviceConfig = None, session_location: str = None, actor_name: str = None, persistent_context: str = None) -> str:
        """
        构建系统提示词
        
        Returns:
            str: 系统提示词
        """
        return self.prompt_builder.build_system_prompt(mode_profile, device_config, session_location, actor_name, persistent_context)


