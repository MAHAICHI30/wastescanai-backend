FROM python:3.11-slim

WORKDIR /app

# 不安装任何系统依赖！直接用 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--timeout", "120"]
