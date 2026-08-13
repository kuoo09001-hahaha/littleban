import os
import time
import subprocess
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse

from core import config
from core.asr import get_asr_model
from core.utils import which_ffmpeg, handle_uploaded_file, create_temp_file, batch_temp_files

logger = logging.getLogger("Audio-Router")
router = APIRouter(prefix="", tags=["audio"])

# ----------------------------------------------------------------------
# 新接口：单纯接收文件并保存到桌面
# ----------------------------------------------------------------------
@router.post("/save-file")
async def save_file_to_desktop(
    file: UploadFile = File(..., description="要保存到桌面的文件")
):
    """
    单纯接收文件并保存到配置的上传目录
    - 接收任意文件
    - 返回保存的文件路径
    """
    try:
        save_dir = config.SAVE_FILE_DIR
        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
        
        # 构建保存路径
        file_path = os.path.join(save_dir, file.filename)
        
        # 处理文件名冲突
        counter = 1
        name, ext = os.path.splitext(file.filename)
        while os.path.exists(file_path):
            file_path = os.path.join(save_dir, f"{name}_{counter}{ext}")
            counter += 1
        
        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"文件已保存到: {file_path}")
        return JSONResponse({
            "status": "success",
            "message": "文件保存成功",
            "file_path": file_path
        })
    
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

########## 原版 #############
# @router.post("/transcribe")
# async def transcribe_audio(file: UploadFile = File(..., description="音频文件")):
#     """语音识别接口 - 使用新的临时文件处理"""
#     model = get_asr_model()  
#     start = time.time()

#     try:
#         async with handle_uploaded_file(file) as temp_path:
#             result = model.generate(input=temp_path)
#             text = result[0].get("text", "") if result else ""
#             cost = time.time() - start
            
#             # 关键字分析（需要导入analyze_keywords）
#             from core.keyword_utils import analyze_keywords
#             keyword_analysis = analyze_keywords(text)
            
#             return JSONResponse({
#                 "text": text, 
#                 "processing_time": cost,
#                 "keyword_analysis": keyword_analysis
#             })
#     except Exception as e:
#         logger.error(f"识别失败: {e}")
#         raise HTTPException(status_code=500, detail=f"识别失败: {e}")

########## 返回声纹识别结果 #############
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    model = get_asr_model()
    start = time.time()

    try:
        async with handle_uploaded_file(file) as temp_path:
            # 返回声纹嵌入
            result = model.generate(
                input=temp_path,
                return_spk_embedding=True
            )
            res = result[0]
            text = res.get("text", "")
            spk_embedding = res.get("spk_embedding", None)

            # 识别说话人
            speaker = None
            if spk_embedding is not None:
                from core.speaker_recognition import identify_speaker
                speaker = identify_speaker(spk_embedding)
                logger.info(f"识别说话人: {speaker}")

            cost = time.time() - start

            from core.keyword_utils import analyze_keywords
            keyword_analysis = analyze_keywords(text)

            return JSONResponse({
                "text": text,
                "processing_time": cost,
                "keyword_analysis": keyword_analysis,
                "speaker": speaker
            })
    except Exception as e:
        logger.error(f"识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")

@router.post("/convert")
async def convert_amr_to_mp3(
    file: UploadFile = File(..., description="AMR音频文件"),
    ac: int = config.DEFAULT_AC,
    ar: int = config.DEFAULT_AR,
    bitrate: str = config.DEFAULT_BITRATE,
):
    """AMR转MP3接口 - 使用新的临时文件处理"""
    ffmpeg_path = which_ffmpeg()
    if not ffmpeg_path:
        raise HTTPException(status_code=503, detail="ffmpeg 未就绪")

    start = time.time()
    
    try:
        # 使用批量临时文件处理
        with batch_temp_files(2, ".mp3") as temp_paths:
            input_path, output_path = temp_paths
            
            # 保存上传文件到输入路径
            content = await file.read()
            with open(input_path, "wb") as f:
                f.write(content)
            
            # 执行转换
            cmd = [
                ffmpeg_path, "-y", "-i", input_path, "-vn",
                "-ac", str(ac), "-ar", str(ar),
                "-c:a", "libmp3lame", "-b:a", bitrate, output_path
            ]
            
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 返回转换后的文件
            def iter_file():
                with open(output_path, "rb") as f:
                    yield from f

            return StreamingResponse(
                iter_file(),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f'attachment; filename="{os.path.splitext(file.filename)[0]}.mp3"'}
            )
    except Exception as e:
        logger.error(f"转码失败: {e}")
        raise HTTPException(status_code=500, detail=f"转码失败: {e}")

@router.post("/amr-to-text")
async def amr_to_text(file: UploadFile = File(..., description="AMR音频文件")):
    """AMR直接转文本接口 - 使用新的临时文件处理"""
    ffmpeg_path = which_ffmpeg()
    if not ffmpeg_path:
        raise HTTPException(status_code=503, detail="ffmpeg 未就绪")

    model = get_asr_model()
    t0 = time.time()

    try:
        # 使用嵌套的临时文件处理
        async with handle_uploaded_file(file, ".amr") as amr_path:
            async with create_temp_file(".mp3") as mp3_path:
                # 转换AMR到MP3
                cmd = [
                    ffmpeg_path, "-y", "-i", amr_path, "-vn",
                    "-ac", str(config.DEFAULT_AC), "-ar", str(config.DEFAULT_AR),
                    "-c:a", "libmp3lame", "-b:a", config.DEFAULT_BITRATE, mp3_path
                ]
                
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 语音识别
                result = model.generate(input=mp3_path)
                text = result[0].get("text", "") if result else ""
                cost = time.time() - t0

                return JSONResponse({"text": text, "processing_time": cost})
    except Exception as e:
        logger.error(f"处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")
