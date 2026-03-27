FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 and geoalchemy2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Hot-reload dev server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-exclude", ".pytest_cache", "--reload-exclude", "__pycache__", "--reload-exclude", "pytest-cache-files-*"]
