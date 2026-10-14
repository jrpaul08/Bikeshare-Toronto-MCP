FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY collector.py ./

ENV PATH="/app/.venv/bin:$PATH"
ENV DATA_DIR=/data

CMD ["python", "collector.py"]