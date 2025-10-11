#!/usr/bin/env python3
"""启动 FastAPI 服务器的脚本."""

import uvicorn
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

