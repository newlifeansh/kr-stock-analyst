FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_MODULE=app.main:app \
    PORT=8000

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY docs /app/docs

RUN mkdir -p /app/data

RUN pip install --upgrade pip && pip install -e ".[mcp]"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT:-8000}"]
