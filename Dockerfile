FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements-api.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements-api.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY backend ./backend
COPY semob_ai ./semob_ai
COPY prompts ./prompts
COPY knowledge ./knowledge

RUN mkdir -p /app/data/database && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
