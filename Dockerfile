# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 🌟 强力修复：安装 OpenCV 和 YOLOv8 必须依赖的完整底层系统库
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有文件到容器中
COPY . .

# 🌟 修复：将其改为 Railway 通用的 8080 端口（或者直接删掉这行，由系统自动接管）
EXPOSE 8080

# 启动 Flask 服务
CMD ["python", "app.py"]
