FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY docs ./docs

RUN pip install --upgrade pip && pip install -e .

EXPOSE 8010

CMD ["sh", "-c", "alembic upgrade head && uvicorn agent_control_plane.main:app --host 0.0.0.0 --port 8010"]
