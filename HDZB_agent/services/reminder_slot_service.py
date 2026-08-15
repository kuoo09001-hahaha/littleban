"""Deterministic slot filling for a reminder waiting for a time."""

import re
from datetime import date, timedelta


CHINESE_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _parse_hour(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = CHINESE_DIGITS.get(left, 1) if left else 1
        ones = CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return CHINESE_DIGITS.get(value)


def extract_time(text: str) -> str | None:
    """Extract a HH:MM time from a natural Chinese follow-up utterance."""
    patterns = [
        (r"(明早|明天早上|早上|上午|中午|下午|晚上)?\s*(\d{1,2}|[零一二两三四五六七八九十]{1,3})点(?:\s*(\d{1,2})分?)?", "chinese"),
        # ``\b`` does not separate Chinese characters from digits because
        # both are Unicode word characters. Digit lookarounds correctly match
        # compact phrases such as “晚上20:10吃药”.
        (r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", "colon"),
    ]
    for pattern, kind in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == "colon":
            hour, minute = int(match.group(1)), int(match.group(2))
        else:
            period, hour_text, minute_text = match.groups()
            hour, minute = _parse_hour(hour_text), int(minute_text or 0)
            if hour is None:
                continue
            if period in ("下午", "晚上") and hour < 12:
                hour += 12
            elif period == "中午" and hour < 11:
                hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def extract_reminder_date(text: str) -> str:
    """Return the target date for simple relative reminder language."""
    if any(word in text for word in ("明天", "明早", "明晚")):
        return (date.today() + timedelta(days=1)).isoformat()
    return date.today().isoformat()


def format_reminder_date(value: str) -> str:
    """Render an ISO reminder date explicitly instead of saying “tomorrow”."""
    try:
        target = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return f"{target.year}年{target.month}月{target.day}日"


def alarm_date_to_iso(alarm: dict) -> str:
    """Convert an alarm payload's YYYYMMDD date into the SQLite ISO format."""
    value = str(alarm.get("date_value", ""))
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return date.today().isoformat()


def find_reminder_recipient(text: str, actor_name: str | None, member_names: list[str]) -> str | None:
    """Find a named family member who is the recipient of a reminder request.

    The UI already has a family roster, so only exact names from that roster
    are eligible.  This keeps a phrase such as “提醒我奶奶王秀芬……” from
    accidentally creating a second profile called “奶奶”.
    """
    if not any(word in text for word in ("提醒", "闹钟", "记得", "告诉", "转告")):
        return None
    candidates = [name for name in member_names if name != actor_name and name and name in text]
    return max(candidates, key=len) if candidates else None


def is_reminder_recall_query(text: str) -> bool:
    """Recognise a request to recall a previously saved reminder."""
    return bool(
        re.search(r"(?:几点|什么时候|何时|哪天).{0,12}(?:吃饭|吃药|服药|上课|复诊|打电话|提醒)", text)
        or ("来着" in text and any(word in text for word in ("吃饭", "吃药", "服药", "上课", "复诊", "提醒")))
    )


def is_reminder_completion_query(text: str) -> bool:
    """Recognise whether a reminder recipient has completed a task."""
    return bool(
        re.search(r"(?:做完|完成|办完|处理完).{0,4}(?:没|了吗|没有|了)?", text)
        or re.search(r"(?:没|没有|还没).{0,4}(?:做完|完成|办完|处理完)", text)
        or re.search(r"(?:吃药|服药|吃饭|上课|复诊|打电话).{0,5}(?:没|了吗|没有|完成)", text)
    )


def format_reminder_completion_status(recipient_name: str, reminders: list[dict], target_date: str) -> str:
    """Render a clear status for reminders the current user created."""
    if not reminders:
        return f"我没有找到您交给{recipient_name}、在{format_reminder_date(target_date)}要完成的提醒。"
    phrases = []
    for reminder in reminders:
        if reminder["repeat_rule"] == "daily":
            done = reminder.get("last_completed_date") == target_date
        else:
            done = bool(reminder.get("completed_at"))
        state = "已经完成了" if done else "还没有完成"
        phrases.append(f"{recipient_name}的“{reminder['title']}”{state}")
    return "；".join(phrases) + "。"


def reminder_title_hint(text: str) -> str | None:
    """Return a stable task hint for reminder creation and recall."""
    for title in ("吃降压药", "吃药", "服药", "吃饭", "上课", "复诊", "测血压", "打电话"):
        if title in text:
            return "吃药" if title == "服药" else title
    return None


def extract_reminder_task(text: str, actor_name: str | None = None) -> str | None:
    """Build a recipient-facing task after a reminder's date/time.

    A reminder sent to another family member should not show an orphaned
    first-person sentence.  For example, 王刚 sees “秀英要去找我们孙子”, not
    “我要去找我们孙子”.
    """
    time_match = re.search(
        r"(?:明天|明早|明晚|今天)?(?:早上|上午|中午|下午|晚上)?\s*(?:\d{1,2}|[零一二两三四五六七八九十]{1,3})点(?:\s*\d{1,2}分?)?",
        text,
    )
    if not time_match:
        return reminder_title_hint(text)
    task = text[time_match.end():].strip("，。！？、 ：:")
    if not task:
        return reminder_title_hint(text)
    task = re.sub(r"[了吧呀啊]+$", "", task)
    if actor_name:
        before_time = text[:time_match.start()]
        first_person_before_time = bool(
            re.search(r"我(?:明天|明早|明晚|今天)?(?:早上|上午|中午|下午|晚上)?\s*$", before_time)
        )
        task = task.replace("等我", f"等{actor_name}")
        task = re.sub(r"^我(?=要|会|得|想|去|来)", actor_name, task)
        if first_person_before_time and not task.startswith(actor_name):
            task = f"{actor_name}要{task}"
    return task[:64]
