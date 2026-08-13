# routers/chat_router.py - 完整版本，双服务独立接口
import logging
import httpx
import json
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from core import config
from core.asr import get_asr_model
from core.utils import handle_uploaded_file
from core.device_utils import extract_device_id
from core.response_utils import normalize_agent_response
from core.speaker_recognition import identify_speaker

logger = logging.getLogger("Chat-Router")
router = APIRouter(prefix="", tags=["chat"])

# 服务配置
COMPANION_SERVICE = {
    "name": "陪伴助手",
    "url_non_stream": config.COMPANION_CHAT_URL,
    "url_stream": config.COMPANION_STREAM_URL,
    "health_check": config.COMPANION_HEALTH_URL,
    "base_url": config.COMPANION_SERVICE_URL,
}

AGENT_SERVICE = {
    "name": "智能Agent", 
    "url_non_stream": config.AGENT_CHAT_URL,
    "url_audio_chat": config.AGENT_AUDIO_CHAT_URL,
    "health_check": config.AGENT_HEALTH_URL,
    "base_url": config.AGENT_SERVICE_URL,
}

# =============================================================================
# 陪伴助手服务接口（原有服务）
# =============================================================================

@router.post("/companion/chat")
async def companion_chat(file: UploadFile = File(...)):
    """陪伴助手语音对话 - 原有服务接口"""
    model = get_asr_model()
    
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id
        
        logger.info(f"陪伴助手对话 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 语音识别
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(input=temp_path)
            text = result[0].get("text", "") if result else ""
            if not text.strip():
                raise HTTPException(status_code=400, detail="未识别到语音内容")

        # 调用陪伴助手服务
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COMPANION_SERVICE["url_non_stream"],
                json={
                    "message": text,
                    "session_id": session_id
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        return JSONResponse({
            "service": COMPANION_SERVICE["name"],
            "asr_text": text,
            "ai_response": ai_data["response"],
            "session_id": ai_data["session_id"],
            "device_id": device_id,
            "message": f"设备 {device_id} 的陪伴助手对话已完成"
        })
        
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"陪伴助手服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="陪伴助手服务不可用")
    except Exception as e:
        logger.exception("companion_chat 失败")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/companion/chat/stream")
async def companion_chat_stream(file: UploadFile = File(...)):
    """陪伴助手流式对话 - 原有服务接口"""
    model = get_asr_model()
    
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id
        
        logger.info(f"陪伴助手流式对话 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 语音识别
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(input=temp_path)
            text = result[0].get("text", "") if result else ""
            if not text.strip():
                raise HTTPException(status_code=400, detail="未识别到语音内容")
                
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("ASR 失败")
        raise HTTPException(status_code=500, detail=f"ASR 失败: {str(e)}")

    async def generate_stream():
        """流式响应生成器"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream(
                    "POST",
                    COMPANION_SERVICE["url_stream"],
                    json={
                        "message": text,
                        "session_id": session_id
                    },
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                chunk = json.loads(data)
                                if "content" in chunk and chunk["content"]:
                                    # 控制台实时打印
                                    print(chunk["content"], end="", flush=True)
                                    # 发送给前端
                                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            except json.JSONDecodeError:
                                continue
            print()  # 换行
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(), 
        media_type="text/event-stream",
        headers={
            "X-Device-ID": device_id,
            "X-Session-ID": session_id,
            "X-Service": "companion"
        }
    )

# =============================================================================
# 智能Agent服务接口（新服务）
# =============================================================================

@router.post("/agent/chat")
async def agent_chat(
    file: UploadFile = File(...),
    mode: str = Form("elder"),
    family_id: str = Form("default"),
    actor_name: str | None = Form(None),
):
    """智能Agent语音对话 - 新服务接口"""
    model = get_asr_model()
    
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id  # 设备ID直接作为会话ID
        
        logger.info(f"智能Agent对话 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 语音识别
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(input=temp_path,return_spk_embedding=True)# 新增返回声纹向量
            text = result[0].get("text", "") if result else ""
            spk_embedding = result[0].get("spk_embedding", None)# 新增返回声纹向量
            if not text.strip():
                raise HTTPException(status_code=400, detail="未识别到语音内容")
            
         # 识别说话人身份
        speaker = None
        if spk_embedding is not None:
            speaker = identify_speaker(spk_embedding)
            logger.info(f"识别说话人: {speaker}")

        # 调用Agent服务 - 确保传递正确的session_id
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AGENT_SERVICE["url_non_stream"],
                json={
                    "message": text,
                    "session_id": session_id,  # 使用设备ID作为session_id
                    "speaker": speaker,      # 传递说话人信姓名
                    "agent_type": "companion",
                    "mode": mode,
                    "family_id": family_id,
                    "actor_name": actor_name,
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        # 检查返回的session_id是否与我们发送的一致
        returned_session_id = ai_data.get("session_id", "")
        if returned_session_id != session_id:
            logger.warning(f"Session ID不匹配: 发送={session_id}, 返回={returned_session_id}")

        # 修改：适配新的响应格式
        ai_response = ai_data.get("response", "")
        if isinstance(ai_response, dict):
            # 如果response是字典，提取文本内容
            ai_response_text = ai_response.get("text", "") if isinstance(ai_response, dict) else str(ai_response)
        else:
            ai_response_text = str(ai_response)

        return JSONResponse({
            "service": AGENT_SERVICE["name"],
            "asr_text": text,
            "ai_response": ai_response_text,  # 修改：确保是字符串
            "session_id": session_id,  # 始终返回设备ID作为session_id
            "device_id": device_id,
            "speaker": speaker,                     # 前端可显示当前说话人
            "success": ai_data.get("success", True),
            "tool_used": ai_data.get("tool_used", False),
            "tool_results": ai_data.get("tool_results", []),
            "command_type": ai_data.get("command_type", None),
            "metadata": ai_data.get("metadata", {}),
        })
        
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"智能Agent服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="智能Agent服务不可用")
    except Exception as e:
        logger.exception("agent_chat 失败")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/audio_chat")
async def agent_audio_chat(file: UploadFile = File(...)):
    """智能Agent音频直接对话 - 音频直接发送给Agent处理"""
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id  # 设备ID直接作为会话ID
        
        logger.info(f"智能Agent音频对话 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 直接将音频文件发送给Agent服务处理
        async with httpx.AsyncClient() as client:
            # 读取文件内容
            file_content = await file.read()
            files = {"file": (file.filename, file_content, file.content_type)}
            
            response = await client.post(
                AGENT_SERVICE["url_audio_chat"],
                files=files,
                data={"session_id": session_id},  # 确保传递session_id
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        # 检查返回的session_id
        returned_session_id = ai_data.get("session_id", "")
        if returned_session_id != session_id:
            logger.warning(f"Session ID不匹配: 发送={session_id}, 返回={returned_session_id}")

        return JSONResponse({
            "service": AGENT_SERVICE["name"],
            "device_id": device_id,
            "session_id": session_id,  # 始终返回设备ID作为session_id
            "ai_response": ai_data["response"],
            "success": ai_data.get("success", True),
            "metadata": ai_data.get("metadata", {}),
            "message": f"设备 {device_id} 的智能Agent音频对话已完成"
        })
        
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"智能Agent服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="智能Agent服务不可用")
    except Exception as e:
        logger.exception("agent_audio_chat 失败")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 直接文本对话接口（双服务支持）
# =============================================================================

@router.post("/companion/direct_chat")
async def companion_direct_chat(message: str, session_id: str):
    """陪伴助手直接文本对话"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COMPANION_SERVICE["url_non_stream"],
                json={
                    "message": message,
                    "session_id": session_id
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        return JSONResponse({
            "service": COMPANION_SERVICE["name"],
            "user_message": message,
            "ai_response": ai_data["response"],
            "session_id": ai_data["session_id"]
        })
        
    except httpx.HTTPError as e:
        logger.error(f"陪伴助手服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="陪伴助手服务不可用")
    except Exception as e:
        logger.exception("companion_direct_chat 失败")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/direct_chat")
async def agent_direct_chat(message: str, session_id: str):
    """智能Agent直接文本对话"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                AGENT_SERVICE["url_non_stream"],
                json={
                    "message": message,
                    "session_id": session_id,
                    "agent_type": "companion"
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        # 修改：适配新的响应格式
        ai_response = ai_data.get("response", "")
        if isinstance(ai_response, dict):
            ai_response_text = ai_response.get("text", "") if isinstance(ai_response, dict) else str(ai_response)
        else:
            ai_response_text = str(ai_response)

        return JSONResponse({
            "service": AGENT_SERVICE["name"],
            "user_message": message,
            "ai_response": ai_response_text,  # 修改：确保是字符串
            "session_id": ai_data["session_id"],
            "success": ai_data.get("success", True),
            "tool_used": ai_data.get("tool_used", False),
            "tool_results": ai_data.get("tool_results", []),
            "command_type": ai_data.get("command_type", None),
            "metadata": ai_data.get("metadata", {})
        })
        
    except httpx.HTTPError as e:
        logger.error(f"智能Agent服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="智能Agent服务不可用")
    except Exception as e:
        logger.exception("agent_direct_chat 失败")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 设备管理接口（双服务支持）
# =============================================================================

@router.get("/companion/device/{device_id}/history")
async def get_companion_device_history(device_id: str):
    """获取陪伴助手设备会话历史"""
    try:
        session_id = device_id
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{COMPANION_SERVICE['base_url']}/sessions/{session_id}")
            if response.status_code == 200:
                history = response.json()
                return {
                    "service": COMPANION_SERVICE["name"],
                    "device_id": device_id,
                    "session_id": session_id,
                    "history": history
                }
            else:
                raise HTTPException(status_code=404, detail="设备会话不存在")
    except Exception as e:
        logger.error(f"获取陪伴助手设备历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话历史失败: {str(e)}")

@router.get("/agent/device/{device_id}/history")
async def get_agent_device_history(device_id: str):
    """获取智能Agent设备会话历史"""
    try:
        session_id = device_id
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AGENT_SERVICE['base_url']}/agent/sessions/{session_id}")
            if response.status_code == 200:
                history_data = response.json()
                return {
                    "service": AGENT_SERVICE["name"],
                    "device_id": device_id,
                    "session_id": session_id,
                    "conversation_history": history_data.get("conversation_history", []),
                    "important_memories": history_data.get("important_memories", []),
                    "session_data": history_data.get("session_data", {})
                }
            else:
                raise HTTPException(status_code=404, detail="设备会话不存在")
    except Exception as e:
        logger.error(f"获取智能Agent设备历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话历史失败: {str(e)}")

@router.delete("/companion/device/{device_id}/clear")
async def clear_companion_device_session(device_id: str):
    """清理陪伴助手设备会话"""
    try:
        session_id = device_id
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{COMPANION_SERVICE['base_url']}/sessions/{session_id}")
            if response.status_code == 200:
                return {
                    "service": COMPANION_SERVICE["name"],
                    "message": f"设备 {device_id} 的陪伴助手会话已清理",
                    "device_id": device_id
                }
            else:
                return {
                    "service": COMPANION_SERVICE["name"],
                    "message": f"设备 {device_id} 的陪伴助手会话不存在",
                    "device_id": device_id
                }
    except Exception as e:
        logger.error(f"清理陪伴助手设备会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理会话失败: {str(e)}")

@router.delete("/agent/device/{device_id}/clear")
async def clear_agent_device_session(device_id: str):
    """清理智能Agent设备会话"""
    try:
        session_id = device_id
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{AGENT_SERVICE['base_url']}/agent/sessions/{session_id}")
            if response.status_code == 200:
                return {
                    "service": AGENT_SERVICE["name"],
                    "message": f"设备 {device_id} 的智能Agent会话已清理",
                    "device_id": device_id
                }
            else:
                return {
                    "service": AGENT_SERVICE["name"],
                    "message": f"设备 {device_id} 的智能Agent会话不存在",
                    "device_id": device_id
                }
    except Exception as e:
        logger.error(f"清理智能Agent设备会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理会话失败: {str(e)}")

# =============================================================================
# 服务状态检查
# =============================================================================

@router.get("/services/status")
async def get_services_status():
    """获取所有AI服务状态"""
    status = {}
    
    # 检查陪伴助手服务
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 假设陪伴助手有健康检查端点
            response = await client.get(COMPANION_SERVICE["health_check"])
            status["companion"] = {
                "name": COMPANION_SERVICE["name"],
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": COMPANION_SERVICE["url_non_stream"]
            }
    except Exception as e:
        status["companion"] = {
            "name": COMPANION_SERVICE["name"],
            "status": "offline",
            "error": str(e)
        }
    
    # 检查智能Agent服务
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(AGENT_SERVICE["health_check"])
            status["agent"] = {
                "name": AGENT_SERVICE["name"],
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": AGENT_SERVICE["url_non_stream"]
            }
    except Exception as e:
        status["agent"] = {
            "name": AGENT_SERVICE["name"],
            "status": "offline",
            "error": str(e)
        }
    
    # 检查ASR服务状态
    from core.asr import get_model_status
    asr_status = get_model_status()
    status["asr"] = {
        "name": "语音识别服务",
        "status": "healthy" if asr_status["loaded"] else "warming_up",
        "model_ready": asr_status["loaded"],
        "model_loading": asr_status["loading"]
    }
    
    return {
        "services": status,
        "timestamp": __import__("time").time()
    }

# =============================================================================
# 兼容性接口（保持原有接口不变）
# =============================================================================

# ------- 非流式：一次性返回 -------
@router.post("/chat_with_ai")
async def chat_with_ai_legacy(file: UploadFile = File(...)):
    """原有接口 - 转发到陪伴助手服务（保持兼容）"""
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id
        
        logger.info(f"兼容接口 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 语音识别
        model = get_asr_model()
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(input=temp_path)
            text = result[0].get("text", "") if result else ""
            if not text.strip():
                raise HTTPException(status_code=400, detail="未识别到语音内容")

        # 调用陪伴助手服务 - 使用正确的变量名
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COMPANION_SERVICE["url_non_stream"],  # 修复：使用正确的变量名
                json={
                    "message": text,
                    "session_id": session_id
                },
                timeout=30.0
            )
            response.raise_for_status()
            ai_data = response.json()

        return JSONResponse({
            "asr_text": text,
            "ai_response": ai_data["response"],
            "session_id": ai_data["session_id"],
            "device_id": device_id,
            "message": f"设备 {device_id} 的对话已完成"
        })
        
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"陪伴助手服务调用失败: {e}")
        raise HTTPException(status_code=502, detail="陪伴助手服务不可用")
    except Exception as e:
        logger.exception("chat_with_ai 失败")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat_with_ai/stream")
async def chat_with_ai_stream_legacy(file: UploadFile = File(...)):
    """原有接口 - 转发到陪伴助手流式服务（保持兼容）"""
    model = get_asr_model()
    
    try:
        # 从文件名提取设备ID
        device_id = extract_device_id(file.filename)
        session_id = device_id
        
        logger.info(f"兼容流式接口 - 设备ID: {device_id}, 文件名: {file.filename}")
        
        # 语音识别
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(input=temp_path)
            text = result[0].get("text", "") if result else ""
            if not text.strip():
                raise HTTPException(status_code=400, detail="未识别到语音内容")
                
    except ValueError as e:
        logger.error(f"设备ID提取失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("ASR 失败")
        raise HTTPException(status_code=500, detail=f"ASR 失败: {str(e)}")

    async def generate_stream():
        """流式响应生成器"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream(
                    "POST",
                    COMPANION_SERVICE["url_stream"],  # 修复：使用正确的变量名
                    json={
                        "message": text,
                        "session_id": session_id
                    },
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                chunk = json.loads(data)
                                if "content" in chunk and chunk["content"]:
                                    # 控制台实时打印
                                    print(chunk["content"], end="", flush=True)
                                    # 发送给前端
                                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            except json.JSONDecodeError:
                                continue
            print()  # 换行
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(), 
        media_type="text/event-stream",
        headers={
            "X-Device-ID": device_id,
            "X-Session-ID": session_id
        }
    )
