# Hi-Tom-AI Backend Dockerfile
# 推荐用 Python 3.11，性能更好
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 防止 Python 生成 pyc 文件，并让日志直接输出到控制台
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. 先只复制依赖文件 (利用 Docker 缓存机制加速构建)
COPY requirements.txt .

# 2. 安装依赖 (使用清华源加速国内构建)
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 复制项目所有代码到容器
COPY . .

# 4. 创建 uploads 目录
RUN mkdir -p /app/uploads

# 暴露端口 (FastAPI 默认 8000)
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]