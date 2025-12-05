FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 1. Copy pyproject.toml AND README.md (Required by pyproject.toml)
COPY pyproject.toml README.md ./

# 2. Copy the code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# 3. Install dependencies
# 'pip install .' reads pyproject.toml, finds 'itsdangerous', and installs it.
RUN pip install --no-cache-dir .

# DEBUG: Add this line to verify installation in the build logs
RUN pip list | grep itsdangerous

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]