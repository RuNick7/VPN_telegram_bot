# Built with the repo root as build context (see docker-compose.yml), so both
# admin_bot/ and shared/ are visible to COPY.
FROM python:3.11-slim

# postgresql-client supplies pg_dump, used by the daily database-backup job.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
COPY shared/ ./shared/
RUN pip install --no-cache-dir -r requirements.txt

COPY admin_bot/ ./admin_bot/

WORKDIR /app/admin_bot
CMD ["python", "main.py"]
