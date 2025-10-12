# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（不包括项目本身）
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件（在安装 editable 模式之前）
COPY . .

# 安装项目本身（editable 模式）
RUN pip install --no-cache-dir -e .

# 创建数据目录（如果不存在）
RUN mkdir -p data

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

