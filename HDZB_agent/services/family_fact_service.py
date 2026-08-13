"""Strict extraction of small, durable family facts from explicit statements."""

import re


RELATIONS = ("奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿", "老伴")
LONG_TERM_CONDITIONS = ("高血压", "糖尿病", "哮喘", "冠心病", "关节炎", "花粉过敏", "药物过敏")


def normalize_person_name(value: str) -> str:
    """Remove common age phrases accidentally attached to a person's name."""
    name = value.strip("，。！？、 ：: ")
    name = re.sub(r"(?:今年|现年)(?:\d{1,3}|[零一二两三四五六七八九十]+)?(?:岁)?$", "", name)
    name = re.sub(r"(?:\d{1,3}|[零一二两三四五六七八九十]+)岁$", "", name)
    return name.strip("，。！？、 ：: ")


def extract_named_relationship(text: str) -> tuple[str, str] | None:
    """Extract phrases such as '我爷爷叫王刚' for the current speaker."""
    relation_pattern = "|".join(RELATIONS)
    match = re.search(rf"我(?:的)?({relation_pattern})(?:叫|是)([\u4e00-\u9fff]{{2,8}})(?:(?:今年|现年)?(?:\d{{1,3}}|[零一二两三四五六七八九十]+)岁)?", text)
    return (match.group(1), normalize_person_name(match.group(2))) if match else None


def extract_named_age(text: str) -> tuple[str, int] | None:
    """Extract '王秀芬今年68岁' without storing the age as part of the name."""
    relation_pattern = "|".join(RELATIONS)
    match = re.search(
        rf"我(?:的)?(?:{relation_pattern})(?:叫|是)([\u4e00-\u9fff]{{2,8}}?)(?:今年|现年)?(\d{{1,3}})岁",
        text,
    )
    if not match:
        match = re.search(r"([\u4e00-\u9fff]{2,8}?)(?:今年|现年)(\d{1,3})岁", text)
    if not match:
        return None
    return normalize_person_name(match.group(1)), int(match.group(2))


def extract_explicit_facts(text: str, actor_name: str | None) -> list[tuple[str, str]]:
    """Return only deliberate long-term facts stated about the current speaker."""
    if not actor_name:
        return []
    facts: list[tuple[str, str]] = []
    for key, pattern in (
        ("喜欢", r"我(?:很)?喜欢([^，。！？!?]{1,24})"),
        ("不喜欢", r"我(?:很)?不喜欢([^，。！？!?]{1,24})"),
        ("过敏", r"我(?:对)?([^，。！？!?]{1,24})过敏"),
    ):
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value:
                facts.append((key, value))
    for condition in LONG_TERM_CONDITIONS:
        if re.search(rf"我(?:患有|有){condition}", text):
            facts.append(("长期健康情况", condition))
    return facts


def format_persistent_context(profile: dict | None, relationships: list[dict], facts: list[dict]) -> str:
    """Compact, model-facing summary; it deliberately excludes raw chat history."""
    items: list[str] = []
    if profile and profile.get("age") is not None:
        items.append(f"年龄：{profile['age']}岁")
    items.extend(f"{item['relation']}：{item['target_name']}" for item in relationships)
    items.extend(f"{item['fact_key']}：{item['fact_value']}" for item in facts)
    return "；".join(items) if items else "暂无已确认的长期重点信息"
