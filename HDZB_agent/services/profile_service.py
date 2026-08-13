"""Persistent profile service for family-member information."""

from typing import Optional

from storage.sqlite_store import SQLiteStore


class ProfileService:
    """Manage family member profile data."""

    def __init__(self, store: SQLiteStore):
        self.store = store

    def upsert_family_member(
        self,
        person_name: str,
        age: str = "",
        gender: str = "",
        health_condition: str = "",
    ):
        self.store.upsert_family_member(
            person_name=person_name,
            age=age,
            gender=gender,
            health_condition=health_condition,
        )

    def get_family_member(self, person_name: str) -> Optional[dict]:
        return self.store.get_family_member(person_name)

    def list_family_members(self) -> list[dict]:
        return self.store.list_family_members()

