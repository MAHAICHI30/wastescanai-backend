# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 🌟 修复：使用新版 libgl1 代替已废弃的 libgl1-mesa-glx
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有文件到容器中
COPY . .

# 暴露 Flask 运行的 5001 端口
EXPOSE 5001

# 启动 Flask 服务
CMD ["python", "app.py"]
