"""
老年人陪伴AI Agent服务 - 主应用模块
基于FastAPI的AI Agent服务，为老年人提供智能陪伴、天气查询、记忆管理等功能
修复启动事件和服务器配置问题
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any
import logging
import uuid
import re
from datetime import datetime
import contextlib

# 导入自定义模块
from agents.companion_agent import CompanionAgent
from tools.chat_tools import ElderlyChatTool, MemoryRecallTool, KnowledgeSearchTool, WeatherTool, LocationTool, AddPersonalInfoTool, RecallPersonalInfoTool, ListFamilyMembersTool
from tools.intent_tools import IntentAnalyzerTool  # 新增导入
from memory.conversation_memory import EnhancedConversationMemory
from config.settings import settings
from api.devices import create_devices_router
from api.memory import create_memory_router
from api.personal_info import create_personal_info_router
from api.sessions import create_sessions_router
from api.status import create_status_router
from api.weather import create_weather_router
from api.traces import create_traces_router
from api.reminders import create_reminders_router
from api.location import create_location_router
from api.health_memory import create_health_memory_router
from api.family import create_family_router
from domain.modes import get_mode_profile
from schemas.agent import AgentRequest, AgentResponse
from services.device_config_service import DeviceConfigService
from services.device_mode_service import DeviceModeService
from services.profile_service import ProfileService
from storage.sqlite_store import SQLiteStore
from utils.session_utils import extract_session_id_from_message, remove_filename_markers
from observability.tracing import TraceStore
from services.reminder_slot_service import (
    alarm_date_to_iso,
    extract_reminder_date,
    extract_time,
    extract_reminder_task,
    find_reminder_recipient,
    format_reminder_completion_status,
    format_reminder_date,
    is_reminder_recall_query,
    is_reminder_completion_query,
    reminder_title_hint,
)
from services.health_memory_service import extract_activity, extract_subject, extract_symptom, format_activity_events, format_events, inverse_relation, is_health_query, query_activity, query_subject, query_window_start
from services.family_fact_service import extract_explicit_facts, extract_named_age, extract_named_relationship, format_persistent_context, normalize_person_name

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("elderly_agent_service")

# 全局变量
agents = {}
conversation_memory = EnhancedConversationMemory(
    max_token_limit=settings.MEMORY_MAX_TOKENS,
    window_size=settings.MEMORY_WINDOW_SIZE
)
active_sessions = {}
sqlite_store = SQLiteStore(settings.SQLITE_DB_PATH)
device_mode_service = DeviceModeService(store=sqlite_store)
device_config_service = DeviceConfigService(sqlite_store)
profile_service = ProfileService(sqlite_store)
trace_store = TraceStore()

def get_companion_agent():
    """Return the initialized companion agent, if available."""
    return agents.get("companion")

def get_agents():
    """Return initialized agent state."""
    return agents

def get_active_sessions():
    """Return active session state."""
    return active_sessions

def get_conversation_memory():
    """Return conversation memory state."""
    return conversation_memory

def get_device_mode_service():
    """Return device mode service."""
    return device_mode_service

def get_device_config_service():
    """Return device config service."""
    return device_config_service

def get_trace_store():
    """Return structured request traces for evaluation and debugging."""
    return trace_store

def get_sqlite_store():
    return sqlite_store

def setup_agents():
    """
    初始化各种Agent实例
    
    创建陪伴聊天Agent，集成天气查询、位置服务、记忆回忆等工具
    """
    
    # 创建工具实例
    chat_tool = ElderlyChatTool()
    memory_tool = MemoryRecallTool()
    knowledge_tool = KnowledgeSearchTool()
    weather_tool = WeatherTool()  # 使用高德天气的WeatherTool，已优化缓存
    location_tool = LocationTool()
    add_personal_info_tool = AddPersonalInfoTool()
    recall_personal_info_tool = RecallPersonalInfoTool()
    list_family_members_tool = ListFamilyMembersTool()
    intent_analyzer_tool = IntentAnalyzerTool()  # 意图识别工具
    
    tools = [
        chat_tool, memory_tool, knowledge_tool, 
        weather_tool, location_tool,
        add_personal_info_tool, recall_personal_info_tool, list_family_members_tool,
        intent_analyzer_tool  # 意图识别工具
    ]
    
    # 创建陪伴Agent - 支持function calling版本
    companion_agent = CompanionAgent(tools, conversation_memory, profile_service=profile_service)
    agents["companion"] = companion_agent
    
    logger.info("AI Agent初始化完成 - 已集成家庭成员个人信息管理")
    logger.info(f"回复最大长度: {settings.AGENT_MAX_TOKENS} tokens")
    logger.info(f"高德API密钥状态: {'已配置' if settings.AMAP_API_KEY and settings.AMAP_API_KEY != '您的高德API密钥' else '未配置'}")
    logger.info(f"可用工具数量: {len(tools)}")
    logger.info(f"新增工具: 个人信息管理 (添加、查询、列出家庭成员)")
    logger.info(f"新增工具: LLM意图识别")

# 使用新的 lifespan 事件处理器替代已弃用的 on_event
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    setup_agents()
    logger.info("老年人陪伴AI Agent服务启动完成 - 使用DeepSeek V3和高德天气API")
    yield
    # 关闭时清理资源
    logger.info("老年人陪伴AI Agent服务正在关闭...")

# 创建FastAPI应用，使用 lifespan 管理启动和关闭
app = FastAPI(
    title="老年人陪伴AI Agent服务", 
    version="2.0.0",
    description="基于AI的老年人智能陪伴服务，提供聊天陪伴、天气查询、记忆管理等功能",
    lifespan=lifespan
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

weather_router = create_weather_router()
personal_info_router = create_personal_info_router(get_companion_agent)
sessions_router = create_sessions_router(get_active_sessions, get_conversation_memory)
memory_router = create_memory_router(get_conversation_memory)
status_router = create_status_router(get_agents, get_active_sessions, get_conversation_memory)
devices_router = create_devices_router(get_device_mode_service, get_device_config_service)
traces_router = create_traces_router(get_trace_store)
reminders_router = create_reminders_router(get_sqlite_store)
location_router = create_location_router(get_sqlite_store)
health_memory_router = create_health_memory_router(get_sqlite_store)
family_router = create_family_router(get_sqlite_store)
app.include_router(weather_router)
app.include_router(personal_info_router)
app.include_router(sessions_router)
app.include_router(memory_router)
app.include_router(status_router)
app.include_router(devices_router)
app.include_router(traces_router)
app.include_router(reminders_router)
app.include_router(location_router)
app.include_router(health_memory_router)
app.include_router(family_router)
app.mount("/app", StaticFiles(directory=".", html=True), name="web_app")

@app.post("/agent/chat", response_model=AgentResponse)
async def agent_chat_endpoint(request: AgentRequest):
    """
    AI Agent聊天端点 - 修复版本：支持文件名session_id和连续对话
    """
    
    start_time = datetime.now()
    
    # 第一步：尝试从文件名提取session_id
    filename_session_id = extract_session_id_from_message(request.message)
    
    # 第二步：确定最终的session_id
    # 优先级：显式session_id > 文件名session_id > 新生成
    if request.session_id:
        session_id = request.session_id
        logger.info(f"使用显式session_id: {session_id}")
    elif filename_session_id:
        session_id = filename_session_id
        logger.info(f"从文件名提取session_id: {session_id}")
    else:
        session_id = str(uuid.uuid4())
        logger.info(f"生成新session_id: {session_id}")

    # A household profile carries the actual person's age. Prefer it to a
    # manually selected UI mode so a child automatically gets child-safe
    # responses even when sharing one local device with an elder.
    actor_profile = sqlite_store.get_household_member(request.family_id, request.actor_name) if request.actor_name else None
    effective_mode = request.mode
    if actor_profile and actor_profile.get("age") is not None:
        effective_mode = "child" if actor_profile["age"] < 18 else "elder"

    try:
        resolved_mode = device_mode_service.resolve_mode(
            device_id=session_id,
            request_mode=effective_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 第三步：会话管理
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "created_at": datetime.now(),
            "agent_type": request.agent_type,
            "message_count": 1,
            "last_active": datetime.now(),
            "source": "filename" if filename_session_id else ("explicit" if request.session_id else "new")
        }
        logger.info(f"创建新会话: {session_id}")
    else:
        active_sessions[session_id]["last_active"] = datetime.now()
        active_sessions[session_id]["message_count"] += 1
        logger.info(f"继续现有会话: {session_id}, 消息计数: {active_sessions[session_id]['message_count']}")
    
    # 第四步：清理消息内容（移除文件名标记）
    clean_message = remove_filename_markers(request.message)
    
    # 选择Agent类型，默认为陪伴Agent
    agent_type = request.agent_type
    if agent_type not in agents:
        agent_type = "companion"
        logger.warning(f"未知Agent类型: {request.agent_type}，使用默认companion")
    
    agent = agents[agent_type]
    
    try:
        mode_profile = get_mode_profile(resolved_mode.mode)
        device_config = device_config_service.get_config(session_id)
        location = sqlite_store.get_session_location(session_id)

        # Complete a reminder that asked for its missing time in a previous
        # turn. This happens before the LLM so short replies such as “早上8点”
        # are interpreted reliably and survive service restarts.
        pending_reminder = sqlite_store.get_pending_reminder(session_id)
        pending_time = extract_time(clean_message) if pending_reminder else None
        delete_reminder_request = bool(re.search(r"(?:删除|取消|关闭|不要|移除).{0,12}(?:提醒|闹钟|吃药|服药)", clean_message))
        # First persist a relationship stated in this very message.  This
        # allows “我奶奶是王秀芬…提醒她” to resolve the recipient immediately.
        named_relationship = extract_named_relationship(clean_message)
        named_age = extract_named_age(clean_message)
        relationship_target = named_relationship[1] if named_relationship else None
        if named_relationship and request.actor_name:
            relation, target_name = named_relationship
            target_age = named_age[1] if named_age and named_age[0] == target_name else None
            sqlite_store.add_household_member(request.family_id, target_name, age=target_age)
            sqlite_store.set_family_relationship(request.family_id, request.actor_name, target_name, relation)
            inverse = inverse_relation(request.actor_name, relation)
            if inverse:
                sqlite_store.set_family_relationship(request.family_id, target_name, request.actor_name, inverse)

        household_members = sqlite_store.list_household_members(request.family_id)
        # Repair earlier records made before name parsing learned to remove
        # trailing age words, e.g. “王秀芬今年” -> “王秀芬”.
        member_names = {member["member_name"] for member in household_members}
        if request.actor_name:
            for relation_record in sqlite_store.list_member_relationships(request.family_id, request.actor_name):
                corrected_name = normalize_person_name(relation_record["target_name"])
                if corrected_name in member_names and corrected_name != relation_record["target_name"]:
                    sqlite_store.repair_relationship_target(
                        request.family_id, request.actor_name, relation_record["target_name"], corrected_name
                    )
        named_member = next((member["member_name"] for member in household_members if member["member_name"] in clean_message), None)
        reminder_recipient = find_reminder_recipient(
            clean_message, request.actor_name, [member["member_name"] for member in household_members]
        )
        if not reminder_recipient and relationship_target and re.search(r"(?:提醒|记得|闹钟).{0,10}(?:她|他)", clean_message):
            reminder_recipient = relationship_target
        spoken_recipient_relation = next(
            (
                relation for relation in ("奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿")
                if re.search(rf"(?:提醒|记得|闹钟|告诉|转告).{{0,8}}我(?:的)?{relation}", clean_message)
            ),
            None,
        )
        if not reminder_recipient and spoken_recipient_relation and request.actor_name:
            related_member = sqlite_store.find_member_by_spoken_relation(
                request.family_id, request.actor_name, spoken_recipient_relation
            )
            reminder_recipient = related_member["member_name"] if related_member else None
        recipient_session_id = (
            sqlite_store.member_session_id(request.family_id, reminder_recipient) if reminder_recipient else session_id
        )
        reminder_recall = is_reminder_recall_query(clean_message)
        reminder_completion_query = is_reminder_completion_query(clean_message)
        identity_query = bool(
            request.actor_name
            and re.search(r"(?:你知道|你记得)?\s*我(?:是|叫)?谁(?:吗|嘛)?[？?]?$", clean_message.strip())
        )
        health_subject = (query_subject(clean_message) or named_member) if is_health_query(clean_message) else None
        status_recipient = named_member
        if reminder_completion_query and not status_recipient and request.actor_name:
            status_relation = next((item for item in ("奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "老伴", "孙子", "孙女", "儿子", "女儿") if item in clean_message), None)
            related = sqlite_store.find_member_by_spoken_relation(request.family_id, request.actor_name, status_relation) if status_relation else None
            status_recipient = related["member_name"] if related else None
        activity_subject = query_subject(clean_message) or named_member
        activity = query_activity(clean_message) if activity_subject else None
        profile_subject = next((relation for relation in ("孙子", "孙女", "儿子", "女儿", "奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "老伴") if relation in clean_message), None)
        relation_match = re.search(r"(.{1,32}?)是我的(孙子|孙女|儿子|女儿|奶奶|爷爷|爸爸|妈妈|外婆|外公|老伴)", clean_message)
        if relation_match and request.actor_name:
            target_name, relation = relation_match.groups()
            target_name = normalize_person_name(target_name)
            if sqlite_store.get_household_member(request.family_id, target_name):
                sqlite_store.set_family_relationship(request.family_id, request.actor_name, target_name, relation)
                inverse = inverse_relation(request.actor_name, relation)
                if inverse:
                    sqlite_store.set_family_relationship(request.family_id, target_name, request.actor_name, inverse)
        for fact_key, fact_value in extract_explicit_facts(clean_message, request.actor_name):
            sqlite_store.upsert_family_fact(request.family_id, request.actor_name, fact_key, fact_value, session_id)
        persistent_context = format_persistent_context(
            actor_profile,
            sqlite_store.list_member_relationships(request.family_id, request.actor_name) if request.actor_name else [],
            sqlite_store.list_family_facts(request.family_id, request.actor_name) if request.actor_name else [],
        )
        is_profile_query = profile_subject and any(word in clean_message for word in ("信息", "多大", "几岁", "叫什么", "名字", "年龄"))
        if identity_query:
            age_text = f"，今年{actor_profile['age']}岁" if actor_profile and actor_profile.get("age") is not None else ""
            result = {
                "success": True,
                "response": f"当然知道，您是{request.actor_name}{age_text}。",
                "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                "current_actor": request.actor_name,
            }
        elif reminder_completion_query and status_recipient and request.actor_name:
            requested_date = extract_reminder_date(clean_message)
            reminders = sqlite_store.find_reminder_status_for_creator(
                sqlite_store.member_session_id(request.family_id, status_recipient),
                request.actor_name,
                requested_date,
                reminder_title_hint(clean_message),
            )
            result = {
                "success": True,
                "response": format_reminder_completion_status(status_recipient, reminders, requested_date),
                "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                "reminder_status": reminders,
            }
        elif reminder_recall:
            requested_date = extract_reminder_date(clean_message)
            reminders = sqlite_store.find_reminders_for_recall(
                session_id, reminder_title_hint(clean_message), requested_date
            )
            if reminders:
                reminder = reminders[0]
                date_text = format_reminder_date(requested_date)
                setter = f"，是{reminder['created_by']}帮您设的" if reminder.get("created_by") else ""
                result = {
                    "success": True,
                    "response": f"您{date_text}{reminder['reminder_time']}要{reminder['title']}{setter}。",
                    "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                    "reminder": reminder,
                }
            else:
                result = {
                    "success": True,
                    "response": f"我这里没有找到您{format_reminder_date(requested_date)}的这项提醒。",
                    "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                }
        elif delete_reminder_request:
            title_hint = "吃药" if any(word in clean_message for word in ("吃药", "服药")) else ""
            deleted = sqlite_store.delete_matching_reminders(session_id, title_hint)
            result = {
                "success": True,
                "response": f"好的，已删除{deleted}条提醒。" if deleted else "没有找到需要删除的提醒。",
                "session_id": session_id, "agent_type": agent_type, "command_type": "DELETE_ALARM",
                "tool_used": False, "tool_results": [], "deleted_reminders": deleted,
            }
        elif is_profile_query:
            member = sqlite_store.find_related_member(request.family_id, request.actor_name, profile_subject) if request.actor_name else None
            if member:
                age_text = f"，今年{member['age']}岁" if member.get("age") is not None else ""
                result = {
                    "success": True, "response": f"您{profile_subject}叫{member['member_name']}{age_text}。",
                    "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                    "family_profile": member,
                }
            else:
                result = {
                    "success": True, "response": f"我还不知道您和{profile_subject}对应的是哪位家人。可以先说“某某是我的{profile_subject}”。",
                    "session_id": session_id, "agent_type": agent_type, "tool_used": False, "tool_results": [],
                }
        elif health_subject:
            events = sqlite_store.find_recent_health_events(request.family_id, health_subject, query_window_start(clean_message).isoformat())
            result = {
                "success": True, "response": format_events(health_subject, events), "session_id": session_id,
                "agent_type": agent_type, "tool_used": False, "tool_results": [],
                "health_memory": {"family_id": request.family_id, "person_name": health_subject, "event_count": len(events)},
            }
        elif activity_subject and activity:
            events = sqlite_store.find_recent_activity_events(request.family_id, activity_subject, activity, query_window_start(clean_message).isoformat())
            result = {
                "success": True, "response": format_activity_events(activity_subject, activity, events), "session_id": session_id,
                "agent_type": agent_type, "tool_used": False, "tool_results": [],
                "activity_memory": {"family_id": request.family_id, "person_name": activity_subject, "activity": activity, "event_count": len(events)},
            }
        elif pending_reminder and pending_time:
            reminder_date = pending_reminder.get("reminder_date") or datetime.now().date().isoformat()
            reminder, updated = sqlite_store.upsert_reminder(
                session_id=pending_reminder.get("recipient_session_id") or session_id,
                title=pending_reminder["title"],
                reminder_time=pending_time,
                repeat_rule=pending_reminder["repeat_rule"],
                reminder_date=reminder_date,
                created_by=pending_reminder.get("created_by") or request.actor_name,
            )
            sqlite_store.clear_pending_reminder(session_id)
            repeat_text = "每天" if reminder["repeat_rule"] == "daily" else ""
            date_text = "" if reminder["repeat_rule"] == "daily" else f"{format_reminder_date(reminder_date)}"
            result = {
                "success": True,
                "response": f"好的，已{'更新' if updated else '设置'}{date_text}{repeat_text}{pending_time}的{reminder['title']}。",
                "session_id": session_id,
                "agent_type": agent_type,
                "command_type": "SET_ALARM",
                "tool_used": False,
                "tool_results": [],
                "alarm_control": {"action": "set", "alarm_info": {"name": reminder["title"], "display_time": pending_time, "repeat_desc": reminder["repeat_rule"]}},
                "reminder": reminder,
            }
        else:

            # 执行Agent处理（使用清理后的消息）
            result = await agent.run(
                input_text=clean_message,
                session_id=session_id,
                mode_profile=mode_profile,
                device_config=device_config,
                session_location=location["location_name"] if location else None,
                actor_name=request.actor_name,
                persistent_context=persistent_context,
            )

        # Persist an explicit symptom statement independently of short-term
        # chat history, so an authorised family member can retrieve it later.
        symptom = extract_symptom(clean_message)
        subject = extract_subject(clean_message, request.actor_name)
        if symptom and subject and not health_subject:
            result["health_event"] = sqlite_store.add_health_event(
                family_id=request.family_id, person_name=subject, symptom=symptom, session_id=session_id,
            )
        activity_statement = extract_activity(clean_message)
        if activity_statement and subject and not activity:
            result["activity_event"] = sqlite_store.add_activity_event(
                family_id=request.family_id, person_name=subject, activity=activity_statement, session_id=session_id,
            )

        if result.get("command_type") == "SET_ALARM" and result.get("alarm_control", {}).get("action") == "needs_time":
            alarm = result["alarm_control"]["alarm_info"]
            sqlite_store.set_pending_reminder(
                session_id,
                alarm.get("name", "提醒"),
                alarm.get("repeat_desc", "once"),
                alarm_date_to_iso(alarm),
                recipient_session_id=recipient_session_id if reminder_recipient else None,
                created_by=request.actor_name if reminder_recipient else None,
            )

        if result.get("command_type") == "SET_ALARM" and result.get("alarm_control", {}).get("action") == "set":
            alarm = result.get("alarm_control", {}).get("alarm_info", {})
            extracted_task = extract_reminder_task(clean_message, request.actor_name)
            if extracted_task:
                alarm["name"] = extracted_task
            reminder_date = alarm_date_to_iso(alarm)
            reminder, updated = sqlite_store.upsert_reminder(
                session_id=recipient_session_id,
                title=alarm.get("name", "提醒"),
                reminder_time=str(alarm.get("display_time", "08:00")),
                repeat_rule=alarm.get("repeat_desc", "once"),
                reminder_date=reminder_date,
                created_by=request.actor_name if reminder_recipient else None,
            )
            result.setdefault("reminder", reminder)
            repeat_text = "每天" if reminder["repeat_rule"] == "daily" else ""
            date_text = "" if reminder["repeat_rule"] == "daily" else format_reminder_date(reminder_date)
            recipient_text = f"给{reminder_recipient}" if reminder_recipient else ""
            result["response"] = f"好的，已{'更新' if updated else '设置'}{recipient_text}{date_text}{repeat_text}{reminder['reminder_time']}的{reminder['title']}。"
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        trace = trace_store.record(
            session_id=session_id,
            input_text=clean_message,
            result=result,
            total_latency_ms=processing_time * 1000,
            mode=resolved_mode.mode.value,
        )
        
        # 记录性能日志
        logger.info(f"Agent处理完成，会话: {session_id}, 耗时: {processing_time:.2f}秒")
        logger.info(f"当前会话消息计数: {active_sessions[session_id]['message_count']}")
        if result.get("tool_used"):
            logger.info(f"工具调用情况: {len(result.get('tool_results', []))}个工具被调用")
        
        # 构建响应，包含command_type字段
        response_data = {
            "response": result["response"],
            "session_id": session_id,
            "agent_type": agent_type,
            "success": result["success"],
            "tool_used": result.get("tool_used", False),
            "tool_results": result.get("tool_results", None),
            "metadata": {
                "mode": resolved_mode.mode.value,
                "mode_source": resolved_mode.source,
                "processing_time": processing_time,
                "message_count": active_sessions[session_id]["message_count"],
                "timestamp": end_time.isoformat(),
                "trace_id": trace["trace_id"],
            }
        }
        
        # 添加command_type字段（如果存在）
        if "command_type" in result:
            response_data["command_type"] = result["command_type"]
            logger.info(f"包含系统指令类型: {result['command_type']}")
        
        return AgentResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Agent处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail="Agent处理失败")

if __name__ == "__main__":
    import uvicorn
    
    # 启动服务
    uvicorn.run(
        app, 
        host=settings.SERVER_HOST, 
        port=settings.SERVER_PORT,
        log_level="info",
        access_log=True
    )
