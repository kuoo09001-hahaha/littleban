"""Weather-related Agent API routes."""

import logging
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, HTTPException

from config.settings import settings
from schemas.agent import WeatherQueryRequest
from tools.chat_tools import WeatherTool


logger = logging.getLogger("agent_weather_router")
router = APIRouter()


def create_weather_router(weather_tool_factory: Callable[[], WeatherTool] = WeatherTool) -> APIRouter:
    """Create the weather router with injectable tool factory for tests."""

    @router.post("/agent/weather/query")
    async def weather_query_endpoint(request: WeatherQueryRequest):
        """
        统一的天气查询接口
        支持测试模式和正常查询模式
        """
        try:
            location = request.location
            test_mode = request.test_mode

            logger.info(f"天气查询请求: 位置={location}, 测试模式={test_mode}")

            weather_tool = weather_tool_factory()

            if test_mode:
                api_configured = bool(settings.AMAP_API_KEY and settings.AMAP_API_KEY != "您的高德API密钥")

                if not api_configured:
                    return {
                        "success": False,
                        "location": location,
                        "test_mode": True,
                        "api_status": "not_configured",
                        "message": "高德API密钥未配置",
                        "timestamp": datetime.now().isoformat()
                    }

                try:
                    result = await weather_tool._arun(location)
                    return {
                        "success": True,
                        "location": location,
                        "test_mode": True,
                        "api_status": "available",
                        "weather_info": result,
                        "message": "天气API测试成功",
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    logger.error(f"天气API测试失败: {str(e)}")
                    return {
                        "success": False,
                        "location": location,
                        "test_mode": True,
                        "api_status": "error",
                        "error": str(e),
                        "message": "天气API测试失败",
                        "timestamp": datetime.now().isoformat()
                    }

            result = await weather_tool._arun(location)
            return {
                "success": True,
                "location": location,
                "test_mode": False,
                "weather_info": result,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"天气查询失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"天气查询失败: {str(e)}")

    return router

