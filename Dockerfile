FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY dbt ./dbt

ENV PYTHONUNBUFFERED=1

CMD ["python", "src/orchestration/run_pipeline.py", "2026"]