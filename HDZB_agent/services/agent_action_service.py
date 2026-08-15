"""Backend implementations for stateful Function Calling tools."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from services.health_memory_service import format_events
from services.reminder_slot_service import extract_reminder_date, extract_time, format_reminder_date


RELATIONS = {
    "奶奶", "爷爷", "爸爸", "妈妈", "外婆", "外公", "孙子", "孙女", "儿子", "女儿", "老伴",
    "父母", "祖辈", "孩子", "孙辈",
}
INVALID_NAMES = {"谁", "谁吗", "哪位", "哪个人", "什么", "什么名字", "他", "她", "家人", "对方"}
GENERIC_REMINDER_TITLES = {"", "提醒", "设置提醒", "通知", "闹钟", "记得"}
PREFERENCE_CATEGORIES = {
    "food": "饮食", "activity": "活动", "entertainment": "娱乐",
    "habit": "生活习惯", "other": "其他",
}


class AgentActionService:
    """Execute validated tools against the family-scoped SQLite store."""

    def __init__(self, store):
        self.store = store

    def _resolve_member(self, family_id: str, actor_name: str | None, reference: str | None) -> dict | None:
        reference = (reference or "self").strip()
        if reference in {"self", "我", "自己"}:
            return self.store.get_household_member(family_id, actor_name) if actor_name else None
        exact = self.store.get_household_member(family_id, reference)
        if exact:
            return exact
        if actor_name and reference in RELATIONS:
            return self.store.find_member_by_spoken_relation(family_id, actor_name, reference)
        return None

    @staticmethod
    def _valid_iso_date(value: str) -> str:
        try:
            return date.fromisoformat(value).isoformat()
        except (TypeError, ValueError):
            return date.today().isoformat()

    @staticmethod
    def _valid_time(value: str) -> str | None:
        try:
            return datetime.strptime(value, "%H:%M").strftime("%H:%M")
        except (TypeError, ValueError):
            return None

    def execute(self, tool_name: str, arguments: dict, context: dict) -> dict[str, Any]:
        handler = getattr(self, f"_{tool_name}", None)
        if handler is None:
            return {"content": f"工具{tool_name}暂不可用"}
        return handler(arguments, context)

    def _save_family_relationship(self, args: dict, context: dict) -> dict:
        family_id, actor_name = context["family_id"], context.get("actor_name")
        relation = str(args.get("relation") or "").strip()
        target_name = str(args.get("target_name") or "").strip()
        if not actor_name or relation not in RELATIONS:
            return {"content": "家庭关系参数不完整，未写入。", "direct_response": "我还没能确认这条家庭关系。"}
        if not 2 <= len(target_name) <= 16 or target_name in INVALID_NAMES or any(word in target_name for word in INVALID_NAMES):
            return {"content": "姓名无效，未写入。", "direct_response": "我还没能确认家人的姓名，所以没有记录。"}
        # The model may normalise punctuation, but it cannot invent a person
        # who was absent from the user's message.
        if target_name not in context.get("input_text", ""):
            return {"content": "姓名未出现在用户原话，未写入。", "direct_response": "我没有从您的原话里确认到家人姓名，所以没有记录。"}
        age = args.get("target_age")
        try:
            age = int(age) if age is not None else None
        except (TypeError, ValueError):
            age = None
        if age is not None and not 0 <= age <= 130:
            age = None
        self.store.add_household_member(family_id, target_name, age=age)
        self.store.set_family_relationship(family_id, actor_name, target_name, relation)
        age_text = f"，今年{age}岁" if age is not None else ""
        response = f"记住了，您的{relation}是{target_name}{age_text}。"
        return {"content": response, "direct_response": response}

    def _query_family_relationship(self, args: dict, context: dict) -> dict:
        relation = str(args.get("relation") or "").strip()
        if relation not in RELATIONS or not context.get("actor_name"):
            response = "我还没弄清您想问的是哪种家庭关系。"
            return {"content": response, "direct_response": response}
        member = self.store.find_member_by_spoken_relation(context["family_id"], context["actor_name"], relation)
        if not member:
            response = f"我还不知道您的{relation}是哪位家人。"
        else:
            age_text = f"，今年{member['age']}岁" if member.get("age") is not None else ""
            response = f"认识，您的{relation}是{member['member_name']}{age_text}。"
        return {"content": response, "direct_response": response}

    def _record_health_event(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        symptoms = [str(item).strip() for item in (args.get("symptoms") or []) if str(item).strip()][:4]
        if not member or not symptoms:
            response = "我还没能确认是哪位家人不舒服，所以没有写入健康记录。"
            return {"content": response, "direct_response": response}
        events = [
            self.store.add_health_event(context["family_id"], member["member_name"], symptom, context["session_id"])
            for symptom in symptoms
        ]
        response = f"我记下了，{member['member_name']}提到过{'、'.join(symptoms)}。"
        return {"content": response, "direct_response": response, "health_events": events}

    def _query_health_events(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        if not member:
            response = "我还没弄清您问的是哪位家人。"
            return {"content": response, "direct_response": response}
        try:
            days = max(1, min(30, int(args.get("days", 7))))
        except (TypeError, ValueError):
            days = 7
        events = self.store.find_recent_health_events(
            context["family_id"], member["member_name"], (datetime.now() - timedelta(days=days)).isoformat()
        )
        response = format_events(member["member_name"], events)
        return {"content": response, "direct_response": response, "health_events": events}

    def _resolve_health_event(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        symptoms = [str(item).strip() for item in (args.get("symptoms") or []) if str(item).strip()][:4]
        if not member or not symptoms:
            response = "我还没能确认是哪位家人的什么症状已经好了。"
            return {"content": response, "direct_response": response}
        resolved = self.store.resolve_health_events(
            context["family_id"], member["member_name"], symptoms
        )
        if resolved:
            response = f"记下了，{member['member_name']}说{'、'.join(symptoms)}已经好了。"
        else:
            response = f"我没有找到{member['member_name']}近期关于{'、'.join(symptoms)}的未恢复记录。"
        return {"content": response, "direct_response": response, "resolved_health_events": resolved}

    def _save_preference(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        category = str(args.get("category") or "other").strip()
        polarity = str(args.get("polarity") or "").strip()
        item = str(args.get("item") or "").strip(" ，。！？、")[:32]
        if not member or category not in PREFERENCE_CATEGORIES or polarity not in {"like", "dislike"} or not item:
            response = "我还没能确认这条偏好，所以没有记录。"
            return {"content": response, "direct_response": response}
        if item not in context.get("input_text", ""):
            response = "我没有从您的原话里确认到具体偏好，所以没有记录。"
            return {"content": response, "direct_response": response}
        fact = self.store.upsert_family_preference(
            context["family_id"], member["member_name"], category, item, polarity, context["session_id"]
        )
        preference_text = "喜欢" if polarity == "like" else "不喜欢"
        response = f"记住了，{member['member_name']}在{PREFERENCE_CATEGORIES[category]}方面{preference_text}{item}。"
        return {"content": response, "direct_response": response, "preference": fact}

    def _query_preferences(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        category = str(args.get("category") or "").strip()
        if not member:
            response = "我还没弄清您想查询哪位家人的偏好。"
            return {"content": response, "direct_response": response}
        facts = self.store.list_family_facts(context["family_id"], member["member_name"])
        preferences = []
        for fact in facts:
            key, value = fact["fact_key"], fact["fact_value"]
            if key.startswith("偏好:") and ":" in value:
                stored_category = key.split(":", 1)[1]
                if category and stored_category != category:
                    continue
                polarity, item = value.split(":", 1)
                preferences.append(
                    f"{PREFERENCE_CATEGORIES.get(stored_category, stored_category)}方面"
                    f"{'喜欢' if polarity == 'like' else '不喜欢'}{item}"
                )
            elif key in {"喜欢", "不喜欢"} and not category:
                preferences.append(f"{key}{value}")
        if preferences:
            response = f"我记得{member['member_name']}的长期偏好：{'；'.join(preferences)}。"
        else:
            response = f"我还没有记录{member['member_name']}的长期偏好。"
        return {"content": response, "direct_response": response, "preferences": preferences}

    def _update_member_profile(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        if not member:
            response = "我还没弄清要更新哪位家人的资料。"
            return {"content": response, "direct_response": response}
        updates = []
        if args.get("age") is not None:
            try:
                age = int(args["age"])
            except (TypeError, ValueError):
                age = -1
            if 0 <= age <= 130:
                self.store.add_household_member(context["family_id"], member["member_name"], age=age)
                updates.append(f"年龄更新为{age}岁")
        for change in (args.get("health_changes") or [])[:6]:
            condition = str(change.get("condition") or "").strip()
            status = str(change.get("status") or "").strip()
            if not condition or status not in {"active", "resolved"}:
                continue
            if status == "active":
                self.store.upsert_family_fact(
                    context["family_id"], member["member_name"], "长期健康情况", condition, context["session_id"]
                )
                updates.append(f"新增长期健康情况“{condition}”")
            else:
                self.store.remove_family_fact(
                    context["family_id"], member["member_name"], "长期健康情况", condition
                )
                updates.append(f"将“{condition}”标记为已解除")
        if not updates:
            response = "我没有从这句话里确认到需要更新的年龄或长期健康情况。"
        else:
            response = f"已经更新{member['member_name']}的资料：{'；'.join(updates)}。"
        return {"content": response, "direct_response": response, "profile_updates": updates}

    def _query_member_profile(self, args: dict, context: dict) -> dict:
        member = self._resolve_member(context["family_id"], context.get("actor_name"), args.get("subject_ref"))
        if not member:
            response = "我还没弄清您想查询哪位家人的资料。"
            return {"content": response, "direct_response": response}
        facts = self.store.list_family_facts(context["family_id"], member["member_name"])
        details = []
        if member.get("age") is not None:
            details.append(f"{member['age']}岁")
        conditions = [item["fact_value"] for item in facts if item["fact_key"] == "长期健康情况"]
        if conditions:
            details.append(f"长期健康情况包括{'、'.join(conditions)}")
        preferences = []
        for fact in facts:
            if fact["fact_key"].startswith("偏好:") and ":" in fact["fact_value"]:
                category = fact["fact_key"].split(":", 1)[1]
                polarity, item = fact["fact_value"].split(":", 1)
                preferences.append(
                    f"{PREFERENCE_CATEGORIES.get(category, category)}方面"
                    f"{'喜欢' if polarity == 'like' else '不喜欢'}{item}"
                )
        if preferences:
            details.append("；".join(preferences))
        if details:
            response = f"我记得{member['member_name']}的资料：{'；'.join(details)}。"
        else:
            response = f"我目前只知道这位家人叫{member['member_name']}，还没有更多长期资料。"
        return {"content": response, "direct_response": response, "member_profile": member, "family_facts": facts}

    def _set_reminder(self, args: dict, context: dict) -> dict:
        family_id, actor_name = context["family_id"], context.get("actor_name")
        member = self._resolve_member(family_id, actor_name, args.get("recipient_ref"))
        if not member:
            response = "我还没弄清提醒要交给哪位家人。"
            return {"content": response, "direct_response": response}
        original_text = context.get("input_text", "")
        reminder_time = extract_time(original_text) or self._valid_time(str(args.get("time") or ""))
        if not reminder_time:
            response = "提醒时间还不完整，请告诉我具体几点。"
            return {"content": response, "direct_response": response, "needs_time": True}
        llm_date = self._valid_iso_date(str(args.get("date") or ""))
        reminder_date = extract_reminder_date(original_text) if any(word in original_text for word in ("今天", "明天", "明早", "明晚")) else llm_date
        repeat_rule = str(args.get("repeat") or "once").strip()
        if repeat_rule not in {"once", "daily", "weekdays", "weekend"} and not repeat_rule.startswith("weekly_"):
            repeat_rule = "once"
        action = str(args.get("canonical_action") or "").strip()
        obj = str(args.get("canonical_object") or "").strip()
        task = str(args.get("task") or "").strip()
        canonical_title = f"{action}{obj}".strip()
        # “提醒/通知”只表示工具意图，不是用户要做的任务。若把它
        # 当作标题，回复模板再追加“提醒”就会出现“提醒提醒”。
        if canonical_title in GENERIC_REMINDER_TITLES:
            title = task if task not in GENERIC_REMINDER_TITLES else "提醒"
        else:
            title = canonical_title
        target_session = self.store.member_session_id(family_id, member["member_name"])
        reminder, updated = self.store.upsert_reminder(
            target_session, title, reminder_time, repeat_rule, reminder_date,
            created_by=actor_name if member["member_name"] != actor_name else None,
        )
        date_text = "" if repeat_rule == "daily" else format_reminder_date(reminder_date)
        schedule = f"每天{reminder_time}" if repeat_rule == "daily" else f"{date_text}{reminder_time}"
        operation = "更新" if updated else "设置"
        if title in GENERIC_REMINDER_TITLES:
            response = f"好的，已为{member['member_name']}{operation}{schedule}的提醒。"
        else:
            response = f"好的，已为{member['member_name']}{operation}{schedule}的提醒：{title}。"
        return {
            "content": response,
            "direct_response": response,
            "command_type": "SET_ALARM",
            "reminder": reminder,
            "reminder_persisted": True,
            "alarm_control": {
                "action": "set",
                "recipient_name": member["member_name"],
                "recipient_session_id": target_session,
                "alarm_info": {
                    "name": title, "display_time": reminder_time,
                    "date_value": reminder_date.replace("-", ""), "repeat_desc": repeat_rule,
                },
            },
        }
