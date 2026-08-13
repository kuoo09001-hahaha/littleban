"""Personal information Agent API routes."""

import logging
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, HTTPException

from schemas.agent import PersonalInfoRequest


logger = logging.getLogger("agent_personal_info_router")
router = APIRouter()


def create_personal_info_router(get_companion_agent: Callable[[], object]) -> APIRouter:
    """Create personal-info routes with access to the initialized companion agent."""

    @router.post("/agent/personal_info/add")
    async def add_personal_info_endpoint(request: PersonalInfoRequest):
        """添加家庭成员个人信息"""
        try:
            person_name = request.person_name
            age = request.age
            gender = request.gender
            health_condition = request.health_condition

            logger.info(f"添加个人信息请求: {person_name}, {age}岁, {gender}, {health_condition}")

            companion_agent = get_companion_agent()
            if not companion_agent:
                raise HTTPException(status_code=500, detail="Companion Agent未初始化")

            result = await companion_agent._execute_add_personal_info_tool({
                "person_name": person_name,
                "age": age or "",
                "gender": gender or "",
                "health_condition": health_condition or ""
            })

            return {
                "success": True,
                "message": "个人信息添加成功",
                "person_name": person_name,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"添加个人信息失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"添加个人信息失败: {str(e)}")

    @router.get("/agent/personal_info/{person_name}")
    async def get_personal_info_endpoint(person_name: str):
        """获取家庭成员个人信息"""
        try:
            logger.info(f"查询个人信息请求: {person_name}")

            companion_agent = get_companion_agent()
            if not companion_agent:
                raise HTTPException(status_code=500, detail="Companion Agent未初始化")

            result = await companion_agent._execute_recall_personal_info_tool({
                "person_name": person_name
            })

            return {
                "success": True,
                "person_name": person_name,
                "personal_info": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"查询个人信息失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"查询个人信息失败: {str(e)}")

    @router.get("/agent/personal_info")
    async def list_family_members_endpoint():
        """列出所有已记录的家庭成员"""
        try:
            logger.info("列出家庭成员请求")

            companion_agent = get_companion_agent()
            if not companion_agent:
                raise HTTPException(status_code=500, detail="Companion Agent未初始化")

            result = await companion_agent._execute_list_family_members_tool({
                "query": "列出所有家庭成员"
            })

            return {
                "success": True,
                "family_members": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"列出家庭成员失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"列出家庭成员失败: {str(e)}")

    return router

