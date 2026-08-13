"""Time-aware, family-scoped health memory extraction and retrieval."""

import re
from datetime import datetime, timedelta


SYMPTOM_ALIASES = {
    "头疼": ("头疼", "头痛", r"脑袋(?:有点|有些|有一点)?疼", r"脑壳(?:有点|有些|有一点)?疼", "头有点疼", "头发胀"),
    "肚子疼": ("肚子疼", "腹痛"),
    "胃疼": ("胃疼", "胃不舒服"),
    "胸口疼": ("胸口疼", "胸痛", "胸闷"),
    "腿疼": ("腿疼", "腿不舒服"),
    "腰疼": ("腰疼", "腰不舒服"),
    "咳嗽": ("咳嗽", "咳个不停", "咳得难受"),
    "发烧": ("发烧", "发热", "烧起来了"),
    "头晕": ("头晕", "晕乎乎", "头昏"),
    "不舒服": ("不舒服", "难受"),
}
RELATIONS = ("奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公")
ACTIVITY_ALIASES = {
    "买菜": ("买菜", "买东西", "采购", "去超市"),
    "散步": ("散步", "遛弯", "出去走走"),
    "看病": ("看病", "去医院", "复诊"),
    "回家": ("回家", "到家"),
    "游泳": ("游泳", "游个泳", "去泳池"),
    "上学": ("上学", "去学校", "到学校"),
}
NEGATION_PATTERN = re.compile(r"(?:没|没有|不|未|别)(?:\s*有)?(?:去|出门|在)?")


def inverse_relation(source_name: str, relation: str) -> str | None:
    """Infer the target's view of a relationship when the role is explicit."""
    if relation in ("儿子", "女儿"):
        if "爸爸" in source_name:
            return "爸爸"
        if "妈妈" in source_name:
            return "妈妈"
    if relation in ("孙子", "孙女"):
        if "奶奶" in source_name:
            return "奶奶"
        if "爷爷" in source_name:
            return "爷爷"
        if "外婆" in source_name:
            return "外婆"
        if "外公" in source_name:
            return "外公"
    if relation == "老伴":
        return "老伴"
    if relation == "爸爸":
        return "儿子"
    if relation == "妈妈":
        return "儿子"
    return None


def extract_symptom(text: str) -> str | None:
    for normalized, aliases in SYMPTOM_ALIASES.items():
        if any(re.search(alias, text) for alias in aliases):
            return normalized
    return None


def extract_subject(text: str, actor_name: str | None) -> str | None:
    for name in RELATIONS:
        if name in text:
            return name
    return actor_name if "我" in text else None


def extract_activity(text: str) -> str | None:
    """Extract explicit, short-lived family activity statements."""
    if not any(marker in text for marker in ("去", "出门", "在", "刚", "已经")):
        return None
    if is_negated_activity_statement(text):
        return None
    for normalized, aliases in ACTIVITY_ALIASES.items():
        if any(alias in text for alias in aliases):
            return normalized
    return None


def is_negated_activity_statement(text: str) -> bool:
    """True for statements such as '今天没去买菜' before event persistence."""
    for aliases in ACTIVITY_ALIASES.values():
        for alias in aliases:
            position = text.find(alias)
            if position >= 0 and NEGATION_PATTERN.search(text[max(0, position - 6):position]):
                return True
    return False


def is_health_query(text: str) -> bool:
    return any(phrase in text for phrase in ("有没有说", "哪里不舒服", "最近不舒服", "最近怎么样", "身体怎么样"))


def query_subject(text: str) -> str | None:
    return next((name for name in RELATIONS if name in text), None)


def query_activity(text: str) -> str | None:
    if not any(marker in text for marker in ("去", "在", "了吗", "有没有")):
        return None
    for normalized, aliases in ACTIVITY_ALIASES.items():
        if any(alias in text for alias in aliases):
            return normalized
    return None


def query_window_start(text: str) -> datetime:
    days = 7
    match = re.search(r"最近\s*(\d+)\s*天", text)
    if match:
        days = int(match.group(1))
    elif "两天" in text or "2天" in text:
        days = 2
    elif "今天" in text:
        days = 1
    return datetime.now() - timedelta(days=days)


def format_events(person_name: str, events: list[dict]) -> str:
    if not events:
        return f"最近没有记录到{person_name}说身体不舒服。"
    newest = events[0]
    happened = datetime.fromisoformat(newest["occurred_at"])
    days_ago = (datetime.now().date() - happened.date()).days
    when = "今天" if days_ago == 0 else ("昨天" if days_ago == 1 else f"{days_ago}天前")
    return f"{person_name}{when}提到过{newest['symptom']}。这是健康情况记录，若症状持续或加重，建议尽快联系家人或医生。"


def format_activity_events(person_name: str, activity: str, events: list[dict]) -> str:
    if not events:
        return f"最近没有记录到{person_name}去{activity}。"
    happened = datetime.fromisoformat(events[0]["occurred_at"])
    days_ago = (datetime.now().date() - happened.date()).days
    when = "今天" if days_ago == 0 else ("昨天" if days_ago == 1 else f"{days_ago}天前")
    return f"有记录：{person_name}{when}说过自己去{activity}了。"

