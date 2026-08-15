"""SQLite storage adapter for local Agent prototype state."""

import sqlite3
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote


RELATION_GENDER = {
    "爸爸": "male", "爷爷": "male", "外公": "male", "儿子": "male", "孙子": "male",
    "妈妈": "female", "奶奶": "female", "外婆": "female", "女儿": "female", "孙女": "female",
}
NEUTRAL_RELATIONS = {
    "爸爸": "父母", "妈妈": "父母",
    "爷爷": "祖辈", "奶奶": "祖辈", "外公": "祖辈", "外婆": "祖辈",
    "儿子": "孩子", "女儿": "孩子",
    "孙子": "孙辈", "孙女": "孙辈",
}


class SQLiteStore:
    """Small SQLite store for local device configuration."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self.rebuild_all_family_graphs()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_modes (
                    device_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS family_members (
                    person_name TEXT PRIMARY KEY,
                    age TEXT NOT NULL DEFAULT '',
                    gender TEXT NOT NULL DEFAULT '',
                    health_condition TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_configs (
                    device_id TEXT PRIMARY KEY,
                    volume INTEGER NOT NULL,
                    light_profile TEXT NOT NULL,
                    wake_method TEXT NOT NULL,
                    usage_start TEXT NOT NULL,
                    usage_end TEXT NOT NULL,
                    content_policy TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    repeat_rule TEXT NOT NULL DEFAULT 'once',
                    reminder_date TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_triggered_date TEXT,
                    last_completed_date TEXT
                )
                """
            )
            # Lightweight migration for databases created before reminders
            # gained recurring-delivery tracking.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(reminders)")}
            if "last_triggered_date" not in columns:
                conn.execute("ALTER TABLE reminders ADD COLUMN last_triggered_date TEXT")
            if "last_completed_date" not in columns:
                conn.execute("ALTER TABLE reminders ADD COLUMN last_completed_date TEXT")
            if "created_by" not in columns:
                conn.execute("ALTER TABLE reminders ADD COLUMN created_by TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_locations (
                    session_id TEXT PRIMARY KEY,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    location_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_reminders (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    repeat_rule TEXT NOT NULL,
                    reminder_date TEXT,
                    recipient_session_id TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            pending_columns = {row[1] for row in conn.execute("PRAGMA table_info(pending_reminders)")}
            if "reminder_date" not in pending_columns:
                conn.execute("ALTER TABLE pending_reminders ADD COLUMN reminder_date TEXT")
            if "recipient_session_id" not in pending_columns:
                conn.execute("ALTER TABLE pending_reminders ADD COLUMN recipient_session_id TEXT")
            if "created_by" not in pending_columns:
                conn.execute("ALTER TABLE pending_reminders ADD COLUMN created_by TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS health_events (
                    event_id TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    person_name TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                    ,expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_events (
                    event_id TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    person_name TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                    ,expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS household_members (
                    family_id TEXT NOT NULL,
                    member_name TEXT NOT NULL,
                    relationship TEXT NOT NULL DEFAULT '',
                    age INTEGER,
                    gender TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (family_id, member_name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS family_relationships (
                    family_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    edge_type TEXT NOT NULL DEFAULT 'direct',
                    evidence TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (family_id, source_name, target_name, relation)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS family_facts (
                    fact_id TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (family_id, subject_name, fact_key, fact_value)
                )
                """
            )
            household_columns = {row[1] for row in conn.execute("PRAGMA table_info(household_members)")}
            if "relationship" not in household_columns:
                conn.execute("ALTER TABLE household_members ADD COLUMN relationship TEXT NOT NULL DEFAULT ''")
            if "age" not in household_columns:
                conn.execute("ALTER TABLE household_members ADD COLUMN age INTEGER")
            if "gender" not in household_columns:
                conn.execute("ALTER TABLE household_members ADD COLUMN gender TEXT NOT NULL DEFAULT ''")
            relationship_columns = {row[1] for row in conn.execute("PRAGMA table_info(family_relationships)")}
            if "edge_type" not in relationship_columns:
                conn.execute("ALTER TABLE family_relationships ADD COLUMN edge_type TEXT NOT NULL DEFAULT 'direct'")
            if "evidence" not in relationship_columns:
                conn.execute("ALTER TABLE family_relationships ADD COLUMN evidence TEXT NOT NULL DEFAULT ''")
            # Older releases eagerly wrote a guessed reverse row (for example
            # 小明→王刚=爸爸 together with 王刚→小明=儿子).  Those rows have no
            # provenance, so migrate only the mechanically paired, near-
            # simultaneous reverse rows to derived edges.  The graph rebuild
            # below will recreate them from the direct statement with evidence.
            conn.execute(
                """UPDATE family_relationships AS reverse
                SET edge_type = 'derived', evidence = '旧版自动反向关系迁移'
                WHERE reverse.edge_type = 'direct' AND reverse.evidence = ''
                  AND reverse.relation IN ('儿子', '女儿', '孙子', '孙女')
                  AND EXISTS (
                    SELECT 1 FROM family_relationships AS forward
                    WHERE forward.family_id = reverse.family_id
                      AND forward.source_name = reverse.target_name
                      AND forward.target_name = reverse.source_name
                      AND (
                        (reverse.relation IN ('儿子', '女儿') AND forward.relation IN ('爸爸', '妈妈'))
                        OR
                        (reverse.relation IN ('孙子', '孙女') AND forward.relation IN ('爷爷', '奶奶', '外公', '外婆'))
                      )
                      AND ABS((julianday(forward.updated_at) - julianday(reverse.updated_at)) * 86400.0) <= 10
                  )"""
            )
            for table, retention in (("health_events", 30), ("activity_events", 4 / 24)):
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if "expires_at" not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN expires_at TEXT")
                    rows = conn.execute(f"SELECT event_id, created_at FROM {table} WHERE expires_at IS NULL").fetchall()
                    for event_id, created_at in rows:
                        expiry = datetime.fromisoformat(created_at) + timedelta(days=retention)
                        conn.execute(f"UPDATE {table} SET expires_at = ? WHERE event_id = ?", (expiry.isoformat(), event_id))
            health_columns = {row[1] for row in conn.execute("PRAGMA table_info(health_events)")}
            if "resolved_at" not in health_columns:
                conn.execute("ALTER TABLE health_events ADD COLUMN resolved_at TEXT")
            self._purge_expired_events(conn)

    @staticmethod
    def _purge_expired_events(conn) -> dict:
        now = datetime.now().isoformat()
        health = conn.execute("DELETE FROM health_events WHERE expires_at <= ?", (now,)).rowcount
        activity = conn.execute("DELETE FROM activity_events WHERE expires_at <= ?", (now,)).rowcount
        return {"health_events": health, "activity_events": activity}

    def purge_expired_events(self) -> dict:
        """Remove expired short-lived activity and health memories."""
        with self._connect() as conn:
            return self._purge_expired_events(conn)

    def set_device_mode(self, device_id: str, mode: str):
        updated_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_modes (device_id, mode, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = excluded.updated_at
                """,
                (device_id, mode, updated_at),
            )

    def get_device_mode(self, device_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mode FROM device_modes WHERE device_id = ?",
                (device_id,),
            ).fetchone()

        if row is None:
            return None

        return row[0]

    def upsert_family_member(self, person_name: str, age: str, gender: str, health_condition: str):
        updated_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO family_members (person_name, age, gender, health_condition, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(person_name) DO UPDATE SET
                    age = excluded.age,
                    gender = excluded.gender,
                    health_condition = excluded.health_condition,
                    updated_at = excluded.updated_at
                """,
                (person_name, age, gender, health_condition, updated_at),
            )

    def get_family_member(self, person_name: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT person_name, age, gender, health_condition
                FROM family_members
                WHERE person_name = ?
                """,
                (person_name,),
            ).fetchone()

        if row is None:
            return None

        return {
            "person_name": row[0],
            "age": row[1],
            "gender": row[2],
            "health_condition": row[3],
        }

    def list_family_members(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT person_name, age, gender, health_condition
                FROM family_members
                ORDER BY updated_at ASC, person_name ASC
                """
            ).fetchall()

        return [
            {
                "person_name": row[0],
                "age": row[1],
                "gender": row[2],
                "health_condition": row[3],
            }
            for row in rows
        ]

    def upsert_device_config(self, config):
        updated_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_configs (
                    device_id, volume, light_profile, wake_method,
                    usage_start, usage_end, content_policy, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    volume = excluded.volume,
                    light_profile = excluded.light_profile,
                    wake_method = excluded.wake_method,
                    usage_start = excluded.usage_start,
                    usage_end = excluded.usage_end,
                    content_policy = excluded.content_policy,
                    updated_at = excluded.updated_at
                """,
                (
                    config.device_id,
                    config.volume,
                    config.light_profile,
                    config.wake_method,
                    config.usage_start,
                    config.usage_end,
                    config.content_policy,
                    updated_at,
                ),
            )

    def get_device_config(self, device_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT device_id, volume, light_profile, wake_method,
                       usage_start, usage_end, content_policy
                FROM device_configs
                WHERE device_id = ?
                """,
                (device_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "device_id": row[0],
            "volume": row[1],
            "light_profile": row[2],
            "wake_method": row[3],
            "usage_start": row[4],
            "usage_end": row[5],
            "content_policy": row[6],
        }

    @staticmethod
    def member_session_id(family_id: str, member_name: str) -> str:
        """Return the same stable per-member web session ID used by the UI."""
        return f"web-{family_id}-{quote(member_name, safe='')}"

    def create_reminder(self, session_id: str, title: str, reminder_time: str, repeat_rule: str = "once", reminder_date: str | None = None, created_by: str | None = None) -> dict:
        """Persist a reminder extracted from a SET_ALARM command."""
        reminder = {"reminder_id": str(uuid4()), "session_id": session_id, "title": title, "reminder_time": reminder_time, "repeat_rule": repeat_rule, "reminder_date": reminder_date, "created_at": datetime.now().isoformat(), "completed_at": None, "last_triggered_date": None, "last_completed_date": None, "created_by": created_by}
        with self._connect() as conn:
            conn.execute("INSERT INTO reminders (reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date, created_at, completed_at, last_triggered_date, last_completed_date, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(reminder.values()))
        return reminder

    def upsert_reminder(self, session_id: str, title: str, reminder_time: str, repeat_rule: str = "once", reminder_date: str | None = None, created_by: str | None = None) -> tuple[dict, bool]:
        """Idempotently create or update a reminder event.

        The same recipient, task, time, date and repeat rule identify one
        logical event for every reminder type. ``BEGIN IMMEDIATE`` serialises
        concurrent writers so duplicate HTTP requests cannot both insert it.
        A short daily correction still updates the only active daily reminder.
        """
        title = title.strip() or "提醒"
        reminder_time = reminder_time.strip()
        repeat_rule = repeat_rule.strip() or "once"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            keys = ("reminder_id", "session_id", "title", "reminder_time", "repeat_rule", "reminder_date", "created_at", "completed_at", "last_triggered_date", "last_completed_date", "created_by")
            exact = conn.execute(
                """SELECT reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date,
                          created_at, completed_at, last_triggered_date, last_completed_date, created_by
                   FROM reminders
                   WHERE session_id = ? AND title = ? AND reminder_time = ? AND repeat_rule = ?
                     AND COALESCE(reminder_date, '') = COALESCE(?, '')
                   ORDER BY created_at LIMIT 1""",
                (session_id, title, reminder_time, repeat_rule, reminder_date),
            ).fetchone()
            if exact:
                return dict(zip(keys, exact)), True

            if repeat_rule != "daily":
                reminder = {"reminder_id": str(uuid4()), "session_id": session_id, "title": title, "reminder_time": reminder_time, "repeat_rule": repeat_rule, "reminder_date": reminder_date, "created_at": datetime.now().isoformat(), "completed_at": None, "last_triggered_date": None, "last_completed_date": None, "created_by": created_by}
                conn.execute(
                    "INSERT INTO reminders (reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date, created_at, completed_at, last_triggered_date, last_completed_date, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(reminder.values()),
                )
                return reminder, False

            rows = conn.execute(
                "SELECT reminder_id, title FROM reminders WHERE session_id = ? AND repeat_rule = 'daily' AND completed_at IS NULL ORDER BY created_at",
                (session_id,),
            ).fetchall()
            if len(rows) == 1:
                reminder_id, old_title = rows[0]
                final_title = old_title if title in ("", "提醒") else title
                conn.execute(
                    "UPDATE reminders SET title = ?, reminder_time = ?, reminder_date = ?, created_by = COALESCE(?, created_by), last_triggered_date = NULL, last_completed_date = NULL WHERE reminder_id = ?",
                    (final_title, reminder_time, reminder_date, created_by, reminder_id),
                )
                row = conn.execute("SELECT reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date, created_at, completed_at, last_triggered_date, last_completed_date, created_by FROM reminders WHERE reminder_id = ?", (reminder_id,)).fetchone()
                return dict(zip(keys, row)), True
            reminder = {"reminder_id": str(uuid4()), "session_id": session_id, "title": title, "reminder_time": reminder_time, "repeat_rule": repeat_rule, "reminder_date": reminder_date, "created_at": datetime.now().isoformat(), "completed_at": None, "last_triggered_date": None, "last_completed_date": None, "created_by": created_by}
            conn.execute(
                "INSERT INTO reminders (reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date, created_at, completed_at, last_triggered_date, last_completed_date, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(reminder.values()),
            )
            return reminder, False

    def list_reminders(self, session_id: str, include_completed: bool = False) -> list[dict]:
        query = "SELECT reminder_id, session_id, title, reminder_time, repeat_rule, reminder_date, created_at, completed_at, last_triggered_date, last_completed_date, created_by FROM reminders WHERE session_id = ?"
        if not include_completed:
            query += " AND completed_at IS NULL"
        query += " ORDER BY reminder_time, created_at"
        with self._connect() as conn:
            rows = conn.execute(query, (session_id,)).fetchall()
        keys = ("reminder_id", "session_id", "title", "reminder_time", "repeat_rule", "reminder_date", "created_at", "completed_at", "last_triggered_date", "last_completed_date", "created_by")
        return [dict(zip(keys, row)) for row in rows]

    def find_reminders_for_recall(self, session_id: str, title_hint: str | None = None, reminder_date: str | None = None) -> list[dict]:
        """Find active reminders belonging to one person for a spoken query."""
        reminders = self.list_reminders(session_id)
        if title_hint:
            reminders = [item for item in reminders if title_hint in item["title"]]
        if reminder_date:
            reminders = [
                item for item in reminders
                if item["repeat_rule"] == "daily" or item.get("reminder_date") in (None, reminder_date)
            ]
        return sorted(reminders, key=lambda item: (item.get("reminder_date") or "", item["reminder_time"]))

    def find_reminder_status_for_creator(self, recipient_session_id: str, created_by: str, reminder_date: str, title_hint: str | None = None) -> list[dict]:
        """Return one sender's active-or-completed tasks for one recipient.

        This is deliberately sender-scoped: a family member can check the
        status of a reminder they created, but not inspect another person's
        private reminder list.
        """
        reminders = [
            item for item in self.list_reminders(recipient_session_id, include_completed=True)
            if item.get("created_by") == created_by
            and (item["repeat_rule"] == "daily" or item.get("reminder_date") in (None, reminder_date))
        ]
        if title_hint:
            reminders = [item for item in reminders if title_hint in item["title"]]
        return sorted(reminders, key=lambda item: (item.get("reminder_date") or "", item["reminder_time"]))

    def complete_reminder(self, reminder_id: str) -> bool:
        """Complete once-only reminders; acknowledge daily ones for today."""
        with self._connect() as conn:
            row = conn.execute("SELECT repeat_rule FROM reminders WHERE reminder_id = ? AND completed_at IS NULL", (reminder_id,)).fetchone()
            if row is None:
                return False
            if row[0] == "daily":
                cursor = conn.execute("UPDATE reminders SET last_completed_date = ? WHERE reminder_id = ?", (datetime.now().date().isoformat(), reminder_id))
            else:
                cursor = conn.execute("UPDATE reminders SET completed_at = ? WHERE reminder_id = ?", (datetime.now().isoformat(), reminder_id))
        return cursor.rowcount == 1

    def delete_reminder(self, reminder_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM reminders WHERE reminder_id = ?", (reminder_id,))
        return cursor.rowcount == 1

    def delete_matching_reminders(self, session_id: str, title_hint: str = "") -> int:
        """Delete active reminders for a session; prefer a named task match."""
        with self._connect() as conn:
            if title_hint:
                cursor = conn.execute(
                    "DELETE FROM reminders WHERE session_id = ? AND title LIKE ?",
                    (session_id, f"%{title_hint}%"),
                )
                if cursor.rowcount:
                    return cursor.rowcount
            cursor = conn.execute("DELETE FROM reminders WHERE session_id = ?", (session_id,))
        return cursor.rowcount

    def mark_reminder_triggered(self, reminder_id: str, triggered_date: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE reminders SET last_triggered_date = ? WHERE reminder_id = ?",
                (triggered_date, reminder_id),
            )
        return cursor.rowcount == 1

    def set_session_location(self, session_id: str, latitude: float, longitude: float, location_name: str) -> dict:
        location = {"session_id": session_id, "latitude": latitude, "longitude": longitude, "location_name": location_name, "updated_at": datetime.now().isoformat()}
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO session_locations (session_id, latitude, longitude, location_name, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET latitude=excluded.latitude, longitude=excluded.longitude, location_name=excluded.location_name, updated_at=excluded.updated_at""",
                tuple(location.values()),
            )
        return location

    def get_session_location(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT session_id, latitude, longitude, location_name, updated_at FROM session_locations WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(("session_id", "latitude", "longitude", "location_name", "updated_at"), row))

    def set_pending_reminder(self, session_id: str, title: str, repeat_rule: str, reminder_date: str | None = None, recipient_session_id: str | None = None, created_by: str | None = None) -> dict:
        pending = {"session_id": session_id, "title": title, "repeat_rule": repeat_rule, "reminder_date": reminder_date, "recipient_session_id": recipient_session_id, "created_by": created_by, "created_at": datetime.now().isoformat()}
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO pending_reminders (session_id, title, repeat_rule, reminder_date, recipient_session_id, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET title=excluded.title, repeat_rule=excluded.repeat_rule, reminder_date=excluded.reminder_date, recipient_session_id=excluded.recipient_session_id, created_by=excluded.created_by, created_at=excluded.created_at""",
                tuple(pending.values()),
            )
        return pending

    def get_pending_reminder(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT session_id, title, repeat_rule, reminder_date, recipient_session_id, created_by, created_at FROM pending_reminders WHERE session_id = ?", (session_id,)).fetchone()
        return dict(zip(("session_id", "title", "repeat_rule", "reminder_date", "recipient_session_id", "created_by", "created_at"), row)) if row else None

    def clear_pending_reminder(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_reminders WHERE session_id = ?", (session_id,))

    def add_health_event(self, family_id: str, person_name: str, symptom: str, session_id: str, occurred_at: str | None = None) -> dict:
        now = datetime.now().isoformat()
        event = {"event_id": str(uuid4()), "family_id": family_id, "person_name": person_name, "symptom": symptom, "source_session_id": session_id, "occurred_at": occurred_at or now, "created_at": now, "expires_at": (datetime.now() + timedelta(days=30)).isoformat(), "resolved_at": None}
        with self._connect() as conn:
            conn.execute("INSERT INTO health_events (event_id, family_id, person_name, symptom, source_session_id, occurred_at, created_at, expires_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(event.values()))
        return event

    def resolve_health_events(self, family_id: str, person_name: str, symptoms: list[str], resolved_at: str | None = None) -> int:
        """Mark matching recent symptoms as recovered without deleting history."""
        values = [item.strip() for item in symptoms if item and item.strip()]
        if not values:
            return 0
        placeholders = ",".join("?" for _ in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""UPDATE health_events SET resolved_at = ?
                WHERE family_id = ? AND person_name = ? AND symptom IN ({placeholders})
                  AND resolved_at IS NULL AND expires_at > ?""",
                (resolved_at or datetime.now().isoformat(), family_id, person_name, *values, datetime.now().isoformat()),
            )
        return cursor.rowcount

    def find_recent_health_events(self, family_id: str, person_name: str, since_iso: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT event_id, family_id, person_name, symptom, source_session_id, occurred_at, created_at, expires_at, resolved_at FROM health_events WHERE family_id = ? AND (person_name = ? OR person_name LIKE ?) AND occurred_at >= ? AND expires_at > ? ORDER BY occurred_at DESC, created_at DESC, rowid DESC", (family_id, person_name, f"%{person_name}", since_iso, datetime.now().isoformat())).fetchall()
        keys = ("event_id", "family_id", "person_name", "symptom", "source_session_id", "occurred_at", "created_at", "expires_at", "resolved_at")
        return [dict(zip(keys, row)) for row in rows]

    def add_activity_event(self, family_id: str, person_name: str, activity: str, session_id: str, occurred_at: str | None = None) -> dict:
        now = datetime.now().isoformat()
        event = {"event_id": str(uuid4()), "family_id": family_id, "person_name": person_name, "activity": activity, "source_session_id": session_id, "occurred_at": occurred_at or now, "created_at": now, "expires_at": (datetime.now() + timedelta(hours=4)).isoformat()}
        with self._connect() as conn:
            conn.execute("INSERT INTO activity_events (event_id, family_id, person_name, activity, source_session_id, occurred_at, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(event.values()))
        return event

    def find_recent_activity_events(self, family_id: str, person_name: str, activity: str, since_iso: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT event_id, family_id, person_name, activity, source_session_id, occurred_at, created_at, expires_at FROM activity_events WHERE family_id = ? AND (person_name = ? OR person_name LIKE ?) AND activity = ? AND occurred_at >= ? AND expires_at > ? ORDER BY occurred_at DESC, created_at DESC, rowid DESC", (family_id, person_name, f"%{person_name}", activity, since_iso, datetime.now().isoformat())).fetchall()
        keys = ("event_id", "family_id", "person_name", "activity", "source_session_id", "occurred_at", "created_at", "expires_at")
        return [dict(zip(keys, row)) for row in rows]

    def add_household_member(self, family_id: str, member_name: str, relationship: str = "", age: int | None = None, gender: str = "") -> dict:
        gender = gender if gender in {"male", "female"} else ""
        member = {"family_id": family_id, "member_name": member_name.strip(), "relationship": relationship.strip(), "age": age, "gender": gender, "created_at": datetime.now().isoformat()}
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO household_members (family_id, member_name, relationship, age, gender, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(family_id, member_name) DO UPDATE SET
                    relationship=CASE WHEN excluded.relationship != '' THEN excluded.relationship ELSE household_members.relationship END,
                    age=COALESCE(excluded.age, household_members.age),
                    gender=CASE WHEN excluded.gender != '' THEN excluded.gender ELSE household_members.gender END""",
                tuple(member.values()),
            )
        return member

    def list_household_members(self, family_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT family_id, member_name, relationship, age, gender, created_at FROM household_members WHERE family_id = ? ORDER BY created_at", (family_id,)).fetchall()
        return [dict(zip(("family_id", "member_name", "relationship", "age", "gender", "created_at"), row)) for row in rows]

    def find_household_member_by_relationship(self, family_id: str, relationship: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT family_id, member_name, relationship, age, gender, created_at FROM household_members WHERE family_id = ? AND relationship = ? ORDER BY created_at LIMIT 1", (family_id, relationship)).fetchone()
        return dict(zip(("family_id", "member_name", "relationship", "age", "gender", "created_at"), row)) if row else None

    @staticmethod
    def _inverse_graph_relation(relation: str, source_gender: str = "") -> str | None:
        if relation in {"爸爸", "妈妈", "父母"}:
            return "儿子" if source_gender == "male" else ("女儿" if source_gender == "female" else "孩子")
        if relation in {"爷爷", "奶奶", "外公", "外婆", "祖辈"}:
            return "孙子" if source_gender == "male" else ("孙女" if source_gender == "female" else "孙辈")
        if relation in {"儿子", "女儿", "孩子"}:
            return "爸爸" if source_gender == "male" else ("妈妈" if source_gender == "female" else "父母")
        if relation in {"孙子", "孙女", "孙辈"}:
            return "爷爷" if source_gender == "male" else ("奶奶" if source_gender == "female" else "祖辈")
        if relation == "老伴":
            return "老伴"
        return None

    def set_family_relationship(
        self,
        family_id: str,
        source_name: str,
        target_name: str,
        relation: str,
        edge_type: str = "direct",
        evidence: str = "",
    ) -> dict:
        edge_type = "derived" if edge_type == "derived" else "direct"
        record = {
            "family_id": family_id, "source_name": source_name.strip(), "target_name": target_name.strip(),
            "relation": relation.strip(), "edge_type": edge_type, "evidence": evidence.strip(),
            "updated_at": datetime.now().isoformat(),
        }
        with self._connect() as conn:
            # These roles identify one person from a speaker's point of view.
            # Re-stating one of them updates the old value instead of leaving
            # two competing targets whose selection depends on timestamps.
            if edge_type == "direct" and record["relation"] in {"奶奶", "爷爷", "外婆", "外公", "爸爸", "妈妈", "老伴"}:
                conn.execute(
                    "DELETE FROM family_relationships WHERE family_id = ? AND source_name = ? AND relation = ? AND target_name <> ?",
                    (record["family_id"], record["source_name"], record["relation"], record["target_name"]),
                )
            conn.execute(
                """INSERT INTO family_relationships
                (family_id, source_name, target_name, relation, edge_type, evidence, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(family_id, source_name, target_name, relation) DO UPDATE SET
                  edge_type=CASE
                    WHEN family_relationships.edge_type='direct' OR excluded.edge_type='direct' THEN 'direct'
                    ELSE 'derived' END,
                  evidence=CASE WHEN excluded.edge_type='direct' THEN excluded.evidence ELSE family_relationships.evidence END,
                  updated_at=excluded.updated_at""",
                tuple(record.values()),
            )
        if edge_type == "direct":
            self.rebuild_family_graph(family_id)
        return record

    def rebuild_all_family_graphs(self) -> None:
        with self._connect() as conn:
            family_ids = [row[0] for row in conn.execute("SELECT DISTINCT family_id FROM family_relationships")]
        for family_id in family_ids:
            self.rebuild_family_graph(family_id)

    def rebuild_family_graph(self, family_id: str) -> None:
        """Rebuild safe inverse and cross-generation edges from direct facts."""
        with self._connect() as conn:
            conn.execute("DELETE FROM family_relationships WHERE family_id = ? AND edge_type = 'derived'", (family_id,))
            direct_rows = conn.execute(
                """SELECT source_name, target_name, relation
                FROM family_relationships WHERE family_id = ? AND edge_type = 'direct'""",
                (family_id,),
            ).fetchall()

            # Gender is inferred only from an explicit gendered kinship word;
            # never from a person's name.
            for _, target, relation in direct_rows:
                gender = RELATION_GENDER.get(relation, "")
                if gender:
                    conn.execute(
                        """UPDATE household_members SET gender = ?
                        WHERE family_id = ? AND member_name = ? AND gender = ''""",
                        (gender, family_id, target),
                    )
            genders = {
                name: gender for name, gender in conn.execute(
                    "SELECT member_name, gender FROM household_members WHERE family_id = ?", (family_id,)
                ).fetchall()
            }

            derived: dict[tuple[str, str, str], str] = {}

            def add_edge(source: str, target: str, relation: str | None, evidence: str) -> None:
                if source and target and source != target and relation:
                    derived[(source, target, relation)] = evidence

            # Every direct edge gets a safe reverse. Unknown gender produces a
            # neutral role such as 孩子/孙辈 instead of a guessed 儿子/孙子.
            for source, target, relation in direct_rows:
                add_edge(
                    target, source,
                    self._inverse_graph_relation(relation, genders.get(source, "")),
                    f"由{source}→{target}的{relation}关系反推",
                )

            direct_map = {(source, relation): target for source, target, relation in direct_rows}
            # Chinese paternal/maternal grandparent terms encode a safe
            # parent-of-parent path.
            for child in {source for source, _, _ in direct_rows}:
                father, mother = direct_map.get((child, "爸爸")), direct_map.get((child, "妈妈"))
                paternal_grandma = direct_map.get((child, "奶奶"))
                paternal_grandpa = direct_map.get((child, "爷爷"))
                maternal_grandma = direct_map.get((child, "外婆"))
                maternal_grandpa = direct_map.get((child, "外公"))
                for parent, grandparent, relation in (
                    (father, paternal_grandma, "妈妈"), (father, paternal_grandpa, "爸爸"),
                    (mother, maternal_grandma, "妈妈"), (mother, maternal_grandpa, "爸爸"),
                ):
                    if parent and grandparent:
                        evidence = f"由{child}的家庭关系路径推导"
                        add_edge(parent, grandparent, relation, evidence)
                        add_edge(
                            grandparent, parent,
                            self._inverse_graph_relation(relation, genders.get(parent, "")), evidence,
                        )

            now = datetime.now().isoformat()
            for (source, target, relation), evidence in derived.items():
                conn.execute(
                    """INSERT INTO family_relationships
                    (family_id, source_name, target_name, relation, edge_type, evidence, updated_at)
                    VALUES (?, ?, ?, ?, 'derived', ?, ?)
                    ON CONFLICT(family_id, source_name, target_name, relation) DO NOTHING""",
                    (family_id, source, target, relation, evidence, now),
                )

    def find_related_member(self, family_id: str, source_name: str, relation: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT m.family_id, m.member_name, m.relationship, m.age, m.gender, m.created_at
                FROM family_relationships r JOIN household_members m
                  ON m.family_id = r.family_id AND m.member_name = r.target_name
                WHERE r.family_id = ? AND r.source_name = ? AND r.relation = ?
                ORDER BY CASE r.edge_type WHEN 'direct' THEN 0 ELSE 1 END, r.updated_at DESC LIMIT 1""",
                (family_id, source_name, relation),
            ).fetchone()
            if row is None and relation in NEUTRAL_RELATIONS:
                neutral = NEUTRAL_RELATIONS[relation]
                rows = conn.execute(
                    """SELECT DISTINCT m.family_id, m.member_name, m.relationship, m.age, m.gender, m.created_at
                    FROM family_relationships r JOIN household_members m
                      ON m.family_id = r.family_id AND m.member_name = r.target_name
                    WHERE r.family_id = ? AND r.source_name = ? AND r.relation = ?""",
                    (family_id, source_name, neutral),
                ).fetchall()
                row = rows[0] if len(rows) == 1 else None
        return dict(zip(("family_id", "member_name", "relationship", "age", "gender", "created_at"), row)) if row else None

    def find_member_by_spoken_relation(self, family_id: str, source_name: str, relation: str) -> dict | None:
        """Resolve a speaker's '奶奶/爸爸…' to one concrete household member.

        Direct relationships are preferred.  For grandparent/parent roles we
        can also reverse an already recorded statement such as “小明是我的孙子”.
        A reverse lookup is only used when it has exactly one candidate, so a
        phrase like “我奶奶” never silently chooses between two grandparents.
        """
        return self.find_related_member(family_id, source_name, relation)

    def list_member_relationships(self, family_id: str, source_name: str) -> list[dict]:
        """Return direct and safely derived relationships for one member."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT target_name, relation, edge_type, evidence, updated_at
                FROM family_relationships
                WHERE family_id = ? AND source_name = ?
                ORDER BY CASE edge_type WHEN 'direct' THEN 0 ELSE 1 END, updated_at DESC""",
                (family_id, source_name),
            ).fetchall()
        return [dict(zip(("target_name", "relation", "edge_type", "evidence", "updated_at"), row)) for row in rows]

    def list_family_relationship_graph(self, family_id: str) -> list[dict]:
        """Return the inspectable edge list for one household relationship graph."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT source_name, target_name, relation, edge_type, evidence, updated_at
                FROM family_relationships WHERE family_id = ?
                ORDER BY source_name, CASE edge_type WHEN 'direct' THEN 0 ELSE 1 END,
                         relation, target_name""",
                (family_id,),
            ).fetchall()
        keys = ("source_name", "target_name", "relation", "edge_type", "evidence", "updated_at")
        return [dict(zip(keys, row)) for row in rows]

    def repair_relationship_target(self, family_id: str, source_name: str, old_target: str, new_target: str) -> bool:
        """Repair a malformed relationship target without deleting member data."""
        if old_target == new_target:
            return False
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT relation, updated_at FROM family_relationships WHERE family_id = ? AND source_name = ? AND target_name = ?",
                (family_id, source_name, old_target),
            ).fetchall()
            for relation, updated_at in rows:
                conn.execute(
                    """INSERT INTO family_relationships (family_id, source_name, target_name, relation, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(family_id, source_name, target_name, relation) DO UPDATE SET updated_at=excluded.updated_at""",
                    (family_id, source_name, new_target, relation, updated_at),
                )
            cursor = conn.execute(
                "DELETE FROM family_relationships WHERE family_id = ? AND source_name = ? AND target_name = ?",
                (family_id, source_name, old_target),
            )
        repaired = cursor.rowcount > 0
        if repaired:
            self.rebuild_family_graph(family_id)
        return repaired

    def upsert_family_fact(self, family_id: str, subject_name: str, fact_key: str, fact_value: str, session_id: str) -> dict:
        """Persist one explicitly stated, long-term family fact (not chat text)."""
        now = datetime.now().isoformat()
        fact = {
            "fact_id": str(uuid4()), "family_id": family_id, "subject_name": subject_name,
            "fact_key": fact_key, "fact_value": fact_value, "source_session_id": session_id,
            "created_at": now, "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO family_facts
                (fact_id, family_id, subject_name, fact_key, fact_value, source_session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(family_id, subject_name, fact_key, fact_value) DO UPDATE SET
                  source_session_id=excluded.source_session_id, updated_at=excluded.updated_at""",
                tuple(fact.values()),
            )
        return fact

    def remove_family_fact(self, family_id: str, subject_name: str, fact_key: str, fact_value: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM family_facts WHERE family_id = ? AND subject_name = ? AND fact_key = ? AND fact_value = ?",
                (family_id, subject_name, fact_key, fact_value),
            )
        return cursor.rowcount > 0

    def upsert_family_preference(self, family_id: str, subject_name: str, category: str, item: str, polarity: str, session_id: str) -> dict:
        """Store one durable preference and replace its opposite state."""
        now = datetime.now().isoformat()
        fact_key = f"偏好:{category}"
        fact_value = f"{polarity}:{item}"
        fact = {
            "fact_id": str(uuid4()), "family_id": family_id, "subject_name": subject_name,
            "fact_key": fact_key, "fact_value": fact_value, "source_session_id": session_id,
            "created_at": now, "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM family_facts WHERE family_id = ? AND subject_name = ? AND fact_key = ? AND fact_value IN (?, ?)",
                (family_id, subject_name, fact_key, f"like:{item}", f"dislike:{item}"),
            )
            conn.execute(
                """INSERT INTO family_facts
                (fact_id, family_id, subject_name, fact_key, fact_value, source_session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(fact.values()),
            )
        return fact

    def list_family_facts(self, family_id: str, subject_name: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT fact_id, family_id, subject_name, fact_key, fact_value, source_session_id, created_at, updated_at
                FROM family_facts WHERE family_id = ? AND subject_name = ? ORDER BY updated_at DESC""",
                (family_id, subject_name),
            ).fetchall()
        keys = ("fact_id", "family_id", "subject_name", "fact_key", "fact_value", "source_session_id", "created_at", "updated_at")
        return [dict(zip(keys, row)) for row in rows]

    def get_household_member(self, family_id: str, member_name: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT family_id, member_name, relationship, age, gender, created_at FROM household_members WHERE family_id = ? AND member_name = ?", (family_id, member_name)).fetchone()
        return dict(zip(("family_id", "member_name", "relationship", "age", "gender", "created_at"), row)) if row else None

    def remove_household_member(self, family_id: str, member_name: str) -> bool:
        """Delete one member's profile and family-scoped memories permanently."""
        name = member_name.strip()
        web_session_id = f"web-{family_id}-{quote(name, safe='')}"
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM household_members WHERE family_id = ? AND member_name = ?",
                (family_id, name),
            )
            if cursor.rowcount:
                conn.execute("DELETE FROM health_events WHERE family_id = ? AND person_name = ?", (family_id, name))
                conn.execute("DELETE FROM activity_events WHERE family_id = ? AND person_name = ?", (family_id, name))
                conn.execute("DELETE FROM family_relationships WHERE family_id = ? AND (source_name = ? OR target_name = ?)", (family_id, name, name))
                conn.execute("DELETE FROM family_facts WHERE family_id = ? AND subject_name = ?", (family_id, name))
                conn.execute("DELETE FROM reminders WHERE session_id = ?", (web_session_id,))
                conn.execute("DELETE FROM pending_reminders WHERE session_id = ?", (web_session_id,))
                conn.execute("DELETE FROM session_locations WHERE session_id = ?", (web_session_id,))
                conn.execute("DELETE FROM device_modes WHERE device_id = ?", (web_session_id,))
                conn.execute("DELETE FROM device_configs WHERE device_id = ?", (web_session_id,))
        removed = cursor.rowcount > 0
        if removed:
            self.rebuild_family_graph(family_id)
        return removed
