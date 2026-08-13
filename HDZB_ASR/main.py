# main.py - 更新版本信息
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from core import config
from routers.audio_router import router as audio_router
from routers.keyword_router import router as keyword_router
from routers.chat_router import router as chat_router
from routers.speaker_router import router as speaker_router
from core.asr import get_asr_model, get_model_status

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="语音处理服务",
    description="语音识别 + 指令分析 + 双AI服务独立接口",
    version="2.0.0"  # 更新版本号
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态
_model_warmup_started = False

@app.on_event("startup")
def startup_event():
    """应用启动时立即开始模型预热"""
    global _model_warmup_started
    logger = logging.getLogger("Startup")
    
    logger.info("服务启动中，开始预热ASR模型...")
    _model_warmup_started = True
    
    # 立即开始预热（同步方式，会阻塞启动但确保模型就绪）
    try:
        start_time = time.time()
        model = get_asr_model()  # 同步加载，确保启动完成时模型已就绪
        load_time = time.time() - start_time
        logger.info(f"ASR模型预热完成，耗时: {load_time:.2f}秒")
    except Exception as e:
        logger.error(f"模型预热失败: {e}")
        # 即使失败也继续启动，但后续请求会失败

@app.get("/")
async def root():
    status = get_model_status()
    return {
        "message": "语音处理服务运行中 - 双AI服务独立接口",
        "model_status": status,
        "services": {
            "asr": "语音识别服务",
            "companion": "陪伴助手服务", 
            "agent": "智能Agent服务"
        },
        "endpoints": {
            "companion": {
                "语音对话": "POST /companion/chat",
                "流式对话": "POST /companion/chat/stream", 
                "文本对话": "POST /companion/direct_chat",
                "会话历史": "GET /companion/device/{device_id}/history",
                "清理会话": "DELETE /companion/device/{device_id}/clear"
            },
            "agent": {
                "语音对话": "POST /agent/chat", 
                "音频对话": "POST /agent/audio_chat",
                "文本对话": "POST /agent/direct_chat",
                "会话历史": "GET /agent/device/{device_id}/history", 
                "清理会话": "DELETE /agent/device/{device_id}/clear"
            }
        },
        "version": "2.0.0"
    }

@app.get("/health")
async def health():
    status = get_model_status()
    return {
        "status": "healthy" if status["loaded"] else "warming_up",
        "model_ready": status["loaded"],
        "model_loading": status["loading"],
        "services": {
            "asr": status["loaded"],
            "keyword_analysis": True,
            "device_management": True,
            "companion_service": True,
            "agent_service": True
        }
    }

@app.get("/model/status")
async def model_status():
    """详细的模型状态接口"""
    return get_model_status()

# 注册路由
app.include_router(audio_router)
app.include_router(keyword_router)
app.include_router(chat_router)
app.include_router(speaker_router)

if __name__ == "__main__":
    logger = logging.getLogger("Main")
    logger.info(f"启动服务在 {config.HOST}:{config.PORT}")
    logger.info("双AI服务独立接口:")
    logger.info("  陪伴助手服务: /companion/*")
    logger.info("  智能Agent服务: /agent/*")
    uvicorn.run(app, host=config.HOST, port=config.PORT)