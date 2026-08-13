# core/device_utils.py
import os
import re
import logging
from typing import Optional

logger = logging.getLogger("Device-Utils")

def extract_device_id(filename: str) -> str:
    """
    从文件名中提取设备ID
    文件名格式必须为: @设备号@文件名.扩展名
    例如: @device001@voice_message.amr -> device001
    
    如果找不到设备ID，直接抛出 ValueError
    """
    basename = os.path.basename(filename)
    
    # 严格匹配格式: @设备号@文件名
    pattern = r'^@([^@]+)@'
    match = re.match(pattern, basename)
    
    if not match:
        raise ValueError(f"文件名格式错误: {filename}。必须为 @设备号@文件名.扩展名 格式")
    
    device_id = match.group(1)
    
    if not device_id or device_id.strip() == "":
        raise ValueError(f"设备ID为空: {filename}")
    
    logger.info(f"从文件名 {filename} 中提取到设备ID: {device_id}")
    return device_id