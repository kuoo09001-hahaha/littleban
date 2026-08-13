# core/speaker_recognition.py
import os
import numpy as np
import logging
from typing import Optional, Dict
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("speaker_recognition")

# 声纹注册目录
REGISTRY_DIR = Path("./data/speaker_registry")
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

def register_speaker(name: str, embedding: np.ndarray):
    """注册说话人声纹"""
    file_path = REGISTRY_DIR / f"{name}.npy"
    np.save(file_path, embedding)
    logger.info(f"已注册说话人 {name}")

def get_registered_speakers() -> Dict[str, np.ndarray]:
    """获取所有已注册说话人声纹"""
    speakers = {}
    for file_path in REGISTRY_DIR.glob("*.npy"):
        name = file_path.stem
        embedding = np.load(file_path)
        speakers[name] = embedding
    return speakers

def identify_speaker(embedding: np.ndarray, threshold: float = 0.7) -> Optional[str]:
    """识别说话人身份，返回姓名或 None"""
    speakers = get_registered_speakers()
    if not speakers:
        return None

    max_sim = -1
    best_name = None
    for name, registered_emb in speakers.items():
        # 确保 embedding 是二维的
        emb = embedding.reshape(1, -1)
        reg_emb = registered_emb.reshape(1, -1)
        sim = cosine_similarity(emb, reg_emb)[0][0]
        if sim > max_sim:
            max_sim = sim
            best_name = name

    return best_name if max_sim >= threshold else None