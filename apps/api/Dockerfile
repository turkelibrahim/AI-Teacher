FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2/asyncpg if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]



