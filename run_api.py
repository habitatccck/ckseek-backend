#!/usr/bin/env python3
"""启动 FastAPI 服务器的脚本."""

import os
import uvicorn
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

if __name__ == "__main__":
    # 从环境变量获取端口，默认为 8000（支持 Railway 部署）
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

