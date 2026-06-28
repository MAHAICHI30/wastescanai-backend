FROM python:3.11-slim

WORKDIR /app

# 1. 更新包列表（使用官方源，添加重试）
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 复制项目文件
COPY . .

# 4. 启动服务
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--timeout", "120"]
