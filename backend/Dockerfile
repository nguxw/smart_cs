FROM python:3.12-slim

WORKDIR /app
COPY README.md /app/README.md
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY backend/data /app/data

RUN pip install --no-cache-dir -e .
RUN useradd -m smartcs
USER smartcs

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
