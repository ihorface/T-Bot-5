
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

# Install runtime deps
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY spot_executor_fastapi.py /app/spot_executor_fastapi.py

# Defaults
ENV PAPER=true
ENV PORT=10000

# Render/Cloud expect listening on $PORT
EXPOSE 10000
CMD ["sh","-c","uvicorn spot_executor_fastapi:app --host 0.0.0.0 --port ${PORT}"]
