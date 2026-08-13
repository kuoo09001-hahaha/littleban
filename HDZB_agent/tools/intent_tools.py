
"""
意图识别工具 - 通过prompt分类，代码拼接JSON
"""

import json
import logging
import httpx
from typing import Dict, Any, Type, ClassVar
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from config.settings import settings
import re
from datetime import datetime, timedelta
from services.reminder_slot_service import extract_reminder_date, extract_reminder_task, extract_time, reminder_title_hint

logger = logging.getLogger("intent_tools")

class IntentAnalyzerInput(BaseModel):
    user_input: str = Field(description="用户输入")

class IntentAnalyzerTool(BaseTool):
    """意图识别工具 - 通过prompt分类，代码拼接JSON"""
    
    name: str = "intent_analyzer"
    description: str = "分析用户意图，返回分类结果"
    args_schema: Type[BaseModel] = IntentAnalyzerInput
    
    # 使用ClassVar注解系统指令映射
    SYSTEM_COMMANDS: ClassVar[Dict[str, str]] = {
        "SYSTEM_SHUTDOWN": "SYSTEM_SHUTDOWN",
        "SYSTEM_RESTART": "SYSTEM_RESTART", 
        "CALL_CONTACT_1": "CALL_CONTACT_1",
        "CALL_CONTACT_2": "CALL_CONTACT_2",
        "CALL_CONTACT_3": "CALL_CONTACT_3",
        "VOLUME_MUTE": "VOLUME_MUTE",
        "VOLUME_SET": "VOLUME_SET",
        "SET_ALARM": "SET_ALARM"
    }
    
    def _run(self, user_input: str) -> str:
        import asyncio
        return asyncio.run(self._arun(user_input))
    
    async def _arun(self, user_input: str) -> str:
        try:
            # Reminder intent is high-impact and common. Recognise the stable
            # phrasing locally first so a transient LLM timeout cannot turn a
            # reminder request into ordinary chat.
            local_alarm = self._extract_local_reminder_intent(user_input)
            if local_alarm:
                return json.dumps(local_alarm, ensure_ascii=False)

            # 简化后的prompt，支持多日期闹钟
            system_prompt = """分析用户意图，返回分类和参数。

音量指令编码：
- 设置音量：1xxx（如1070=音量70）
- 减少音量：2xxx（如2020=减少20）
- 增加音量：3xxx（如3020=增加20）

闹钟指令格式：
闹钟设置类|时间类型|时间值|日期值|重复类型|备注名称

时间类型：absolute或relative
时间值：HHMM格式（如0800）或分钟数（如120）
日期值：YYYYMMDD格式，无日期用"today"
重复类型：0=单次,1=每天,2=工作日,3=周末,4=自定义,1-7=周几,多日期用逗号分隔如"3,5"

示例：
"音量调到50" → 音量设置类|1050
"声音大点" → 音量增加类|3020
"下午三点提醒" → 闹钟设置类|absolute|1500|today|0|提醒
"每周三和周五提醒" → 闹钟设置类|absolute|0800|today|3,5|提醒

分类：关机类、重启类、静音类、音量增加类、音量减少类、音量设置类、闹钟设置类、呼叫联系人1/2/3、无指令类

只返回分类和参数，格式：分类|参数1|参数2|..."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            headers = {
                "Authorization": f"Bearer {settings.ARK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": settings.ARK_MODEL_NAME,
                "messages": messages,
                "stream": False,
                "max_tokens": 50,
                "temperature": 0.1
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    settings.ARK_API_URL,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    api_response = response.json()
                    llm_response = api_response["choices"][0]["message"]["content"].strip()
                    logger.info(f"LLM响应: {llm_response}")
                    
                    # 在代码中拼接JSON
                    return self._build_intent_response(llm_response, user_input)
                else:
                    logger.error(f"意图识别API调用失败: {response.status_code}")
                    return self._get_fallback_response()
                    
        except Exception as e:
            logger.exception("意图识别失败")
            return self._get_fallback_response()

    def _extract_local_reminder_intent(self, user_input: str) -> dict | None:
        """Deterministically recognise reminder requests before the LLM call."""
        if not any(word in user_input for word in ("提醒", "闹钟", "记得", "告诉", "转告")):
            return None
        if any(word in user_input for word in ("删除", "取消", "关闭", "不要", "移除")):
            title_hint = "吃药" if any(word in user_input for word in ("吃药", "服药")) else ""
            return {"intent_type": "DELETE_ALARM", "is_system_command": True, "alarm_info": {"name": title_hint}}
        if not any(word in user_input for word in ("吃药", "服药", "吃饭", "打电话", "复诊", "测血压", "上课", "提醒", "告诉", "转告")):
            return None
        time_info = self._extract_time_from_text(user_input)
        has_time = extract_time(user_input) is not None
        repeat_desc = "daily" if any(word in user_input for word in ("每天", "每日", "天天")) else "once"
        title_hint = reminder_title_hint(user_input)
        if "降压药" in user_input:
            name = "吃降压药"
        elif extract_reminder_task(user_input):
            name = extract_reminder_task(user_input)
        elif title_hint:
            name = title_hint
        else:
            name = "提醒"
        reminder_date = extract_reminder_date(user_input)
        return {
            "intent_type": "SET_ALARM",
            "is_system_command": True,
            "alarm_info": {
                "time_type": "absolute", "time_value": time_info["time_value"],
                "date_value": reminder_date.replace("-", ""), "display_time": time_info["display_time"],
                "display_date": reminder_date, "name": name, "repeat_desc": repeat_desc,
                "needs_time": not has_time,
            },
        }
    
    def _build_intent_response(self, llm_response: str, user_input: str) -> str:
        """根据LLM响应构建意图响应JSON"""
        
        # 解析LLM响应
        classification, params = self._parse_llm_response(llm_response)
        
        # 分类到指令的映射
        classification_to_intent = {
            "关机类": {
                "intent_type": "SYSTEM_SHUTDOWN",
                "is_system_command": True
            },
            "重启类": {
                "intent_type": "SYSTEM_RESTART", 
                "is_system_command": True
            },
            "静音类": {
                "intent_type": "VOLUME_MUTE",
                "is_system_command": True
            },
            "音量增加类": {
                "intent_type": "VOLUME_SET",
                "is_system_command": True,
                "volume_change": self._decode_volume_code(params, "increase") if params else 3020
            },
            "音量减少类": {
                "intent_type": "VOLUME_SET", 
                "is_system_command": True,
                "volume_change": self._decode_volume_code(params, "decrease") if params else 2040
            },
            "音量设置类": {
                "intent_type": "VOLUME_SET",
                "is_system_command": True,
                "volume_change": self._decode_volume_code(params, "absolute") if params else self._extract_volume_value(user_input)
            },
            "闹钟设置类": {
                "intent_type": "SET_ALARM",
                "is_system_command": True,
                "alarm_info": self._parse_alarm_params(params) if params else self._extract_alarm_info(user_input)
            },
            "呼叫联系人1": {
                "intent_type": "CALL_CONTACT_1",
                "is_system_command": True
            },
            "呼叫联系人2": {
                "intent_type": "CALL_CONTACT_2",
                "is_system_command": True
            },
            "呼叫联系人3": {
                "intent_type": "CALL_CONTACT_3", 
                "is_system_command": True
            }
        }
        
        # 获取对应的意图配置
        intent_config = classification_to_intent.get(classification)
        
        if intent_config:
            return json.dumps(intent_config, ensure_ascii=False)
        else:
            # 无指令类或其他未知分类
            return json.dumps({
                "intent_type": "NONE",
                "is_system_command": False
            }, ensure_ascii=False)
    
    def _parse_llm_response(self, llm_response: str) -> tuple:
        """解析LLM响应，返回分类和参数"""
        try:
            logger.info(f"原始LLM响应: '{llm_response}'")
            
            # 检查是否包含竖线分隔符
            if "|" in llm_response:
                parts = llm_response.split("|")
                classification = parts[0].strip()
                params = parts[1:] if len(parts) > 1 else None
                
                logger.info(f"解析结果: 分类={classification}, 参数={params}")
                return classification, params
            else:
                # 没有竖线，直接返回分类
                logger.info(f"无参数: {llm_response}")
                return llm_response, None
                
        except Exception as e:
            logger.error(f"解析LLM响应失败: {llm_response}, 错误: {e}")
            return "无指令类", None
    
    def _decode_volume_code(self, params: list, operation_type: str) -> int:
        """解码音量编码"""
        try:
            if not params or len(params) == 0:
                # 如果没有参数，根据操作类型返回默认值
                if operation_type == "increase":
                    return 3020
                elif operation_type == "decrease":
                    return 2040
                else:  # absolute
                    return 1050
            
            volume_code = params[0]
            
            # 解析编码 - 4位数字
            if len(volume_code) == 4 and volume_code.isdigit():
                prefix = volume_code[0]
                value = int(volume_code[1:])
                
                # 根据前缀返回对应的编码值
                if prefix == "1":  # 绝对值设置
                    return 1000 + value
                elif prefix == "2":  # 减少
                    return 2000 + value
                elif prefix == "3":  # 增加
                    return 3000 + value
                else:
                    logger.warning(f"未知的音量编码前缀: {prefix}")
            
            # 如果编码格式不正确，返回默认值
            logger.warning(f"无效的音量编码格式: {volume_code}")
            if operation_type == "increase":
                return 3020
            elif operation_type == "decrease":
                return 2040
            else:
                return 1050
                
        except Exception as e:
            logger.error(f"解码音量编码失败: {params}, 错误: {e}")
            return 1050
    
    def _parse_alarm_params(self, params: list) -> dict:
        """解析闹钟参数 - 支持多日期"""
        try:
            if not params or len(params) < 5:
                return self._get_default_alarm_info()
            
            time_type = params[0].strip().lower()
            time_value = params[1].strip()
            date_value = params[2].strip()
            repeat_type = params[3].strip()
            alarm_name = params[4].strip()
            
            alarm_info = {
                "time_type": time_type,
                "time_value": time_value,
                "date_value": date_value,
                "repeat_type": repeat_type,
                "name": alarm_name,
                "repeat_desc": "once"
            }
            
            # 处理时间
            if time_type == "absolute" and len(time_value) == 4 and time_value.isdigit():
                hour = int(time_value[:2])
                minute = int(time_value[2:])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    alarm_info["display_time"] = f"{hour:02d}:{minute:02d}"
                else:
                    alarm_info["display_time"] = "08:00"
            elif time_type == "relative":
                try:
                    minutes = int(time_value)
                    future_time = datetime.now() + timedelta(minutes=minutes)
                    alarm_info["display_time"] = future_time.strftime("%H:%M")
                    alarm_info["minutes_from_now"] = minutes
                except ValueError:
                    alarm_info["display_time"] = "08:00"
            else:
                alarm_info["display_time"] = "08:00"
            
            # 处理日期
            if date_value == "today":
                today = datetime.now().strftime("%Y%m%d")
                alarm_info["date_value"] = today
                alarm_info["display_date"] = "今天"
            elif len(date_value) == 8 and date_value.isdigit():
                alarm_info["display_date"] = f"{date_value[4:6]}月{date_value[6:8]}日"
            else:
                today = datetime.now().strftime("%Y%m%d")
                alarm_info["date_value"] = today
                alarm_info["display_date"] = "今天"
            
            # 解析重复类型 - 支持多日期
            alarm_info["repeat_desc"] = self._parse_repeat_type(repeat_type)
            
            return alarm_info
            
        except Exception as e:
            logger.error(f"解析闹钟参数失败: {params}, 错误: {e}")
            return self._get_default_alarm_info()
    
    def _parse_repeat_type(self, repeat_type: str) -> str:
        """解析重复类型，支持多日期"""
        # 单个重复类型
        repeat_map = {
            "0": "once",        # 单次
            "1": "daily",       # 每天
            "2": "weekdays",    # 工作日
            "3": "weekend",     # 周末
            "4": "custom"       # 自定义
        }
        
        if repeat_type in repeat_map:
            return repeat_map[repeat_type]
        
        # 多日期处理（逗号分隔）
        if "," in repeat_type:
            days = repeat_type.split(",")
            day_names = []
            for day in days:
                day = day.strip()
                if day in "1234567":
                    week_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                    day_names.append(week_days[int(day)-1])
            
            if day_names:
                return f"weekly_{'_'.join(day_names)}"
        
        # 单个周几
        elif repeat_type in "1234567":
            week_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            return f"weekly_{week_days[int(repeat_type)-1]}"
        
        return "once"
    
    def _get_default_alarm_info(self) -> dict:
        """获取默认闹钟信息"""
        today = datetime.now().strftime("%Y%m%d")
        
        return {
            "time_type": "absolute",
            "time_value": "0800",
            "date_value": today,
            "display_time": "08:00",
            "display_date": "今天",
            "repeat_type": "0",
            "name": "闹钟",
            "repeat_desc": "once"
        }
    
    def _extract_volume_value(self, user_input: str) -> int:
        """从用户输入中提取音量数值（降级方案）"""
        try:
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                target_volume = int(numbers[0])
                return 1000 + target_volume
            else:
                return 1050
        except:
            return 1050
    
    def _extract_alarm_info(self, user_input: str) -> dict:
        """从用户输入中提取闹钟信息（降级方案）"""
        try:
            time_info = self._extract_time_from_text(user_input)
            
            alarm_info = {
                "time_type": "absolute",
                "time_value": time_info["time_value"],
                "date_value": datetime.now().strftime("%Y%m%d"),
                "display_time": time_info["display_time"],
                "display_date": "今天",
                "repeat_type": "0",
                "name": "提醒",
                "repeat_desc": "once"
            }
            
            return alarm_info
        except:
            return self._get_default_alarm_info()
    
    def _extract_time_from_text(self, text: str) -> dict:
        """从文本中提取时间信息"""
        result = {
            "time_value": "0800",
            "display_time": "08:00"
        }
        
        parsed_time = extract_time(text)
        if parsed_time:
            return {"time_value": parsed_time.replace(":", ""), "display_time": parsed_time}

        time_patterns = [
            (r'(中午)', lambda h, m: (12, 0)),
            (r'(\d{1,2})点(\d{1,2})分', lambda h, m: (int(h), int(m))),
            (r'(\d{1,2}):(\d{1,2})', lambda h, m: (int(h), int(m))),
            (r'上午(\d{1,2})点', lambda h, m: (int(h), 0)),
            (r'下午(\d{1,2})点', lambda h, m: (int(h) + 12 if int(h) < 12 else int(h), 0)),
            (r'晚上(\d{1,2})点', lambda h, m: (int(h) + 12 if int(h) < 12 else int(h), 0)),
            (r'(\d{1,2})点', lambda h, m: (int(h), 0)),
        ]
        
        for pattern, converter in time_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    hour, minute = converter(groups[0], groups[1])
                else:
                    hour, minute = converter(groups[0], 0)
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    result["time_value"] = f"{hour:02d}{minute:02d}"
                    result["display_time"] = f"{hour:02d}:{minute:02d}"
                break
        
        return result
    
    def _get_fallback_response(self) -> str:
        """获取降级响应"""
        return json.dumps({
            "intent_type": "NONE",
            "is_system_command": False
        }, ensure_ascii=False)
