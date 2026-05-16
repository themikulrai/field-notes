FROM python:3.11-slim
RUN pip install --no-cache-dir uv==0.5.* && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY pyproject.toml ./
COPY packages/schema/ ./packages/schema/
COPY apps/api/ ./apps/api/
RUN uv sync --no-dev --package field-notes-api
ENV PYTHONPATH=/repo
EXPOSE 8000
HEALTHCHECK --interval=10s CMD curl -fsS http://localhost:8000/healthz || exit 1
CMD ["uv", "run", "--package", "field-notes-api", "uvicorn", "field_notes_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
