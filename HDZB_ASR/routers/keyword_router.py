import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.keyword_utils import analyze_keywords, COMMAND_KEYWORDS, COMMAND_PATTERNS

logger = logging.getLogger("Keyword-Router")
router = APIRouter(prefix="", tags=["keyword"])

@router.post("/analyze-text")
async def analyze_text_command(text: str):
    """文本指令分析接口"""
    try:
        keyword_analysis = analyze_keywords(text)
        return JSONResponse({
            "text": text,
            "command_analysis": keyword_analysis
        })
    except Exception as e:
        logger.error(f"文本分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"文本分析失败: {e}")

@router.get("/supported-commands")
async def get_supported_commands():
    """获取支持的关键字列表"""
    return JSONResponse({
        "simple_keywords": COMMAND_KEYWORDS,
        "pattern_commands": COMMAND_PATTERNS
    })