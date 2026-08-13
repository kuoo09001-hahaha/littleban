"""Mode domain model for child and elder companion experiences."""

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ModeType(str, Enum):
    CHILD = "child"
    ELDER = "elder"


@dataclass(frozen=True)
class FeedbackProfile:
    light: str
    vibration: str


@dataclass(frozen=True)
class ModeProfile:
    mode: ModeType
    display_name: str
    response_style: str
    allowed_tools: FrozenSet[str]
    safety_rules: Tuple[str, ...]
    default_voice: str
    default_feedback: FeedbackProfile


MODE_PROFILES = {
    ModeType.CHILD: ModeProfile(
        mode=ModeType.CHILD,
        display_name="儿童模式",
        response_style="安全、活泼、简短，适合儿童理解",
        allowed_tools=frozenset({
            "get_weather",
            "get_location",
            "add_personal_info",
            "recall_personal_info",
            "list_family_members",
            "intent_analyzer",
            "knowledge_search",
        }),
        safety_rules=(
            "不主动索要住址、学校、电话等隐私信息",
            "涉及个人信息、定位、联系人或设备控制时，用儿童能理解的方式提醒需要家长知情",
            "拒绝成人内容、危险行为和不适龄话题",
            "鼓励孩子寻求家长帮助",
        ),
        default_voice="child_friendly",
        default_feedback=FeedbackProfile(light="warm_colorful", vibration="soft"),
    ),
    ModeType.ELDER: ModeProfile(
        mode=ModeType.ELDER,
        display_name="长辈模式",
        response_style="温和、清楚、慢节奏，避免技术术语",
        allowed_tools=frozenset({
            "get_weather",
            "get_location",
            "add_personal_info",
            "recall_personal_info",
            "list_family_members",
            "intent_analyzer",
            "knowledge_search",
        }),
        safety_rules=(
            "健康相关回复只做生活提醒，不替代医生建议",
            "遇到求助、摔倒、强烈不适等内容建议联系家属或紧急服务",
            "回复保持简短明确",
        ),
        default_voice="warm_elder",
        default_feedback=FeedbackProfile(light="warm_soft", vibration="gentle"),
    ),
}


def parse_mode(value: str | ModeType) -> ModeType:
    """Parse a user-provided mode value."""
    if isinstance(value, ModeType):
        return value

    try:
        return ModeType(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in ModeType)
        raise ValueError(f"Unsupported mode '{value}'. Expected one of: {allowed}") from exc


def get_mode_profile(mode: str | ModeType) -> ModeProfile:
    """Return the profile for a mode."""
    return MODE_PROFILES[parse_mode(mode)]
