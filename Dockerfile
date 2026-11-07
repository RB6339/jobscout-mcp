FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JOBSCOUT_DB=/app/data/jobscout.db
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data/jobs_sample.json ./data/jobs_sample.json
RUN pip install --no-cache-dir -e .

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["uvicorn", "jobscout.api:app", "--host", "0.0.0.0", "--port", "8080"]
