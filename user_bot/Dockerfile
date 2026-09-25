# Built with the repo root as build context (see docker-compose.yml), so both
# user_bot/ and shared/ are visible to COPY. Same image serves two
# docker-compose services (polling bot, webhook server) via a `command:`
# override -- see docker-compose.yml.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
COPY shared/ ./shared/
RUN pip install --no-cache-dir -r requirements.txt

COPY user_bot/ ./user_bot/

WORKDIR /app/user_bot
CMD ["python", "bot.py"]
