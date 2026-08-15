"""Strict extraction of small, durable family facts from explicit statements."""

import re


RELATIONS = ("奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿", "老伴")
PREFERENCE_CATEGORY_LABELS = {
    "food": "饮食", "activity": "活动", "entertainment": "娱乐",
    "habit": "生活习惯", "other": "其他",
}


def normalize_person_name(value: str) -> str:
    """Remove common age phrases accidentally attached to a person's name."""
    name = value.strip("，。！？、 ：: ")
    name = re.sub(r"(?:今年|现年)(?:\d{1,3}|[零一二两三四五六七八九十]+)?(?:岁)?$", "", name)
    name = re.sub(r"(?:\d{1,3}|[零一二两三四五六七八九十]+)岁$", "", name)
    return name.strip("，。！？、 ：: ")


def extract_named_relationship(text: str) -> tuple[str, str] | None:
    """Extract phrases such as '我爷爷叫王刚' for the current speaker."""
    # Relationship memory must only be written from an explicit declaration.
    # “我奶奶是谁吗/我奶奶是王秀芬吗” are questions, not facts.  The old
    # regex consumed “谁吗” as a Chinese name and polluted the family graph.
    if re.search(r"[？?]", text) or re.search(r"(?:谁|哪位|什么名字)", text) or re.search(r"(?:吗|嘛|呢)\s*$", text):
        return None
    relation_pattern = "|".join(RELATIONS)
    match = re.search(rf"我(?:的)?({relation_pattern})(?:叫|是)([\u4e00-\u9fff]{{2,8}})(?:(?:今年|现年)?(?:\d{{1,3}}|[零一二两三四五六七八九十]+)岁)?", text)
    if not match:
        return None
    target_name = normalize_person_name(match.group(2))
    if target_name in {"谁", "谁吗", "哪位", "什么", "什么名字"}:
        return None
    return match.group(1), target_name


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


def format_persistent_context(
    profile: dict | None,
    relationships: list[dict],
    facts: list[dict],
    family_graph: list[dict] | None = None,
) -> str:
    """Compact, model-facing summary; it deliberately excludes raw chat history."""
    items: list[str] = []
    if profile and profile.get("age") is not None:
        items.append(f"年龄：{profile['age']}岁")
    items.extend(f"{item['relation']}：{item['target_name']}" for item in relationships)
    graph_items: list[str] = []
    for edge in (family_graph or [])[:40]:
        source = edge.get("source_name")
        target = edge.get("target_name")
        relation = edge.get("relation")
        if not source or not target or not relation:
            continue
        provenance = "明确" if edge.get("edge_type") == "direct" else "安全推导"
        graph_items.append(f"{source}的{relation}是{target}（{provenance}）")
    if graph_items:
        items.append("家庭关系图：" + "、".join(graph_items))
    for item in facts:
        key, value = item["fact_key"], item["fact_value"]
        if key.startswith("偏好:") and ":" in value:
            category = key.split(":", 1)[1]
            polarity, preference = value.split(":", 1)
            category_text = PREFERENCE_CATEGORY_LABELS.get(category, category)
            items.append(f"{category_text}偏好：{'喜欢' if polarity == 'like' else '不喜欢'}{preference}")
        else:
            items.append(f"{key}：{value}")
    return "；".join(items) if items else "暂无已确认的长期重点信息"
