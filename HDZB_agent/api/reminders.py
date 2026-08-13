"""Local reminder APIs backed by SQLite."""

from datetime import date, datetime
from typing import Callable
from fastapi import APIRouter, HTTPException


def create_reminders_router(get_store: Callable[[], object]) -> APIRouter:
    router = APIRouter(tags=["reminders"])

    @router.get("/agent/reminders/{session_id}")
    async def list_reminders(session_id: str):
        today = date.today().isoformat()
        reminders = [
            item for item in get_store().list_reminders(session_id)
            if item["repeat_rule"] == "daily" or not item.get("reminder_date") or item["reminder_date"] >= today
        ]
        for item in reminders:
            item["completed_today"] = item["repeat_rule"] == "daily" and item.get("last_completed_date") == today
        return {"reminders": reminders}

    @router.get("/agent/reminders/{session_id}/due")
    async def due_reminders(session_id: str):
        now = datetime.now()
        current_time, today = now.strftime("%H:%M"), date.today().isoformat()
        reminders = get_store().list_reminders(session_id)
        due = [
            item for item in reminders
            if item["reminder_time"] <= current_time
            and (item["repeat_rule"] == "daily" or item["reminder_date"] in (None, today))
            and item.get("last_triggered_date") != today
        ]
        for item in due:
            get_store().mark_reminder_triggered(item["reminder_id"], today)
        return {"reminders": due, "checked_at": now.isoformat()}

    @router.post("/agent/reminders/{reminder_id}/complete")
    async def complete_reminder(reminder_id: str):
        if not get_store().complete_reminder(reminder_id):
            raise HTTPException(status_code=404, detail="Reminder not found or already completed")
        return {"success": True, "reminder_id": reminder_id}

    @router.delete("/agent/reminders/{reminder_id}")
    async def delete_reminder(reminder_id: str):
        if not get_store().delete_reminder(reminder_id):
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"success": True, "reminder_id": reminder_id}

    return router
