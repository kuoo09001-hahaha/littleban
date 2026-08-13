"""
应用配置管理模块
集中管理所有配置参数，支持环境变量和默认值
移除缓存相关配置，简化设置
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load the checked-out project's shared template first, then let the Agent's
# private local file override it. This works regardless of the directory from
# which uvicorn is launched.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "HDZB_agent" / ".env", override=True)

class Settings:
    """
    配置管理类
    
    功能特性:
    - 统一管理所有配置参数
    - 支持环境变量和默认值
    - 类型安全的数据访问
    - 配置分组和文档化
    """
    
    # ==================== API配置 ====================
    # DeepSeek API配置 (火山引擎方舟平台)
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "您的API密钥")
    ARK_API_URL: str = os.getenv("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
    ARK_MODEL_NAME: str = os.getenv("ARK_MODEL_NAME", "deepseek-v3-250324")
    
    # 高德地图API配置
    AMAP_API_KEY: str = os.getenv("AMAP_API_KEY", "您的高德API密钥")
    AMAP_WEATHER_URL: str = "https://restapi.amap.com/v3/weather/weatherInfo"
    AMAP_GEOCODE_URL: str = "https://restapi.amap.com/v3/geocode/geo"
    AMAP_REGEOCODE_URL: str = "https://restapi.amap.com/v3/geocode/regeo"
    
    # ==================== 服务器配置 ====================
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8017"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # ==================== 记忆配置 ====================
    MEMORY_MAX_TOKENS: int = int(os.getenv("MEMORY_MAX_TOKENS", "2000"))
    CONVERSATION_WINDOW: int = int(os.getenv("CONVERSATION_WINDOW", "6"))
    MEMORY_WINDOW_SIZE: int = int(os.getenv("MEMORY_WINDOW_SIZE", "6"))
    
    # ==================== Agent配置 ====================
    AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
    AGENT_TEMPERATURE: float = float(os.getenv("AGENT_TEMPERATURE", "0.7"))
    AGENT_MAX_TOKENS: int = int(os.getenv("AGENT_MAX_TOKENS", "800"))
    
    # ==================== 向量存储配置 ====================
    VECTOR_STORE_PATH: str = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./data/agent.db")
    
    # ==================== LangChain配置 ====================
    LANGCHAIN_TRACING: bool = os.getenv("LANGCHAIN_TRACING", "false").lower() == "true"
    
    # ==================== 工具配置 ====================
    WEATHER_TIMEOUT: int = int(os.getenv("WEATHER_TIMEOUT", "10"))  # 天气查询超时时间
    MAX_TOOL_RETRIES: int = int(os.getenv("MAX_TOOL_RETRIES", "3"))  # 工具重试次数
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

    def validate_settings(self):
        """
        验证配置参数的有效性
        
        Raises:
            ValueError: 当必要配置缺失或无效时
        """
        required_settings = [
            ("ARK_API_KEY", self.ARK_API_KEY),
            ("AMAP_API_KEY", self.AMAP_API_KEY)
        ]
        
        for name, value in required_settings:
            if not value or value.startswith("您的"):
                print(f"⚠️ 警告: 必需配置 {name} 未设置或使用默认值")
        
        # 验证端口范围
        if not (1 <= self.SERVER_PORT <= 65535):
            raise ValueError(f"服务器端口 {self.SERVER_PORT} 不在有效范围内")
        
        # 验证温度设置
        if not (0.0 <= self.AGENT_TEMPERATURE <= 2.0):
            raise ValueError(f"Agent温度 {self.AGENT_TEMPERATURE} 不在有效范围内")
        
        print("✅ 配置验证完成，服务可以启动")

# 创建全局配置实例
settings = Settings()

# 应用启动时验证配置
try:
    settings.validate_settings()
except ValueError as e:
    print(f"❌ 配置验证失败: {e}")
    print("💡 请检查环境变量设置")
