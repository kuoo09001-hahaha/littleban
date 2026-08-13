相关依赖项：
一、安装uvicorn
	1. 在 PowerShell 中执行以下命令，确认是否安装 uvicorn：pip show uvicorn
	2. 若无输出，则执行：pip install uvicorn
二、安装FastAPI
	1. 在 PowerShell 中执行以下命令，确认是否安装FastAPI pip show fastapi

项目/
├── main.py
├── core/
│   ├── config.py
│   ├── asr.py          # ASR模型管理
│   ├── utils.py  # 音频处理工具
│   └── keyword_utils.py # 关键字分析工具
└── routers/
    ├── audio_router.py    # 合并所有音频相关功能
    └── keyword_router.py  # 关键字分析功能

重启服务
cd C:\Users\DELL\Desktop
uvicorn HDZB_ASR.main:app --host localhost --port 8015 --reload


