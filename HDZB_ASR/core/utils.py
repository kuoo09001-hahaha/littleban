# utils.py
import os
import shutil
import logging
import tempfile
from contextlib import contextmanager, asynccontextmanager
from fastapi import UploadFile
from typing import Union, List

# 配置日志
logger = logging.getLogger("AMR2MP3-FunASR-Utils")

# ---------------- 工具函数 ----------------

def which_ffmpeg() -> str | None:
    """查找系统中的 ffmpeg 可执行文件路径"""
    return shutil.which("ffmpeg")

def safe_unlink(path: str):
    """安全删除临时文件"""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception as e:
        logger.warning(f"无法删除临时文件 {path}: {e}")

def safe_unlink_multiple(paths: List[str]):
    """安全删除多个临时文件"""
    for path in paths:
        safe_unlink(path)

# ---------------- 统一临时文件处理接口 ----------------

@asynccontextmanager
async def handle_uploaded_file(
    upload_file: UploadFile, 
    suffix: str = None,
    keep_original_extension: bool = True
):
    """
    统一处理上传文件的异步上下文管理器
    
    参数:
    - upload_file: FastAPI的UploadFile对象
    - suffix: 自定义后缀，如 ".wav", ".mp3"
    - keep_original_extension: 是否保留原始文件扩展名
    
    使用示例:
    async with handle_uploaded_file(file) as temp_path:
        # 使用临时文件路径进行处理
        result = process_audio(temp_path)
    """
    if keep_original_extension and upload_file.filename:
        original_suffix = os.path.splitext(upload_file.filename)[1]
        suffix = suffix or original_suffix or ".tmp"
    else:
        suffix = suffix or ".tmp"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        # 读取上传文件内容
        content = await upload_file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        yield temp_file_path
    finally:
        safe_unlink(temp_file_path)

@asynccontextmanager
async def create_temp_file(suffix: str = ".tmp", content: bytes = None):
    """
    创建临时文件的异步上下文管理器
    
    参数:
    - suffix: 文件后缀
    - content: 可选的文件内容
    
    使用示例:
    async with create_temp_file(".mp3") as temp_path:
        # 创建空临时文件或写入内容
        with open(temp_path, "wb") as f:
            f.write(audio_data)
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        if content:
            temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        yield temp_file_path
    finally:
        safe_unlink(temp_file_path)

@contextmanager
def batch_temp_files(count: int, suffix: str = ".tmp"):
    """
    批量创建临时文件的上下文管理器
    
    参数:
    - count: 需要创建的临时文件数量
    - suffix: 文件后缀
    
    使用示例:
    with batch_temp_files(2, ".mp3") as temp_paths:
        input_path, output_path = temp_paths
        # 使用多个临时文件
    """
    temp_files = []
    try:
        for i in range(count):
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_files.append(temp_file.name)
        yield temp_files
    finally:
        for temp_file in temp_files:
            safe_unlink(temp_file)

# ---------------- 音频处理专用函数 ----------------

async def process_audio_with_temp_file(
    upload_file: UploadFile, 
    process_func,
    input_suffix: str = None,
    output_suffix: str = None
):
    """
    高级函数：使用临时文件处理音频的完整流程
    
    参数:
    - upload_file: 上传的音频文件
    - process_func: 处理函数，接受输入路径，返回输出路径或结果
    - input_suffix: 输入文件后缀
    - output_suffix: 输出文件后缀（如果需要输出文件）
    
    返回: 处理函数的返回结果
    """
    async with handle_uploaded_file(upload_file, input_suffix) as input_path:
        return await process_func(input_path)