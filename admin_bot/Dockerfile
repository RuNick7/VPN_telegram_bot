# Built with the repo root as build context (see docker-compose.yml), so both
# admin_bot/ and shared/ are visible to COPY.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
COPY shared/ ./shared/
RUN pip install --no-cache-dir -r requirements.txt

COPY admin_bot/ ./admin_bot/

WORKDIR /app/admin_bot
CMD ["python", "main.py"]
