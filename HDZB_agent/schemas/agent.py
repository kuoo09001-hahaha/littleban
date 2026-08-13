"""Request and response models for Agent API endpoints."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Agent请求数据模型"""

    message: str = Field(..., description="用户输入消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空时创建新会话")
    agent_type: str = Field("companion", description="Agent类型，目前支持companion")
    mode: Optional[str] = Field(None, description="陪伴模式，可选 child 或 elder")
    family_id: str = Field("default", description="家庭空间ID；只有同一家庭空间的成员可查询共享健康记忆")
    actor_name: Optional[str] = Field(None, description="当前说话人，例如奶奶或爸爸")


class AgentResponse(BaseModel):
    """Agent响应数据模型"""

    response: str = Field(..., description="AI回复内容")
    session_id: str = Field(..., description="会话ID")
    agent_type: str = Field(..., description="使用的Agent类型")
    success: bool = Field(..., description="请求是否成功")
    tool_used: Optional[bool] = Field(False, description="是否使用了工具")
    tool_results: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用结果")
    command_type: Optional[str] = Field(None, description="系统指令类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据信息")
    reminder: Optional[Dict[str, Any]] = Field(None, description="由提醒指令创建的本地提醒")


class WeatherQueryRequest(BaseModel):
    """天气查询请求数据模型"""

    location: str = Field(..., description="查询位置")
    test_mode: Optional[bool] = Field(False, description="是否测试模式")


class LocationUpdateRequest(BaseModel):
    """Browser-provided coordinates for one local session."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class MemoryAddRequest(BaseModel):
    """添加记忆请求数据模型"""

    text: str = Field(..., description="记忆内容")
    category: str = Field("general", description="记忆分类")


class PersonalInfoRequest(BaseModel):
    """个人信息请求数据模型"""

    person_name: str = Field(..., description="家庭成员姓名")
    age: Optional[str] = Field(None, description="年龄")
    gender: Optional[str] = Field(None, description="性别")
    health_condition: Optional[str] = Field(None, description="健康状况")


class DeviceModeRequest(BaseModel):
    """设备模式设置请求"""

    mode: str = Field(..., description="设备默认陪伴模式：child 或 elder")


class DeviceModeResponse(BaseModel):
    """设备模式响应"""

    device_id: str = Field(..., description="设备ID")
    mode: str = Field(..., description="当前设备模式")
    source: str = Field(..., description="模式来源")


class DeviceConfigRequest(BaseModel):
    """设备配置设置请求"""

    volume: int = Field(60, ge=0, le=100, description="音量，0-100")
    light_profile: str = Field("warm_soft", description="灯光方案")
    wake_method: str = Field("tap_head", description="唤醒方式")
    usage_start: str = Field("07:00", description="允许使用开始时间，HH:MM")
    usage_end: str = Field("22:00", description="允许使用结束时间，HH:MM")
    content_policy: str = Field("遵循当前模式的默认安全策略", description="设备级内容策略")


class DeviceConfigResponse(DeviceConfigRequest):
    """设备配置响应"""

    device_id: str = Field(..., description="设备ID")
