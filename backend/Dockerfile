FROM python:3.12-slim

WORKDIR /app
COPY README.md /app/README.md
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY backend/data /app/data

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
