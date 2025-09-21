# Backend (FastAPI) image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     TZ=Europe/Paris

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Requirements placeholder (the codegen will provide real requirements)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App
COPY backend/ /app/

# Expose FastAPI on 8000
EXPOSE 8000

# Healthcheck (simple)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
