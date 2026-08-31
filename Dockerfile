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

CMD ["sh", "-c", "exec uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT:-8000} --backlog ${UVICORN_BACKLOG:-4096} --timeout-keep-alive ${UVICORN_KEEP_ALIVE:-75} --ws-ping-interval ${UVICORN_WS_PING_INTERVAL:-20} --ws-ping-timeout ${UVICORN_WS_PING_TIMEOUT:-20} --ws-per-message-deflate ${UVICORN_WS_PER_MESSAGE_DEFLATE:-false} --no-access-log"]
