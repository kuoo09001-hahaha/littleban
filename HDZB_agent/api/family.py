"""Family roster APIs for the local shared-memory space."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class FamilyMemberRequest(BaseModel):
    member_name: str = Field(..., min_length=1, max_length=32)
    age: int | None = Field(None, ge=0, le=130, description="年龄；填写后用于自动切换儿童/长辈模式")


def create_family_router(get_store) -> APIRouter:
    router = APIRouter(tags=["family"])

    @router.get("/agent/families/{family_id}/members")
    async def list_members(family_id: str):
        return {"family_id": family_id, "members": get_store().list_household_members(family_id)}

    @router.post("/agent/families/{family_id}/members")
    async def add_member(family_id: str, request: FamilyMemberRequest):
        name = request.member_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="成员名字不能为空")
        return {
            "success": True,
            "member": get_store().add_household_member(family_id, name, age=request.age),
        }

    @router.get("/agent/families/{family_id}/members/{member_name}/facts")
    async def list_member_facts(family_id: str, member_name: str):
        if not get_store().get_household_member(family_id, member_name):
            raise HTTPException(status_code=404, detail="没有找到这个家庭成员")
        return {
            "family_id": family_id,
            "member_name": member_name,
            "facts": get_store().list_family_facts(family_id, member_name),
            "relationships": get_store().list_member_relationships(family_id, member_name),
        }

    @router.delete("/agent/families/{family_id}/members/{member_name}")
    async def remove_member(family_id: str, member_name: str):
        if not get_store().remove_household_member(family_id, member_name):
            raise HTTPException(status_code=404, detail="没有找到这个家庭成员")
        return {"success": True, "member_name": member_name}

    return router
