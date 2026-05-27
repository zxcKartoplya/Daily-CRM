FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-test.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt \
    && pip install --user --no-cache-dir "psycopg2-binary>=2.9" \
    && pip install --user --no-cache-dir -r requirements-test.txt

FROM builder AS tester
COPY . .
ENV DATABASE_URL=sqlite:///:memory: \
    AUTH_SECRET=ci-test-secret
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "--junit-xml=/tmp/test-results.xml"]

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

USER app
WORKDIR /home/app/api

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/docs > /dev/null || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
