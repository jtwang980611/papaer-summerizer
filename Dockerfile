# 使用 Python 3.11 精简镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 复制项目文件
COPY app_fastapi.py .
COPY paper_summarizer.py .
COPY config/ ./config/

# 创建必要目录
RUN mkdir -p /app/data /app/summaries /app/temp

# 暴露端口
EXPOSE 7860

# 健康检查 - 使用 curl 替代 Python 以减少内存开销
HEALTHCHECK --interval=120s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# 启动应用 (使用FastAPI轻量版本)
CMD ["python", "app_fastapi.py"]
