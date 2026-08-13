import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from core.asr import get_asr_model
from core.utils import handle_uploaded_file
from core.speaker_recognition import register_speaker

logger = logging.getLogger("Speaker-Router")
router = APIRouter(prefix="/speaker", tags=["speaker"])

@router.post("/register")
async def register_speaker_route(name: str, file: UploadFile = File(...)):
    """
    注册说话人声纹
    - name: 说话人姓名，如"爷爷"、"奶奶"
    - file: 包含清晰语音的音频文件（建议时长3-5秒，无背景噪音）
    """
    model = get_asr_model()
    try:
        async with handle_uploaded_file(file) as temp_path:
            result = model.generate(
                input=temp_path,
                return_spk_embedding=True
            )
            res = result[0] if result else {}
            spk_embedding = res.get("spk_embedding", None)

        if spk_embedding is None:
            raise HTTPException(status_code=400, detail="无法提取声纹，请确保音频清晰且包含语音")

        register_speaker(name, spk_embedding)

        return JSONResponse({
            "status": "success",
            "message": f"已成功注册说话人 {name}",
            "speaker": name
        })
    except Exception as e:
        logger.error(f"注册说话人失败: {e}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")