# core/asr.py - 完整版本
import logging
import time
import threading
from typing import Optional
from funasr import AutoModel

logger = logging.getLogger("Core-ASR")

# 全局状态
_model: Optional[AutoModel] = None
_model_loading = False
_model_loaded = False
_model_load_time: Optional[float] = None
_model_load_error: Optional[str] = None

def get_asr_model() -> AutoModel:
    """获取ASR模型（线程安全）"""
    global _model, _model_loading, _model_loaded, _model_load_error
    
    if _model_loaded and _model is not None:
        return _model
    
    if _model_loading:
        # 等待其他线程完成加载
        wait_count = 0
        while _model_loading and wait_count < 300:
            time.sleep(1)
            wait_count += 1
            if wait_count % 10 == 0:
                logger.info(f"等待模型加载... 已等待{wait_count}秒")
        
        if _model_loaded and _model is not None:
            return _model
        elif _model_load_error:
            raise Exception(f"模型加载失败: {_model_load_error}")
        else:
            raise Exception("模型加载超时")
    
    # 开始加载
    _model_loading = True
    _model_load_error = None
    
    try:
        logger.info("开始加载 FunASR 模型...")
        start_time = time.time()
        
        _model = AutoModel(
            model="paraformer-zh",
            model_revision="v2.0.4",
            vad_model="fsmn-vad",
            vad_model_revision="v2.0.4",
            punc_model="ct-punc",
            punc_model_revision="v2.0.4",
            spk_model="cam++",  # 增加声纹识别
            disable_update=True
        )
        
        _model_load_time = time.time() - start_time
        _model_loaded = True
        logger.info(f"FunASR 模型加载完成，耗时: {_model_load_time:.2f}秒")
        
        return _model
        
    except Exception as e:
        _model_load_error = str(e)
        logger.error(f"模型加载失败: {e}")
        raise
    finally:
        _model_loading = False

def get_model_status():
    """获取详细的模型状态"""
    return {
        "loaded": _model_loaded,
        "loading": _model_loading,
        "load_time": _model_load_time,
        "model_ready": _model is not None,
        "error": _model_load_error,
        "timestamp": time.time()
    }

def wait_for_model(timeout: int = 300) -> bool:
    """等待模型加载完成"""
    start_time = time.time()
    while not _model_loaded and (time.time() - start_time) < timeout:
        time.sleep(1)
    return _model_loaded