FROM python:3.11-slim

# Prevents Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install runtime deps
RUN pip install --no-cache-dir fastapi uvicorn python-binance pydantic

# Copy app
WORKDIR /app
COPY spot_executor_fastapi.py /app/spot_executor_fastapi.py

# Default to PAPER (no live trading)
ENV PAPER=true
ENV PORT=8000

EXPOSE 8000
CMD ["uvicorn", "spot_executor_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
